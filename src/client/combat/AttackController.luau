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
local lastAttack = 0
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
        local now = os.clock()
        local player = Players.LocalPlayer
        local character = player.Character
        local attackSpeed = math.max(1, tonumber(character and character:GetAttribute("AttackSpeed")) or 100)
        local localCooldown = AttackConfig.CooldownSeconds * (100 / attackSpeed) * 0.75
        if now - lastAttack < localCooldown then return end
        lastAttack = now
        local target = aimPoseController and aimPoseController.GetAimPosition and aimPoseController.GetAimPosition() or nil
        if target then
            local root = player.Character and player.Character:FindFirstChild("RootCollider")
            if root and root:IsA("BasePart") then
                local direction = Vector3.new(target.X - root.Position.X, 0, target.Z - root.Position.Z)
                if direction.Magnitude > 0.001 then
                    local speedScale = 100 / attackSpeed
                    local facingDuration = AttackConfig.FacingTurnSeconds * speedScale
                    local movementDuration = AttackConfig.MovementLockSeconds * speedScale
                    local poseDuration = AttackConfig.AimPoseSeconds * speedScale

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
                            -- Compatibility fallback for an older MovementController.
                            movementController.LockFacing(direction.Unit, facingDuration)
                        end
                    end
                    if aimPoseController then
                        aimPoseController.BeginAttack(target, poseDuration)
                    end
                end
            end
            if animationController then
                animationController.PlayAction("attack")
            end
            -- One aim point owns presentation and server intent. The server remains
            -- authoritative for range/hit/damage, while the client only poses toward
            -- the exact same point that was sent with this attack.
            attack:FireServer(target)
        end
    end)
end
return AttackController
