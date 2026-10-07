local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local CombatShared = Shared:WaitForChild("combat")
local CharacterConfig = require(CharacterShared:WaitForChild("CharacterConfig"))
local AttackConfig = require(CombatShared:WaitForChild("AttackConfig"))
local WeaponAttackVolume = require(CombatShared:WaitForChild("WeaponAttackVolume"))
local UiInputGuard = require(script.Parent.Parent:WaitForChild("UiInputGuard"))
local AttackController = {}
local started = false
local movementController: any = nil
local animationController: any = nil
local aimPoseController: any = nil
local attackSequence = 0
local activePoseAttackId = 0
local activePoseUntil = 0
local activePoseStartedAt = 0
local poseAccumulator = 0
local weaponPoseRemote: RemoteEvent? = nil


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
    weaponPoseRemote:FireServer({
        clientAttackId = activePoseAttackId,
        elapsed = math.max(0, os.clock() - activePoseStartedAt),
        boxCFrame = boxCFrame,
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
    if aimPoseController and aimPoseController.EndAttack then
        aimPoseController.EndAttack()
    end
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

    RunService.RenderStepped:Connect(function(deltaTime)
        if activePoseAttackId <= 0 then
            return
        end
        if os.clock() > activePoseUntil then
            activePoseAttackId = 0
            poseAccumulator = 0
            return
        end
        poseAccumulator += deltaTime
        if poseAccumulator >= AttackConfig.WeaponPoseSampleInterval then
            poseAccumulator = poseAccumulator % AttackConfig.WeaponPoseSampleInterval
            publishWeaponPose()
        end
    end)
    UserInputService.InputBegan:Connect(function(input, processed)
        if input.UserInputType ~= CharacterConfig.InputBindings.AttackPrimary[1] or UiInputGuard.BlocksWorldInput(input, processed) then return end

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

        local hitEvent = action.timeline and action.timeline.events and action.timeline.events.Hit
        local hitTime = tonumber(hitEvent and hitEvent.time)
        if hitTime == nil then
            warn(("[game1][attack] action has no Hit timeline event: %s"):format(tostring(action.clipId)))
            return
        end

        attackSequence += 1
        local sequence = attackSequence
        local attackDuration = math.max(0.05, tonumber(action.durationSeconds) or 0.05)
        local damagePoseDuration = math.clamp(hitTime, 0, attackDuration)
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
                local playbackSpeed = math.max(0.01, tonumber(action.playbackSpeed) or 1)
                local timelineScale = 1 / playbackSpeed
                local facingTurnDuration = math.min(attackDuration, AttackConfig.FacingTurnSeconds * timelineScale)

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
                if aimPoseController then
                    -- Same target and same complete attack lifetime as gameplay.
                    -- TorsoAimResponse controls interpolation, not early release.
                    aimPoseController.BeginAttack(target, attackDuration)
                end
            end
        end

        task.delay(attackDuration, function()
            finishPresentation(sequence)
        end)

        -- The server validates the same authored Hit event. Weapon contact is
        -- damaging only from attack start through Hit, so pose streaming stops at
        -- that moment even though presentation/cooldown continues to clip end.
        activePoseAttackId = sequence
        activePoseStartedAt = os.clock()
        activePoseUntil = activePoseStartedAt + damagePoseDuration
        poseAccumulator = 0
        attack:FireServer({
            aim = target,
            clipId = action.clipId,
            clientAttackId = sequence,
        })
        publishWeaponPose()
    end)
end
return AttackController
