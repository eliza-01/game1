--!strict
-- Immutable spatial index of uncollidable authored flora. In Studio Play,
-- query actual Model bounds; compiled Runtime MUST use the verified LOD
-- placement manifest because its visual MeshParts are stripped from Workspace.
-- No Touched, physics queries or per-frame scanning.
local Workspace = game:GetService("Workspace")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local World = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("world")
local Registry = require(World:WaitForChild("LocationAssetRegistry"))
local Contract = require(World:WaitForChild("LocationRuntimeManifestContract"))
local Index = {}
local CELL = 32
local MAX_CELLS_PER_VOLUME = 100
local entries: {[Model]: any} = {}
local buckets: {[string]: {[any]: boolean}} = {}
local started = false
local compiledTargets: {[string]: boolean} = {}
local function key(x: number, z: number): string return x .. ":" .. z end
local function cell(x: number): number return math.floor(x / CELL) end
local function isFlora(slug: any): boolean
    if type(slug) ~= "string" then return false end
    local asset = Registry.assets[slug]
    return asset ~= nil and asset.status == "PUBLISHED"
        and (asset.category == "tree" or asset.category == "bush")
end

local function insert(frame: CFrame, size: Vector3, model: Model?): any?
    if size.X <= 0 or size.Y <= 0 or size.Z <= 0 then return nil end
    local r, u, l = frame.RightVector, frame.UpVector, frame.LookVector
    local ex = (math.abs(r.X)*size.X + math.abs(u.X)*size.Y + math.abs(l.X)*size.Z) / 2
    local ez = (math.abs(r.Z)*size.X + math.abs(u.Z)*size.Y + math.abs(l.Z)*size.Z) / 2
    local x0, x1 = cell(frame.Position.X-ex-5), cell(frame.Position.X+ex+5)
    local z0, z1 = cell(frame.Position.Z-ez-5), cell(frame.Position.Z+ez+5)
    if (x1-x0+1)*(z1-z0+1) > MAX_CELLS_PER_VOLUME then
        warn("[game1][flora] oversized contact volume skipped")
        return nil
    end
    local record = {frame = frame, size = size, model = model, cells = {}}
    for x = x0, x1 do
        for z = z0, z1 do
            local id = key(x, z)
            buckets[id] = buckets[id] or {}
            buckets[id][record] = true
            table.insert(record.cells, id)
        end
    end
    return record
end
local function erase(record)
    for _, id in ipairs(record.cells) do
        local bucket = buckets[id]
        if bucket then
            bucket[record] = nil
            if not next(bucket) then buckets[id] = nil end
        end
    end
end
local function unregister(model: Model)
    local record = entries[model]
    if not record then return end
    entries[model] = nil
    erase(record)
end
local function register(model: Model)
    if entries[model] or not model:IsDescendantOf(Workspace) then return end
    local slug = model:GetAttribute("Game1DecoAssetSlug") or model:GetAttribute("LandscapeAssetSlug")
    if not isFlora(slug) or compiledTargets[slug] then return end
    local ok, frame, size = pcall(function() return model:GetBoundingBox() end)
    if not ok then return end
    local record = insert(frame, size, model)
    if record then entries[model] = record end
end

local function frame(values): CFrame
    return CFrame.new(table.unpack(values))
end
local function runtimeIndex(): boolean
    local marker = ReplicatedStorage:FindFirstChild(Contract.MarkerName)
    if not marker and not RunService:IsStudio() then
        -- The marker is replicated from the published Place, not synthesized
        -- locally. A short grace period prevents a streaming-order race.
        marker = ReplicatedStorage:WaitForChild(Contract.MarkerName, 5)
    end
    if not marker then return true end -- Studio Play, uncompiled authoring Place
    if not marker:IsA("StringValue") then
        warn("[game1][flora] invalid Runtime marker; skipping contact index")
        return false
    end
    local manifest, decodeError = Contract.ReadManifest(marker)
    local valid, reason = false, decodeError or "invalid Runtime data"
    if manifest then valid, reason = Contract.Validate(manifest, Registry) end
    if not valid then
        warn("[game1][flora] invalid Runtime manifest: " .. tostring(reason))
        return false
    end
    -- Only streamed slugs use compiled immutable volumes. LOD-disabled
    -- flora remain ordinary Workspace models and need Studio-style indexing.
    for _, slug in ipairs(manifest.targets) do compiledTargets[slug] = true end
    for _, placement in ipairs(manifest.placements) do
        if isFlora(placement.slug) then
            if placement.components then
                for _, component in ipairs(placement.components) do
                    insert(frame(component.cframe), Vector3.new(table.unpack(component.size)), nil)
                end
            else
                insert(frame(placement.cframe), Vector3.new(table.unpack(placement.size)), nil)
            end
        end
    end
    return true
end
function Index.Start()
    if started then return end
    started = true
    -- Runtime streamed types use manifest bounds; disabled/nonstreamed flora
    -- continue to be recognized from ordinary Workspace models.
    if not runtimeIndex() then return end
    -- One initial Workspace inventory, later maintained by events.
    for _, object in ipairs(Workspace:GetDescendants()) do
        if object:IsA("Model") then register(object) end
    end
    Workspace.DescendantAdded:Connect(function(obj)
        if obj:IsA("Model") then
            register(obj)
            if not entries[obj] then task.defer(register, obj) end
        end
    end)
    Workspace.DescendantRemoving:Connect(function(obj)
        if obj:IsA("Model") then unregister(obj) end
    end)
end
-- The first value is an identity token, not a physics collider or Model.
function Index.Find(point: Vector3, padding: number): (any?, Vector3?)
    local bucket = buckets[key(cell(point.X), cell(point.Z))]
    if not bucket then return nil, nil end
    local nearest: any? = nil
    local contact: Vector3? = nil
    local best = math.huge
    for record in pairs(bucket) do
        local model = record.model
        if model and not model:IsDescendantOf(Workspace) then
            unregister(model)
            continue
        end
        local localPoint = record.frame:PointToObjectSpace(point)
        local half = record.size * 0.5
        local closest = Vector3.new(math.clamp(localPoint.X, -half.X, half.X),
            math.clamp(localPoint.Y, -half.Y, half.Y),
            math.clamp(localPoint.Z, -half.Z, half.Z))
        local distance = (localPoint - closest).Magnitude
        if distance <= padding and distance < best then
            nearest, contact, best = record, record.frame:PointToWorldSpace(closest), distance
        end
    end
    return nearest, contact
end
return table.freeze(Index)
