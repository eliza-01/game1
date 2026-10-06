local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local CombatShared = Shared:WaitForChild("combat")
local CharacterConfig = require(CharacterShared:WaitForChild("CharacterConfig"))
local AttackConfig = require(CombatShared:WaitForChild("AttackConfig"))
local AttackController = {}
local started = false
local movementController: any = nil
local animationController: any = nil
local aimPoseController: any = nil
local attackSequence = 0

function AttackController.Start(movement: any?, animation: any?, aimPose: any?)
    movementController = movement
    animationController = animation
    aimPoseController = aimPose
    if started then return end
    started = true
    local remotes = ReplicatedStorage:WaitForChild("Game1Remotes")
    local attack = remotes:WaitForChild("AttackIntent")
    UserInputService.InputBegan:Connect(function(input, processed)
        if processed or input.UserInputType ~= CharacterConfig.InputBindings.AttackPrimary[1] then return end

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

        local root = character:FindFirstChild("RootCollider")
        if root and root:IsA("BasePart") then
            local direction = Vector3.new(target.X - root.Position.X, 0, target.Z - root.Position.Z)
            if direction.Magnitude > 0.001 then
                local playbackSpeed = math.max(0.01, tonumber(action.playbackSpeed) or 1)
                local timelineScale = 1 / playbackSpeed
                local facingDuration = math.min(action.durationSeconds, AttackConfig.FacingTurnSeconds * timelineScale)
                local movementDuration = math.min(action.durationSeconds, AttackConfig.MovementLockSeconds * timelineScale)
                local poseDuration = math.min(action.durationSeconds, AttackConfig.AimPoseSeconds * timelineScale)

                attackSequence += 1
                local sequence = attackSequence
                if movementController then
                    movementController.LockMovement(movementDuration)
                    if movementController.BeginAimFacingCompensation then
                        movementController.BeginAimFacingCompensation(
                            facingDuration,
                            AttackConfig.TorsoYawLimit
                        )
                        movementController.UpdateAimFacingCompensation(direction.Unit)
                        task.delay(facingDuration, function()
                            if sequence == attackSequence and movementController then
                                movementController.EndAimFacingCompensation()
                            end
                        end)
                    else
                        movementController.LockFacing(direction.Unit, facingDuration)
                    end
                end
                if aimPoseController then
                    aimPoseController.BeginAttack(target, poseDuration)
                end
            end
        end

        -- The server validates clipId against the equipped animation profile and
        -- resolves the same authoritative timeline before scheduling any result.
        attack:FireServer({
            aim = target,
            clipId = action.clipId,
        })
    end)
end
return AttackController
