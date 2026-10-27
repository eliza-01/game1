-- Real Estate physics layer. Pure mesh naming + one writer for physics flags.
-- Collision geometry is an independent Roblox Model Asset with no Image ID.
local Policy = {}

function Policy.IsCollider(name: string): boolean
    local lower = string.lower(name)
    return lower:sub(1, 4) == "col_" or lower:find("_col_", 1, true) ~= nil
        or lower:sub(-4) == "_col"
end

function Policy.Apply(mesh: MeshPart, name: string, raw: any)
    local collider = Policy.IsCollider(name)
    local settings = typeof(raw) == "table" and raw or {}
    local noCollide = not collider
    if typeof(settings.noCollide) == "boolean" then
        noCollide = settings.noCollide
    end
    -- Raycasts (including GroundSensor) must see the collision surface.
    -- Set ordering matters: CanQuery=false requires CanCollide=false.
    if noCollide then
        mesh.CanCollide = false
        mesh.CanQuery = false
    else
        mesh.CanQuery = true
        mesh.CanCollide = true
    end
    mesh.CanTouch = false -- physics is not a Touched-based interaction trigger
    if collider then
        mesh.Transparency = 1
        mesh.CastShadow = false
        mesh.Anchored = true
        -- One concave mesh is allowed but not exact; do not use Hull/Box for
        -- holes and openings. For large estates, split into simple volumes.
        mesh.CollisionFidelity = Enum.CollisionFidelity.PreciseConvexDecomposition
        mesh:SetAttribute("Game1RealEstatePhysicsOnly", true)
    else
        mesh:SetAttribute("Game1RealEstatePhysicsOnly", nil)
    end
end

return table.freeze(Policy)
