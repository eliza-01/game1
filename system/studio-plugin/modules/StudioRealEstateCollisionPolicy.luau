-- M342: Real Estate visual-mesh authoring. Collision Blueprint Parts are separate.
local Core = require(script.Parent.StudioMeshPhysicsCore)
local Policy = {}
local FIDELITY = {
    Box = Core.Fidelity("Box"),
    Hull = Core.Fidelity("Hull"),
    Default = Core.Fidelity("Default"),
    PreciseConvexDecomposition = Core.Fidelity("PreciseConvexDecomposition"),
}

function Policy.Apply(mesh: MeshPart, name: string, raw: any)
    local settings = if typeof(raw) == "table" then raw else {}
    local noCollide = if typeof(settings.noCollide) == "boolean" then settings.noCollide else true
    local fidelity = if typeof(settings.collisionFidelity) == "string"
        and FIDELITY[settings.collisionFidelity] then settings.collisionFidelity else "Box"
    Core.Apply(mesh, not noCollide, fidelity,
        if typeof(settings.doubleSided) == "boolean" then settings.doubleSided else false)
    mesh:SetAttribute("Game1RealEstateNoCollide", noCollide)
    mesh:SetAttribute("Game1RealEstateCollisionFidelity", fidelity)
    mesh:SetAttribute("Game1RealEstateDoubleSided", mesh.DoubleSided)
    mesh:SetAttribute("Game1RealEstatePhysicsOnly", nil)
    mesh:SetAttribute("Game1RealEstateDestructible", nil)
    if string.lower(name) == "house" then mesh.Anchored = true end
end

return table.freeze(Policy)
