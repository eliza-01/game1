-- Real Estate physics layer. Only this module writes MeshPart physics.
-- All authored visual parts are DoubleSided by default; COL_* remains physics-only.
local CollectionService = game:GetService("CollectionService")
local Policy = {}
local COLLIDER_TAG = "Game1RealEstateCollider"

local FIDELITY = {
    Box = Enum.CollisionFidelity.Box,
    Hull = Enum.CollisionFidelity.Hull,
    Default = Enum.CollisionFidelity.Default,
    PreciseConvexDecomposition = Enum.CollisionFidelity.PreciseConvexDecomposition,
}

function Policy.IsCollider(name: string): boolean
    local lower = string.lower(name)
    return lower:sub(1, 4) == "col_" or lower:find("_col_", 1, true) ~= nil
        or lower:sub(-4) == "_col"
end

local function preciseByDefault(name: string): boolean
    local lower = string.lower(name)
    return Policy.IsCollider(name) or lower == "door" or lower:sub(1, 5) == "door_"
        or lower:find("glass", 1, true) ~= nil
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
    mesh.CanCollide = not noCollide
    mesh.CanQuery = not noCollide
    mesh.CanTouch = false
    mesh.CollisionFidelity = FIDELITY[fidelity]
    mesh.DoubleSided = if typeof(settings.doubleSided) == "boolean" then settings.doubleSided else true

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

return table.freeze(Policy)
