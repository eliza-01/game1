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
local WeaponAttachmentController = require(script.Parent.Parent:WaitForChild("weapon"):WaitForChild("WeaponAttachmentController"))
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
local bowCaptureSequence = 0
local bowPresentationUntil = 0
local bowPresentationCharacter: Model? = nil
local weaponPoseRemote: RemoteEvent? = nil
local bowAimRemote: RemoteEvent? = nil


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
    bowCaptureSequence = 0
    bowPresentationUntil = 0
    bowPresentationCharacter = nil
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
        -- Bow is VISUALLY aimed continuously through the complete authored clip,
        -- including after Release. This never does an extra hit raycast, changes
        -- the frozen server snapshot or sends additional network packets.
        if bowCaptureSequence > 0 then
            local playerCharacter = Players.LocalPlayer.Character
            if playerCharacter ~= bowPresentationCharacter
                or not playerCharacter or playerCharacter:GetAttribute("LifeState") ~= "Alive"
                or os.clock() > bowPresentationUntil then
                finishPresentation(bowCaptureSequence)
            elseif aimPoseController and movementController then
                local origin, direction = aimPoseController.GetAimRay()
                if typeof(origin) == "Vector3" and typeof(direction) == "Vector3"
                    and direction.Magnitude > 1e-6 then
                    local target = origin + direction.Unit * AttackConfig.MaxAimDistance
                    aimPoseController.UpdateTarget(target, direction)
                    local root = playerCharacter:FindFirstChild("RootCollider")
                    if root and root:IsA("BasePart") then
                        movementController.UpdateAimFacingCompensation(target - root.Position)
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

        if not animationController then return end
        local isBow = string.lower(tostring(character:GetAttribute("EquippedWeaponType") or "")) == "bow"
        -- Bow facing starts with Draw, not with the late target snapshot.
        -- This ray is already used by AttackIntent: no additional world raycast
        -- or per-frame target tracking is needed before Release.
        local bowAimOrigin, bowAimDirection = nil, nil
        if isBow then
            if not aimPoseController or not aimPoseController.GetAimRay then return end
            bowAimOrigin, bowAimDirection = aimPoseController.GetAimRay()
            if typeof(bowAimOrigin) ~= "Vector3" or typeof(bowAimDirection) ~= "Vector3"
                or bowAimDirection.Magnitude <= 1e-6 then return end
        end
        local target = if isBow then nil else
            (aimPoseController and aimPoseController.GetAimPosition and aimPoseController.GetAimPosition() or nil)
        if not isBow and typeof(target) ~= "Vector3" then return end

        -- PlayAction owns the complete attack interval. It returns nil while the
        -- previous attack animation is still inside its configured timeline, so
        -- repeated input can never cut an attack short.
        local action = animationController.PlayAction("attack")
        if not action then
            return
        end

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
        -- Face the reticle immediately for Bow and Melee alike. Bow uses its
        -- initial camera direction only to drive presentation; the authoritative
        -- target is still captured just once close to Release.
        local presentationTarget = if isBow then
            bowAimOrigin + bowAimDirection.Unit * AttackConfig.MaxAimDistance else target
        if root and root:IsA("BasePart") then
            local direction = Vector3.new(presentationTarget.X - root.Position.X, 0,
                presentationTarget.Z - root.Position.Z)
            if direction.Magnitude > 0.001 then
                -- Facing is a gameplay interval, not a function of the FBX clip's
                -- individual playback multiplier.
                if isBow and movementController and movementController.BeginAimFacingCompensation then
                    -- Bow tracks the reticle while idle, moving and backpedalling.
                    -- The root follows full camera yaw; the spine absorbs the turn.
                    movementController.BeginAimFacingCompensation(
                        attackDuration, AttackConfig.TorsoYawLimit, true
                    )
                    movementController.UpdateAimFacingCompensation(direction.Unit)
                elseif movementController and not movingAtAttackStart then
                    local facingTurnDuration = math.min(attackDuration, AttackConfig.FacingTurnSeconds)
                    if movementController.BeginAimFacingCompensation then
                        -- Stationary melee retains its original one-shot
                        -- facing, released if locomotion takes over.
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
            -- The same torso controller applies both weapon types. The bow's
            -- cosmetic target follows the camera; Capture never changes it.
            aimPoseController.BeginAttack(presentationTarget, attackDuration)
        end


        task.delay(attackDuration, function()
            finishPresentation(sequence)
        end)

        -- The server schedules Release. The initial camera direction is only
        -- validated as an attack request; it is NOT a captured hit or target.
        if isBow then
            attack:FireServer({
                clipId = action.clipId,
                clientAttackId = sequence,
                aimOrigin = bowAimOrigin,
                aimDirection = bowAimDirection,
            })
            -- Exactly one late capture for SERVER damage. Presentation tracks
            -- the CAMERA ray each render frame without raycasts or remotes.
            bowCaptureSequence = sequence
            bowPresentationUntil = os.clock() + attackDuration
            bowPresentationCharacter = character
            local lead = math.min(BowProjectileConfig.CaptureLeadSeconds, damagePoseStart * 0.5)
            task.delay(math.max(0.025, damagePoseStart - lead), function()
                if sequence ~= bowCaptureSequence or sequence ~= attackSequence or player.Character ~= character
                    or character:GetAttribute("LifeState") ~= "Alive" then return end
                local origin, direction = aimPoseController.GetAimRay()
                if not origin or not direction then return end
                local launchOrigin = WeaponAttachmentController.GetBowReleaseOrigin(character)
                bowAimRemote:FireServer({
                    clientAttackId = sequence,
                    aimOrigin = origin,
                    aimDirection = direction,
                    launchOrigin = launchOrigin,
                })
                -- Capture is gameplay-only. Never snap the torso to a close
                -- surface at Release: the live camera ray still owns the pose.
            end)
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
        local meleeAimOrigin, meleeAimDirection = nil, nil
        if aimPoseController and aimPoseController.GetAimRay then
            meleeAimOrigin, meleeAimDirection = aimPoseController.GetAimRay()
        end
        attack:FireServer({
            clipId = action.clipId,
            clientAttackId = sequence,
            aimOrigin = meleeAimOrigin,
            aimDirection = meleeAimDirection,
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
