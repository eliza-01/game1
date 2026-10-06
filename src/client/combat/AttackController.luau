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
        if movementController.UnlockMovement then
            movementController.UnlockMovement()
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

        attackSequence += 1
        local sequence = attackSequence
        local attackDuration = math.max(0.05, tonumber(action.durationSeconds) or 0.05)
        local root = character:FindFirstChild("RootCollider")
        if root and root:IsA("BasePart") then
            local direction = Vector3.new(target.X - root.Position.X, 0, target.Z - root.Position.Z)
            if direction.Magnitude > 0.001 then
                local playbackSpeed = math.max(0.01, tonumber(action.playbackSpeed) or 1)
                local timelineScale = 1 / playbackSpeed
                local facingTurnDuration = math.min(attackDuration, AttackConfig.FacingTurnSeconds * timelineScale)

                if movementController then
                    -- RobloxLineage planted-melee contract: legs stay planted for
                    -- the COMPLETE attack, not only during the initial wind-up.
                    movementController.LockMovement(attackDuration)
                    if movementController.BeginAimFacingCompensation then
                        -- facingTurnDuration controls how quickly root overflow is
                        -- reached. Do NOT release it at that time; the final facing
                        -- is held until finishPresentation() at attack end.
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

        -- The server validates clipId against the equipped animation profile and
        -- resolves the same authoritative timeline before scheduling any result.
        attack:FireServer({
            aim = target,
            clipId = action.clipId,
        })
    end)
end
return AttackController
