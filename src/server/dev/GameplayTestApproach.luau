--!strict
-- Server-only lane gate. Attributes are immutable for a spawned test target.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local CharacterConfig = require(Shared:WaitForChild("character"):WaitForChild("CharacterConfig"))
local Approach = {}
function Approach.IsRestricted(model: Model): boolean
    return model:GetAttribute("GameplayTestKind") == "line" and model:GetAttribute("MonsterCombatType") == "ranged"
end
function Approach.Allows(model: Model, rootPosition: Vector3): boolean
    if not Approach.IsRestricted(model) then return true end
    local frame, size = model:GetAttribute("GameplayTestApproachFrame"), model:GetAttribute("GameplayTestApproachSize")
    if typeof(frame) ~= "CFrame" or typeof(size) ~= "Vector3" then return false end
    local p = frame:PointToObjectSpace(rootPosition - Vector3.new(0, CharacterConfig.RootAnchorOffset, 0))
    -- Strict borders: the sprint track itself is never part of the approach.
    return math.abs(p.X) < size.X / 2 and math.abs(p.Z) < size.Z / 2 and p.Y >= -0.75 and p.Y <= 4
end
return table.freeze(Approach)
