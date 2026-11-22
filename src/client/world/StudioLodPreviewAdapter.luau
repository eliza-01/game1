-- Authoring Place presentation adapter. The production streamer owns the tick,
-- distance policy and budget; authoring meshes remain available for physics.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
local RunService = game:GetService("RunService")
local World = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("world")
local Contract = require(World:WaitForChild("StudioLodPreviewContract"))
local Policy = require(World:WaitForChild("LocationLodDistancePolicy"))
local Physics = require(World:WaitForChild("MeshPhysicsCore"))
local Registry = require(World:WaitForChild("LocationAssetRegistry"))
local Adapter = {}
Adapter.__index = Adapter

local function owner(part)
    local node = part.Parent
    while node and node ~= Workspace do
        if node:IsA("Model") then
            local house = node:GetAttribute("Game1RealEstateSlug")
            if type(house) == "string" and house ~= "" then return node, house, true end
            local slug = node:GetAttribute("Game1DecoAssetSlug")
            if node:GetAttribute("LandscapeAuthoringTool") == "Game1LandscapePainter" then
                slug = node:GetAttribute("LandscapeAssetSlug")
            elseif node:GetAttribute("AuthoringTool") == "Game1LandscapePainter" then
                return nil
            end
            if type(slug) == "string" and slug ~= "" then
                return node, (Registry.aliases or {})[slug] or slug, false
            end
        end
        node = node.Parent
    end
    return nil
end
local function visual(part)
    return part:IsA("MeshPart") and not Physics.IsLocationCarrier(part)
        and not Physics.IsCollider(part.Name) and part:GetAttribute("Game1DecoPhysicsOnly") ~= true
end
local function restore(record)
    if record.clone then record.clone:Destroy(); record.clone = nil end
    for part, original in pairs(record.parts) do
        if part.Parent then part.LocalTransparencyModifier = original end
    end
    record.actual = nil
    record.assetId = nil
end

function Adapter.new(originalTransparency)
    if not RunService:IsStudio() then return nil end
    local self = setmetatable({inventory={}, records={}, managed={}, dirty=true, digest=nil, failedTemplates={}}, Adapter)
    self.originalTransparency = originalTransparency
    self.folder = Instance.new("Folder")
    self.folder.Name = "Game1StudioLodVisuals"
    self.folder.Parent = Workspace
    local function add(part)
        if visual(part) and not part:IsDescendantOf(self.folder) then
            local root, slug, house = owner(part)
            if root then
                self.inventory[part] = {root=root, slug=slug, house=house}
                self.dirty = true
            end
        end
    end
    Workspace.DescendantAdded:Connect(add)
    Workspace.DescendantRemoving:Connect(function(part)
        if self.inventory[part] then self.inventory[part] = nil; self.dirty = true end
    end)
    for _, part in ipairs(Workspace:GetDescendants()) do add(part) end
    return self
end

function Adapter:Owns(part) return self.managed[part] == true end

function Adapter:_refresh()
    local marker = ReplicatedStorage:FindFirstChild(Contract.Marker)
    local raw = if marker and marker:IsA("StringValue") then marker.Value else nil
    if raw ~= self.raw then
        self.raw = raw
        self.candidate = Contract.Read(marker)
        self.dirty = true
    end
    local data = self.candidate
    local digest = data and data.digest or nil
    if digest ~= self.digest then self.dirty = true end
    if not self.dirty then return end
    self.dirty = false
    self.digest = digest
    self.data = data
    self.failedTemplates = {}
    -- Reconcile ownership by exact live Instance, never by name alone.
    local nextRecords = {}
    local nextManaged = {}
    for part, entry in pairs(self.inventory) do
        if not data or not part:IsDescendantOf(Workspace) then continue end
        local profile = if entry.house then data.houses[entry.slug] else data.locations[entry.slug]
        if not profile then continue end
        local spec = if entry.house then profile.parts[part.Name] else profile
        if not spec then continue end
        local key = if entry.house then part else entry.root
        local record = nextRecords[key]
        if not record then
            local old = self.records[key]
            record = {root=entry.root, house=entry.house, parts={}, spec=spec, mode=profile.mode,
                actual=old and old.actual, desired=old and old.desired, assetId=old and old.assetId,
                clone=old and old.clone, distance=math.huge}
            nextRecords[key] = record
        end
        local old = self.records[key]
        record.parts[part] = if old and old.parts[part] ~= nil then old.parts[part] else self.originalTransparency(part)
        if not old or old.parts[part] == nil then record.actual = nil end
        nextManaged[part] = true
    end
    for key, old in pairs(self.records) do
        local nextRecord = nextRecords[key]
        if not nextRecord then restore(old) else
            for part, original in pairs(old.parts) do
                if nextRecord.parts[part] == nil and part.Parent then part.LocalTransparencyModifier = original end
            end
        end
    end
    self.records = nextRecords
    self.managed = nextManaged
end

function Adapter:Resolve(cameraPosition)
    self:_refresh()
    if not self.data then return end
    for _, record in pairs(self.records) do
        local part, count = nil, 0
        for mesh in pairs(record.parts) do part = mesh; count += 1 end
        record.source = if count == 1 then part else nil
        if record.mode == "off" then
            record.distance = 0
            record.desired = "FULL"
        elseif record.house then
            record.distance = Policy.SurfaceDistance(cameraPosition, part.CFrame, part.Size)
            local spec = record.spec
            local mode = if record.mode == "lod1" and spec.assetId ~= "" then "lod1" else "full"
            record.desired = Policy.ResolveHouse(record.distance, record.desired, {
                mode=mode, lod1=spec.lod1, hide=spec.hide, hysteresis=self.data.hysteresis})
        else
            record.distance = (cameraPosition - record.root:GetPivot().Position).Magnitude
            -- Composite FULL meshes cannot safely be replaced by an arbitrary
            -- one-mesh template in the editable Place. Keep FULL until hide.
            local mode = record.mode
            if not record.source or record.spec.lod1 == "" then mode = "full"
            elseif mode == "lod2" and record.spec.lod2 == "" then mode = "lod1" end
            record.desired = Policy.Resolve(record.distance, record.desired, Policy.WithHysteresis(record.spec.distances, self.data.hysteresis), mode)
        end
    end
end

local function copyAppearance(clone, source)
    clone.Color = source.Color
    clone.Material = source.Material
    clone.Transparency = source.Transparency
    clone.TextureID = source.TextureID
    clone.DoubleSided = source.DoubleSided
    clone.CastShadow = source.CastShadow
    clone.LocalTransparencyModifier = 0
    for _, child in ipairs(clone:GetChildren()) do
        if child:IsA("SurfaceAppearance") then child:Destroy() end
    end
    local surface = source:FindFirstChildOfClass("SurfaceAppearance")
    if surface then
        local copy = surface:Clone()
        if copy then copy.Parent = clone end
    end
end

function Adapter:Step(budget)
    local cache = ReplicatedStorage:FindFirstChild(Contract.Cache)
    local ordered = {}
    for _, record in pairs(self.records) do table.insert(ordered, record) end
    table.sort(ordered, function(a,b)
        local aUnload = a.desired == "UNLOADED" and a.actual ~= "UNLOADED"
        local bUnload = b.desired == "UNLOADED" and b.actual ~= "UNLOADED"
        if aUnload ~= bUnload then return aUnload end
        return a.distance < b.distance
    end)
    local changes = 0
    for _, record in ipairs(ordered) do
        if changes >= budget then break end
        local desired = record.desired
        local cost = 0
        for _ in pairs(record.parts) do cost += 1 end
        cost = math.min(budget, math.max(1, cost))
        if changes + cost > budget then continue end
        local id = if desired == "LOD1" then (if record.house then record.spec.assetId else record.spec.lod1)
            elseif desired == "LOD2" then record.spec.lod2 else nil
        if desired == record.actual and id == record.assetId then continue end
        local replacement = nil
        if id then
            local template = cache and cache:FindFirstChild(id)
            if template and template:IsA("MeshPart") and record.source and not self.failedTemplates[id] then
                local ok, reason = pcall(function()
                    replacement = template:Clone()
                    replacement.Name = record.source.Name .. "__PreviewLOD"
                    replacement.CFrame = record.source.CFrame
                    replacement.Size = record.source.Size
                    copyAppearance(replacement, record.source)
                    replacement.Parent = self.folder
                end)
                if not ok then
                    if replacement then replacement:Destroy(); replacement = nil end
                    self.failedTemplates[id] = true
                    warn("[game1][LOD preview] could not present " .. id .. ": " .. tostring(reason))
                end
            end
            if not replacement then
                -- Never hide FULL while a replacement is loading or invalid.
                desired = "FULL"
                id = nil
                if desired == record.actual then continue end
            end
        end
        if record.clone then record.clone:Destroy() end
        record.clone = replacement
        for part, original in pairs(record.parts) do
            if part:IsDescendantOf(Workspace) then
                part.LocalTransparencyModifier = if desired == "FULL" then original else 1
            end
        end
        record.actual = desired
        record.assetId = id
        changes += cost
    end
    return changes
end

function Adapter:FollowMoving()
    for _, record in pairs(self.records) do
        if record.clone and record.source and record.source:IsDescendantOf(Workspace) then
            record.clone.CFrame = record.source.CFrame
            record.clone.Size = record.source.Size
            record.clone.Color = record.source.Color
            record.clone.Material = record.source.Material
        end
    end
end
function Adapter:Stats()
    local counts = {FULL=0, LOD1=0, LOD2=0, UNLOADED=0}
    for _, record in pairs(self.records) do if record.actual then counts[record.actual] += 1 end end
    return counts
end
return table.freeze(Adapter)
