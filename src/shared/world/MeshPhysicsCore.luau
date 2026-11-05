-- One Studio MeshPart physics writer shared by Real Estate and Location Assets.
-- Every collidable MeshPart uses Precise. Box is the default for no-collision.
local Core = {}
local FIDELITY = {
    Box = Enum.CollisionFidelity.Box,
    Hull = Enum.CollisionFidelity.Hull,
    Default = Enum.CollisionFidelity.Default,
    PreciseConvexDecomposition = Enum.CollisionFidelity.PreciseConvexDecomposition,
}

function Core.IsCollider(name: string): boolean
    local lower = string.lower(name)
    return lower:sub(1, 4) == "col_" or lower:find("_col_", 1, true) ~= nil
        or lower:sub(-4) == "_col"
end

function Core.IsGlass(name: string): boolean
    return not Core.IsCollider(name) and string.find(string.lower(name), "glass", 1, true) ~= nil
end

function Core.Fidelity(name: string): Enum.CollisionFidelity
    local value = FIDELITY[name]
    if value == nil then error("unsupported CollisionFidelity: " .. tostring(name)) end
    return value
end

function Core.Apply(mesh: MeshPart, canCollide: boolean, fidelity: string, doubleSided: boolean)
    -- CanQuery=false requires CanCollide=false; assign in safe order.
    if canCollide then
        mesh.CanQuery = true
        mesh.CanCollide = true
    else
        mesh.CanCollide = false
        mesh.CanQuery = false
    end
    mesh.CanTouch = false
    mesh.CollisionFidelity = Core.Fidelity(if canCollide then "PreciseConvexDecomposition" else fidelity)
    mesh.DoubleSided = doubleSided
end

local function parts(model: Model): {MeshPart}
    local found = {}
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("MeshPart") then table.insert(found, descendant) end
    end
    return found
end

-- Both domains use Core.Apply as the only MeshPart property writer.
-- Location uses name classification plus saved per-mesh overrides. A missing
-- meshOptions entry means legacy behavior: never silently migrate a Place.
function Core.ApplyLocationModel(model: Model, allowedNames: {[string]: boolean}?, meshOptions: any?): number
    local allParts = parts(model)
    local hasCollider = false
    for _, mesh in ipairs(allParts) do
        if Core.IsCollider(mesh.Name) then hasCollider = true break end
    end
    local affected = 0
    for _, mesh in ipairs(allParts) do
        if allowedNames == nil or allowedNames[mesh.Name] == true then
            local collider, namedGlass = Core.IsCollider(mesh.Name), Core.IsGlass(mesh.Name)
            local raw = if typeof(meshOptions) == "table" then meshOptions[mesh.Name] else nil
            local explicit = typeof(raw) == "table"
            local glass = if explicit and typeof(raw.glass) == "boolean" then raw.glass else namedGlass
            local doublesided = if explicit and typeof(raw.doubleSided) == "boolean"
                then raw.doubleSided else false
            local defaultNoCollide = if hasCollider then not collider else not (collider or namedGlass)
            local noCollide = if explicit and typeof(raw.noCollide) == "boolean"
                then raw.noCollide else defaultNoCollide
            if explicit or hasCollider or collider or namedGlass then
                local fidelity = if noCollide and explicit and typeof(raw.collisionFidelity) == "string"
                    then raw.collisionFidelity elseif noCollide then "Box" else "PreciseConvexDecomposition"
                -- All collidable MeshParts are Precise, including COL_*.
                Core.Apply(mesh, not noCollide, fidelity, doublesided)
            else
                -- Legacy Location without COL: do not override pre-M232 published physics.
                mesh.CanTouch = false
                mesh.DoubleSided = false
            end
            if collider then
                mesh.Transparency = 1
                mesh.CastShadow = false
                mesh:SetAttribute("Game1DecoPhysicsOnly", true)
            else
                mesh:SetAttribute("Game1DecoPhysicsOnly", nil)
            end
            if glass then
                if mesh:GetAttribute("Game1DecoGlassApplied") ~= true then
                    mesh.Transparency = math.max(mesh.Transparency, 0.02)
                    mesh:SetAttribute("Game1DecoGlassApplied", true)
                end
            end
            affected += 1
        end
    end
    return affected
end

-- Scoped existing-placement physics updates can fail on locked Studio parts.
-- Capture before the first change and restore across every managed instance.
function Core.CaptureLocationModel(model: Model, allowedNames: {[string]: boolean}): {any}
    local saved = {}
    for _, mesh in ipairs(parts(model)) do
        if allowedNames[mesh.Name] == true then
            table.insert(saved, {part = mesh, canCollide = mesh.CanCollide,
                canQuery = mesh.CanQuery, canTouch = mesh.CanTouch,
                fidelity = mesh.CollisionFidelity, doubleSided = mesh.DoubleSided,
                transparency = mesh.Transparency, castShadow = mesh.CastShadow,
                physicsOnly = mesh:GetAttribute("Game1DecoPhysicsOnly"),
                glassApplied = mesh:GetAttribute("Game1DecoGlassApplied")})
        end
    end
    return saved
end

function Core.RestoreLocationModel(saved: {any})
    for _, entry in ipairs(saved) do
        local mesh = entry.part
        if mesh and mesh.Parent then
            if entry.canCollide then
                mesh.CanQuery = true
                mesh.CanCollide = true
            else
                mesh.CanCollide = false
                mesh.CanQuery = entry.canQuery
            end
            mesh.CanTouch = entry.canTouch
            mesh.CollisionFidelity = entry.fidelity
            mesh.DoubleSided = entry.doubleSided
            mesh.Transparency = entry.transparency
            mesh.CastShadow = entry.castShadow
            mesh:SetAttribute("Game1DecoPhysicsOnly", entry.physicsOnly)
            mesh:SetAttribute("Game1DecoGlassApplied", entry.glassApplied)
        end
    end
end

return table.freeze(Core)
