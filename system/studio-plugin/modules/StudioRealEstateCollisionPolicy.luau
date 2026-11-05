-- Real Estate physics profile; shared MeshPhysicsCore writes MeshPart physics.
-- New authored MeshParts default to single-sided; existing explicit overrides remain.
local CollectionService = game:GetService("CollectionService")
local Core = require(script.Parent.StudioMeshPhysicsCore)
local Policy = {}
local COLLIDER_TAG = "Game1RealEstateCollider"

local FIDELITY = {
    Box = Core.Fidelity("Box"),
    Hull = Core.Fidelity("Hull"),
    Default = Core.Fidelity("Default"),
    PreciseConvexDecomposition = Core.Fidelity("PreciseConvexDecomposition"),
}

function Policy.IsCollider(name: string): boolean
    return Core.IsCollider(name)
end

local function preciseByDefault(name: string): boolean
    local lower = string.lower(name)
    return Policy.IsCollider(name) or lower == "door" or lower:sub(1, 5) == "door_"
        or Core.IsGlass(name)
end

function Policy.Apply(mesh: MeshPart, name: string, raw: any)
    local collider = Policy.IsCollider(name)
    local settings = if typeof(raw) == "table" then raw else {}
    local preciseDefault = preciseByDefault(name)
    local noCollide = if typeof(settings.noCollide) == "boolean" then settings.noCollide
        else not preciseDefault
    -- The physical shape must be Precise for EVERY collidable part, regardless
    -- of its name or an old saved Default/Box/Hull value.
    local fidelity = if not noCollide then "PreciseConvexDecomposition" else settings.collisionFidelity
    if typeof(fidelity) ~= "string" or FIDELITY[fidelity] == nil then
        fidelity = if preciseDefault then "PreciseConvexDecomposition" else "Box"
    end

    -- Roblox requires CanQuery=true for collidable parts. Touch remains off
    -- (collision physics does not require a Touched event listener).
    Core.Apply(mesh, not noCollide, fidelity,
        if typeof(settings.doubleSided) == "boolean" then settings.doubleSided else false)
    -- Capture the *authoring policy* on the MeshPart itself. Studio copies can
    -- be revalidated without a Host Agent request or a full model reimport.
    -- This metadata is not a second registry: it is the applied snapshot.
    mesh:SetAttribute("Game1RealEstateNoCollide", noCollide)
    mesh:SetAttribute("Game1RealEstateCollisionFidelity", fidelity)
    mesh:SetAttribute("Game1RealEstateDoubleSided", mesh.DoubleSided)

    if collider then
        mesh.Transparency = 1
        mesh.CastShadow = false
        mesh.Anchored = true
        mesh:SetAttribute("Game1RealEstatePhysicsOnly", true)
        mesh:SetAttribute("Game1RealEstateDestructible", settings.destructible == true)
        CollectionService:AddTag(mesh, COLLIDER_TAG)
    else
        -- Houses are static buildings. Published MeshParts may be unanchored.
        if string.lower(name) == "house" then
            mesh.Anchored = true
        end
        mesh:SetAttribute("Game1RealEstatePhysicsOnly", nil)
        mesh:SetAttribute("Game1RealEstateDestructible", nil)
        if CollectionService:HasTag(mesh, COLLIDER_TAG) then
            CollectionService:RemoveTag(mesh, COLLIDER_TAG)
        end
    end
end

-- Studio copy/paste does not pass through Model.Place/PartSync. Reassert the
-- imported physical shape after a managed house enters Workspace, preserving
-- the explicit mesh settings recorded by Apply. Older templates (before this
-- snapshot existed) fall back to their copied collision toggles.
function Policy.RestoreCopiedMesh(mesh: MeshPart): boolean
    local noCollide = mesh:GetAttribute("Game1RealEstateNoCollide")
    if typeof(noCollide) ~= "boolean" then
        noCollide = not mesh.CanCollide
    end
    local fidelity = mesh:GetAttribute("Game1RealEstateCollisionFidelity")
    if typeof(fidelity) ~= "string" or FIDELITY[fidelity] == nil then
        fidelity = mesh.CollisionFidelity.Name
    end
    local doubleSided = mesh:GetAttribute("Game1RealEstateDoubleSided")
    if typeof(doubleSided) ~= "boolean" then
        doubleSided = mesh.DoubleSided
    end
    local expected = if noCollide then (FIDELITY[fidelity] or FIDELITY.Box)
        else FIDELITY.PreciseConvexDecomposition
    local needsRestore = mesh.CollisionFidelity ~= expected
        or mesh.CanCollide ~= not noCollide
        or mesh.CanQuery ~= not noCollide
        or mesh.CanTouch ~= false
        or mesh.DoubleSided ~= doubleSided
    if not needsRestore then return false end
    Policy.Apply(mesh, mesh.Name, {
        noCollide = noCollide,
        collisionFidelity = fidelity,
        doubleSided = doubleSided,
        destructible = mesh:GetAttribute("Game1RealEstateDestructible") == true,
    })
    return true
end

return table.freeze(Policy)
