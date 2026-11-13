-- Classification of existing Real Estate authoring rigs (M341).
-- No new collision mode is enabled here. A Game1RealEstatePhysicsRig
-- is the legacy imported COL_* MeshPart wrapper, not a Collision Blueprint.
-- Keep this predicate identical across placed visual and physics sync.
local Roles = {}

function Roles.IsLegacyCollisionRig(instance: Instance): boolean
    return instance:IsA("Model") and instance:GetAttribute("Game1RealEstatePhysicsRig") == true
end

function Roles.IsVisualRig(instance: Instance): boolean
    return instance:IsA("Model") and not Roles.IsLegacyCollisionRig(instance)
end

return table.freeze(Roles)
