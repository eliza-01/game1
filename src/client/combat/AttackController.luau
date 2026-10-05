local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

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

local function aimPosition(): Vector3?
    local camera = Workspace.CurrentCamera
    if not camera then return nil end
    local mouse = UserInputService:GetMouseLocation()
    local ray = camera:ViewportPointToRay(mouse.X, mouse.Y)
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    local player = Players.LocalPlayer
    params.FilterDescendantsInstances = player.Character and { player.Character } or {}
    local hit = Workspace:Raycast(ray.Origin, ray.Direction * AttackConfig.MaxAimDistance, params)
    return if hit then hit.Position else ray.Origin + ray.Direction * AttackConfig.MaxAimDistance
end

function AttackController.Start(movement: any?, animation: any?)
    movementController = movement
    animationController = animation
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
        local target = aimPosition()
        if target then
            local root = player.Character and player.Character:FindFirstChild("RootCollider")
            if movementController and root and root:IsA("BasePart") then
                local direction = Vector3.new(target.X - root.Position.X, 0, target.Z - root.Position.Z)
                if direction.Magnitude > 0.001 then
                    movementController.LockFacing(direction.Unit, 0.28)
                    movementController.LockMovement(0.22)
                end
            end
            if animationController then
                animationController.PlayAction("attack")
            end
            attack:FireServer(target)
        end
    end)
end
return AttackController
