local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local CombatShared = Shared:WaitForChild("combat")
local CharacterConfig = require(CharacterShared:WaitForChild("CharacterConfig"))
local AttackConfig = require(CombatShared:WaitForChild("AttackConfig"))
local CharacterAttackWindow = require(CombatShared:WaitForChild("CharacterAttackWindow"))
local WeaponAttackVolume = require(CombatShared:WaitForChild("WeaponAttackVolume"))
local BowProjectileConfig = require(CombatShared:WaitForChild("BowProjectileConfig"))
local UiInputGuard = require(script.Parent.Parent:WaitForChild("UiInputGuard"))
local AttackController = {}
local started = false
local movementController: any = nil
local animationController: any = nil
local aimPoseController: any = nil
local attackSequence = 0
local activePoseAttackId = 0
local activePoseFrom = 0
local activePoseUntil = 0
local activePoseStartedAt = 0
local poseAccumulator = 0
local weaponPoseRemote: RemoteEvent? = nil
local bowAimRemote: RemoteEvent? = nil
local bowAimAttackId = 0
local bowAimUntil = 0
local bowAimAccumulator = 0


local function publishWeaponPose()
    if not weaponPoseRemote or activePoseAttackId <= 0 then
        return
    end
    local character = Players.LocalPlayer.Character
    if not character or tostring(character:GetAttribute("LifeState") or "Alive") ~= "Alive" then
        return
    end
    local boxCFrame = WeaponAttackVolume.ReadEquippedWeaponBox(character)
    if typeof(boxCFrame) ~= "CFrame" then
        return
    end

    local aimOrigin = nil
    local aimDirection = nil
    if aimPoseController and aimPoseController.GetAimRay then
        aimOrigin, aimDirection = aimPoseController.GetAimRay()
    end
    weaponPoseRemote:FireServer({
        clientAttackId = activePoseAttackId,
        elapsed = math.max(0, os.clock() - activePoseStartedAt),
        boxCFrame = boxCFrame,
        aimOrigin = aimOrigin,
        aimDirection = aimDirection,
    })
end

local function finishPresentation(sequence: number)
    if sequence ~= attackSequence then
        return
    end
    if movementController then
        if movementController.EndAimFacingCompensation then
            movementController.EndAimFacingCompensation()
        end
        if movementController.UnlockFacing then
            movementController.UnlockFacing()
        end
        if movementController.EndAttackMovement then
            movementController.EndAttackMovement()
        end
    end
    bowAimAttackId = 0
    bowAimUntil = 0
    if aimPoseController and aimPoseController.EndAttack then
        aimPoseController.EndAttack()
    end
end

function AttackController.CancelForBounce(clientAttackId: number)
    local id = math.floor(tonumber(clientAttackId) or 0)
    if id <= 0 or id ~= attackSequence then
        return false
    end
    if activePoseAttackId == id then
        activePoseAttackId = 0
        activePoseFrom = 0
        activePoseUntil = 0
        poseAccumulator = 0
    end
    finishPresentation(id)
    return true
end

function AttackController.Start(movement: any?, animation: any?, aimPose: any?)
    movementController = movement
    animationController = animation
    aimPoseController = aimPose
    if started then return end
    started = true
    local remotes = ReplicatedStorage:WaitForChild("Game1Remotes")
    local attack = remotes:WaitForChild("AttackIntent")
    weaponPoseRemote = remotes:WaitForChild("AttackWeaponPose") :: RemoteEvent
    bowAimRemote = remotes:WaitForChild("BowAimUpdate") :: RemoteEvent

    RunService.RenderStepped:Connect(function(deltaTime)
        if bowAimAttackId > 0 then
            if os.clock() >= bowAimUntil then
                bowAimAttackId = 0
            else
                -- The same stationary attack facing compensation used by hands
                -- receives the live camera direction while the bow is drawn.
                -- This is a local presentation update; server aim packets retain
                -- their existing bounded rate and authoritative validation.
                local origin, direction = aimPoseController.GetAimRay()
                if direction and movementController and movementController.UpdateAimFacingCompensation then
                    movementController.UpdateAimFacingCompensation(direction)
                end
                bowAimAccumulator += deltaTime
                if bowAimAccumulator >= BowProjectileConfig.AimUpdateInterval then
                    bowAimAccumulator = 0
                    if origin and direction then
                        bowAimRemote:FireServer({
                            clientAttackId = bowAimAttackId,
                            aimOrigin = origin,
                            aimDirection = direction,
                        })
                    end
                end
            end
        end
        if activePoseAttackId <= 0 then
            return
        end
        local now = os.clock()
        if now > activePoseUntil then
            activePoseAttackId = 0
            activePoseFrom = 0
            poseAccumulator = 0
            return
        end
        if activePoseFrom > 0 then
            if now < activePoseFrom then
                return
            end
            -- Open the authored damage window with an immediate sample on the
            -- first rendered frame at/after HitStart. No pre-HitStart pose
            -- packets are sent because they can never deal damage.
            activePoseFrom = 0
            poseAccumulator = 0
            publishWeaponPose()
            return
        end
        poseAccumulator += deltaTime
        if poseAccumulator >= AttackConfig.WeaponPoseSampleInterval then
            poseAccumulator = poseAccumulator % AttackConfig.WeaponPoseSampleInterval
            publishWeaponPose()
        end
    end)
    local function attemptAttack()

        local player = Players.LocalPlayer
        local character = player.Character
        if not character or tostring(character:GetAttribute("LifeState") or "Alive") ~= "Alive" then
            return
        end

        local target = aimPoseController and aimPoseController.GetAimPosition and aimPoseController.GetAimPosition() or nil
        if typeof(target) ~= "Vector3" or not animationController then
            return
        end

        -- PlayAction owns the complete attack interval. It returns nil while the
        -- previous attack animation is still inside its configured timeline, so
        -- repeated input can never cut an attack short.
        local action = animationController.PlayAction("attack")
        if not action then
            return
        end

        local isBow = string.lower(tostring(character:GetAttribute("EquippedWeaponType") or "")) == "bow"
        local release = isBow and action.timeline and action.timeline.events
            and action.timeline.events[BowProjectileConfig.ReleaseEvent] or nil
        local damageWindow = if isBow then nil else CharacterAttackWindow.Resolve(action.timeline)
        if (isBow and not release) or (not isBow and not damageWindow) then
            warn(("[game1][attack] missing %s event(s): %s"):format(
                if isBow then "Release" else "HitStart/HitEnd", tostring(action.clipId)))
            return
        end

        attackSequence += 1
        local sequence = attackSequence
        local attackDuration = math.max(0.05, tonumber(action.durationSeconds) or 0.05)
        local damagePoseStart = math.clamp(if isBow then release.time else damageWindow.startTime, 0, attackDuration)
        local damagePoseEnd = if damageWindow then math.clamp(damageWindow.endTime, damagePoseStart, attackDuration) else damagePoseStart
        local movingAtAttackStart = movementController and movementController.IsMoving and movementController.IsMoving() or false
        if movementController and movementController.BeginAttackMovement then
            -- Every weapon may attack while moving. The equipped weapon type
            -- resolves an authored lower-body gait + RunSpeed fraction; no
            -- weapon-specific numbers live in this controller.
            movementController.BeginAttackMovement(character:GetAttribute("EquippedWeaponType"), attackDuration)
        end

        local root = character:FindFirstChild("RootCollider")
        if root and root:IsA("BasePart") then
            local direction = Vector3.new(target.X - root.Position.X, 0, target.Z - root.Position.Z)
            if direction.Magnitude > 0.001 then
                -- Facing is a gameplay interval, not a function of the FBX clip's
                -- individual playback multiplier.
                local facingTurnDuration = math.min(attackDuration, AttackConfig.FacingTurnSeconds)

                if movementController and not movingAtAttackStart then
                    if movementController.BeginAimFacingCompensation then
                        -- Stationary attacks may turn root overflow toward the
                        -- aim target and hold it for the complete attack. The
                        -- moment movement starts, MovementController releases
                        -- this root compensation and live locomotion owns facing.
                        movementController.BeginAimFacingCompensation(
                            facingTurnDuration,
                            AttackConfig.TorsoYawLimit
                        )
                        movementController.UpdateAimFacingCompensation(direction.Unit)
                    else
                        movementController.LockFacing(direction.Unit, attackDuration)
                    end
                end
            end
        end
        if aimPoseController then
            -- World-space yaw AND pitch follow the reticle for the complete
            -- authored attack, including targets directly above or below.
            aimPoseController.BeginAttack(target, attackDuration)
        end


        task.delay(attackDuration, function()
            finishPresentation(sequence)
        end)

        -- Projectile Release is clocked by the server, but the camera may still
        -- move while the bow animation draws. Sample the live aim until release.
        if isBow then
            local aimOrigin, aimDirection = aimPoseController.GetAimRay()
            if not aimOrigin or not aimDirection then
                finishPresentation(sequence)
                return
            end
            bowAimAttackId = sequence
            bowAimUntil = os.clock() + damagePoseStart
            bowAimAccumulator = 0
            attack:FireServer({
                clipId = action.clipId,
                clientAttackId = sequence,
                aimOrigin = aimOrigin,
                aimDirection = aimDirection,
            })
            return
        end

        -- Pose streaming exists only for the authored character melee window:
        -- HitStart through HitEnd. Presentation/cooldown still owns the complete
        -- animation, but no pose packet is sent before or after the damage window.
        activePoseAttackId = sequence
        activePoseStartedAt = os.clock()
        activePoseFrom = activePoseStartedAt + damagePoseStart
        activePoseUntil = activePoseStartedAt + damagePoseEnd
        poseAccumulator = 0
        attack:FireServer({
            clipId = action.clipId,
            clientAttackId = sequence,
        })
    end

    AttackController.RequestAttack = attemptAttack
    UserInputService.InputBegan:Connect(function(input, processed)
        if input.UserInputType == CharacterConfig.InputBindings.AttackPrimary[1]
            and not UiInputGuard.BlocksWorldInput(input, processed) then
            attemptAttack()
        end
    end)
end
return AttackController
