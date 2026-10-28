--!strict
-- Shared root resolver for game1 ControllerManager characters and standard
-- Humanoid avatars. Interaction services must not assume HumanoidRootPart.
local Workspace = game:GetService("Workspace")

local SpatialRoot = {}

function SpatialRoot.IsCustom(player: Player): boolean
    local character = player.Character
    return character ~= nil and character:GetAttribute("CustomCharacter") == true
end

function SpatialRoot.Get(player: Player): BasePart?
    local character = player.Character
    if not character or not character:IsDescendantOf(Workspace) then return nil end

    if character:GetAttribute("CustomCharacter") == true then
        if character:GetAttribute("LifeState") ~= "Alive" then return nil end
        local root = character:FindFirstChild("RootCollider")
            or character:FindFirstChild("NavigationRoot") or character.PrimaryPart
        return if root and root:IsA("BasePart") then root else nil
    end

    local humanoid = character:FindFirstChildOfClass("Humanoid")
    if not humanoid or humanoid.Health <= 0 then return nil end
    local root = character:FindFirstChild("HumanoidRootPart") or character.PrimaryPart
    return if root and root:IsA("BasePart") then root else nil
end

return table.freeze(SpatialRoot)
