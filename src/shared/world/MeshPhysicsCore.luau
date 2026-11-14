-- Shared visual MeshPart physics writer; special COL meshes are retired.
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

function Core.IsLocationCarrier(part: Instance): boolean
    return part:IsA("MeshPart") and part.Name == "rig_carrier"
end

function Core.IsGlass(name: string): boolean
    return string.find(string.lower(name), "glass", 1, true) ~= nil
end

function Core.Fidelity(name: string): Enum.CollisionFidelity
    local value = FIDELITY[name]
    if value == nil then error("unsupported CollisionFidelity: " .. tostring(name)) end
    return value
end

local function applyRuntimeProperties(mesh: MeshPart, canCollide: boolean, doubleSided: boolean)
    -- CanQuery=false requires CanCollide=false; assign in safe order.
    if canCollide then
        mesh.CanQuery = true
        mesh.CanCollide = true
    else
        mesh.CanCollide = false
        mesh.CanQuery = false
    end
    mesh.CanTouch = false
    mesh.DoubleSided = doubleSided
end

function Core.ApplyRuntime(mesh: MeshPart, canCollide: boolean, doubleSided: boolean)
    -- CollisionFidelity is PluginOrOpenCloud-only. Runtime reapplies the
    -- gameplay flags, while the Studio authoring pipeline remains the sole
    -- writer of the persisted decomposition policy.
    applyRuntimeProperties(mesh, canCollide, doubleSided)
end

function Core.Apply(mesh: MeshPart, canCollide: boolean, fidelity: string, doubleSided: boolean)
    applyRuntimeProperties(mesh, canCollide, doubleSided)
    mesh.CollisionFidelity = Core.Fidelity(fidelity)
end

local function parts(model: Model): {MeshPart}
    local found = {}
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("MeshPart") then table.insert(found, descendant) end
    end
    return found
end

-- M342: COL_* has no runtime role. Any retired geometry is deleted during
-- Studio preparation and Location loading. A visual mesh can still opt into
-- ordinary collisions via noCollide=false and a chosen CollisionFidelity.
local function applyLocationModel(model: Model, allowedNames: {[string]: boolean}?, meshOptions: any?, runtimeSafe: boolean): number
    local affected = 0
    for _, mesh in ipairs(parts(model)) do
        if not Core.IsLocationCarrier(mesh) and (allowedNames == nil or allowedNames[mesh.Name] == true) then
            local raw = if typeof(meshOptions) == "table" then meshOptions[mesh.Name] else nil
            local noCollide = if typeof(raw) == "table" and typeof(raw.noCollide) == "boolean"
                then raw.noCollide else false
            local doubleSided = if typeof(raw) == "table" and typeof(raw.doubleSided) == "boolean"
                then raw.doubleSided else false
            local fidelity = if typeof(raw) == "table" and typeof(raw.collisionFidelity) == "string"
                then raw.collisionFidelity else "Box"
            if runtimeSafe then
                Core.ApplyRuntime(mesh, not noCollide, doubleSided)
            else
                Core.Apply(mesh, not noCollide, fidelity, doubleSided)
            end
            mesh:SetAttribute("Game1DecoPhysicsOnly", nil)
            local glass = if typeof(raw) == "table" and typeof(raw.glass) == "boolean"
                then raw.glass else Core.IsGlass(mesh.Name)
            if glass and mesh:GetAttribute("Game1DecoGlassApplied") ~= true then
                mesh.Transparency = math.max(mesh.Transparency, 0.02)
                mesh:SetAttribute("Game1DecoGlassApplied", true)
            end
            affected += 1
        end
    end
    return affected
end

function Core.ApplyLocationModel(model: Model, allowedNames: {[string]: boolean}?, meshOptions: any?): number
    return applyLocationModel(model, allowedNames, meshOptions, false)
end

function Core.ApplyLocationModelRuntime(model: Model, allowedNames: {[string]: boolean}?, meshOptions: any?): number
    return applyLocationModel(model, allowedNames, meshOptions, true)
end

-- Semantic surface for future impact/footstep audio and interaction.
-- This does not own collision flags, sizes, meshes or appearance textures.
-- Only a selected explicit physical material changes Roblox Material; "default"
-- leaves historical authored Materials intact (including collision geometry).
function Core.ApplyLocationSurfaceMaterial(model: Model, surfaceKey: string?, physicalName: string?): number
    local key = if type(surfaceKey) == "string" and surfaceKey ~= "" then surfaceKey else "default"
    local material: Enum.Material? = nil
    if physicalName ~= nil and physicalName ~= "" then
        material = Enum.Material[physicalName]
        if material == nil then error("unsupported Location physical material " .. tostring(physicalName)) end
    end
    local changed = 0
    for _, mesh in ipairs(parts(model)) do
        if Core.IsLocationCarrier(mesh) then continue end
        local differs = mesh:GetAttribute("Game1LocationSurfaceMaterial") ~= key
        if material ~= nil and mesh.Material ~= material then differs = true end
        if differs then
            mesh:SetAttribute("Game1LocationSurfaceMaterial", key)
            if material ~= nil then mesh.Material = material end
            changed += 1
        end
    end
    return changed
end

function Core.CaptureLocationSurfaceMaterial(model: Model): {any}
    local old = {}
    for _, mesh in ipairs(parts(model)) do
        table.insert(old,{part=mesh,material=mesh.Material,
            key=mesh:GetAttribute("Game1LocationSurfaceMaterial")})
    end
    return old
end

function Core.RestoreLocationSurfaceMaterial(saved: {any})
    for _,entry in ipairs(saved) do
        if entry.part.Parent then
            entry.part.Material=entry.material
            entry.part:SetAttribute("Game1LocationSurfaceMaterial",entry.key)
        end
    end
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
