-- M621 Prototype Readiness Cache oracle using mock Instances and signals.
table.freeze = function(value) return value end
function typeof(value)
    if type(value) == "table" and value.__robloxType then return value.__robloxType end
    return type(value)
end

local function signal()
    local s = {connections = {}}
    function s:Connect(callback)
        local connection = {connected = true, callback = callback}
        function connection:Disconnect() self.connected = false end
        table.insert(self.connections, connection)
        return connection
    end
    function s:Fire(...)
        local snapshot = {}
        for _, connection in ipairs(self.connections) do table.insert(snapshot, connection) end
        for _, connection in ipairs(snapshot) do
            if connection.connected then connection.callback(...) end
        end
    end
    function s:CountConnected()
        local count = 0
        for _, connection in ipairs(self.connections) do if connection.connected then count = count + 1 end end
        return count
    end
    return s
end

local function instance(className, name)
    local object = {
        ClassName = className, Name = name, Parent = nil, children = {}, attributes = {},
        propertySignals = {}, attributeSignals = {}, ChildAdded = signal(), ChildRemoved = signal(),
    }
    function object:IsA(class)
        if self.ClassName == class then return true end
        if class == "BasePart" then return self.ClassName == "Part" or self.ClassName == "MeshPart" end
        if class == "Instance" then return true end
        return false
    end
    function object:GetChildren() return self.children end
    function object:FindFirstChild(name)
        for _, child in ipairs(self.children) do if child.Name == name then return child end end
        return nil
    end
    function object:GetAttribute(name) return self.attributes[name] end
    function object:SetAttribute(name, value)
        self.attributes[name] = value
        local event = self.attributeSignals[name]
        if event then event:Fire() end
    end
    function object:GetAttributeChangedSignal(name)
        if not self.attributeSignals[name] then self.attributeSignals[name] = signal() end
        return self.attributeSignals[name]
    end
    function object:GetPropertyChangedSignal(name)
        if not self.propertySignals[name] then self.propertySignals[name] = signal() end
        return self.propertySignals[name]
    end
    function object:SetProperty(name, value)
        self[name] = value
        local event = self.propertySignals[name]
        if event then event:Fire() end
    end
    function object:AddChild(child)
        child.Parent = self
        table.insert(self.children, child)
        self.ChildAdded:Fire(child)
    end
    function object:RemoveChild(child)
        for i, current in ipairs(self.children) do
            if current == child then
                table.remove(self.children, i)
                child.Parent = nil
                self.ChildRemoved:Fire(child)
                return true
            end
        end
        return false
    end
    return object
end

local frame = {__robloxType = "CFrame", label = "test frame"}
local function mesh(name)
    local part = instance("MeshPart", name)
    part.Size = {1, 1, 1}
    part.CFrame = frame
    part.MeshId = "rbxassetid://1"
    return part
end

local metadataBuilds = 0
local assembly = {BuildMetadata = function(prototype)
    metadataBuilds = metadataBuilds + 1
    if prototype:IsA("MeshPart") then
        return {prototype = prototype, kind = "meshpart", count = 1,
            sourceName = prototype:GetAttribute("Game1LodSourceName") or prototype.Name,
            sourceFrame = prototype.CFrame, sourceSize = prototype.Size,
            sourceBase = {0, 0, 0}, parts = {{source = prototype, size = prototype.Size}}}, "ready"
    end
    return {prototype = prototype, kind = "model", count = #prototype:GetChildren(),
        sourceFrame = prototype:GetAttribute("Game1LodPublishedPivot"), parts = prototype:GetChildren()}, "ready"
end}

local Cache = dofile("src/client/world/LodPrototypeCache.luau")
local root = instance("Folder", "ReplicatedStorage")
local now = 0
local cache = Cache.new(root, "Game1LodTemplates", assembly, function() return now end)
local notifications = {}
local changed = cache:ConnectChanged(function(name) notifications[name] = (notifications[name] or 0) + 1 end)


-- Late folder and late prototype arrive after the cache object has already been created.
local status = cache:Resolve("sapling__LOD1", "LOD1")
assert(status == "missing")
local folder = instance("Folder", "Game1LodTemplates")
folder:SetAttribute("Ready", false)
root:AddChild(folder)
status = cache:Resolve("sapling__LOD1", "LOD1")
assert(status == "missing" and cache:FolderReady() == false)
local sapling = mesh("sapling__LOD1")
folder:AddChild(sapling)
local status, candidate, meta = cache:Resolve("sapling__LOD1", "LOD1")
assert(status == "ready" and candidate == sapling and meta.kind == "meshpart" and meta.count == 1)
local initialGeneration = meta.generation
for i = 1, 1000 do
    local repeated, same, repeatedMeta = cache:Resolve("sapling__LOD1", "LOD1")
    assert(repeated == "ready" and same == sapling and repeatedMeta == meta)
end
assert(cache:Stats().prototypeRefreshes == 1, "same MeshPart should be structurally cached")

-- A generic multi-part LOD stays incomplete until expected children and pivot replicate.
local model = instance("Model", "oak__LOD1")
model:SetAttribute("Game1LodVisualCount", 2)
model:SetAttribute("Game1LodPublishedPivot", frame)
model:AddChild(mesh("oak_a"))
folder:AddChild(model)
status = cache:Resolve("oak__LOD1", "LOD1")
assert(status == "incomplete")
model:AddChild(mesh("oak_b"))
local modelStatus, modelCandidate, modelMeta = cache:Resolve("oak__LOD1", "LOD1")
assert(modelStatus == "ready" and modelCandidate == model and modelMeta.count == 2)
local builds = metadataBuilds
for i = 1, 500 do
    local repeated, _, repeatedMeta = cache:Resolve("oak__LOD1", "LOD1")
    assert(repeated == "ready" and repeatedMeta == modelMeta)
end
assert(metadataBuilds == builds, "model bounds/metadata should not be rebuilt during steady state")

-- FULL composite contract is separate from the generic assembly attribute contract.
local full = instance("Model", "oak__FULL")
full:AddChild(mesh("oak_full_a"))
full:AddChild(mesh("oak_full_b"))
folder:AddChild(full)
local components = {{name = "oak_full_a"}, {name = "oak_full_b"}}
local fullStatus, fullCandidate, fullMeta = cache:Resolve("oak__FULL", "FULL", components, "oak_full_a\30oak_full_b")
assert(fullStatus == "ready" and fullCandidate == full and fullMeta.kind == "composite")
local checks = cache:Stats().contractChecks
for i = 1, 300 do
    local repeated, _, repeatedMeta = cache:Resolve("oak__FULL", "FULL", components, "oak_full_a\30oak_full_b")
    assert(repeated == "ready" and repeatedMeta == fullMeta)
end
assert(cache:Stats().contractChecks == checks, "FULL component contract should be memoized")
local refreshesBeforeFullReady = cache:Stats().prototypeRefreshes
local fullMetaBefore = fullMeta
now = 1.1
fullStatus, _, fullMeta = cache:Resolve("oak__FULL", "FULL", components, "oak_full_a\30oak_full_b")
assert(fullStatus == "ready" and fullMeta == fullMetaBefore and cache:Stats().prototypeRefreshes == refreshesBeforeFullReady,
    "a ready composite contract must not refresh the attribute-less generic Model")
full:RemoveChild(full:FindFirstChild("oak_full_b"))
fullStatus = cache:Resolve("oak__FULL", "FULL", components, "oak_full_a\30oak_full_b")
assert(fullStatus == "incomplete", "partial component replication must not be ready")
full:AddChild(mesh("oak_full_b"))
fullStatus, _, fullMeta = cache:Resolve("oak__FULL", "FULL", components, "oak_full_a\30oak_full_b")
assert(fullStatus == "ready" and fullMeta.childrenByName.oak_full_b)
full:FindFirstChild("oak_full_b"):SetProperty("Name", "wrong_component")
fullStatus = cache:Resolve("oak__FULL", "FULL", components, "oak_full_a\30oak_full_b")
assert(fullStatus == "incomplete", "renamed expected component invalidates its contract")

-- Contract-only incompleteness (same child count, wrong name) receives at most two retries.
local contractRetry = instance("Model", "contract_retry__FULL")
contractRetry:SetAttribute("Game1LodVisualCount", 2)
contractRetry:SetAttribute("Game1LodPublishedPivot", frame)
contractRetry:AddChild(mesh("expected_a")); contractRetry:AddChild(mesh("unexpected_b"))
folder:AddChild(contractRetry)
local retryComponents = {{name = "expected_a"}, {name = "expected_b"}}
local contractChecksBefore = cache:Stats().contractChecks
cache:Resolve("contract_retry__FULL", "FULL", retryComponents, "retry-contract")
now = 4.4; cache:Resolve("contract_retry__FULL", "FULL", retryComponents, "retry-contract")
now = 5.5; cache:Resolve("contract_retry__FULL", "FULL", retryComponents, "retry-contract")
now = 6.6; cache:Resolve("contract_retry__FULL", "FULL", retryComponents, "retry-contract")
assert(cache:Stats().contractChecks - contractChecksBefore == 3,
    "contract-incomplete cache should retry exactly twice after its initial validation")


-- Impossible generic count is invalid, not a forever-incomplete partial stream.
local invalidModel = instance("Model", "invalid__LOD1")
invalidModel:SetAttribute("Game1LodVisualCount", 2)
invalidModel:SetAttribute("Game1LodPublishedPivot", frame)
invalidModel:AddChild(mesh("a")); invalidModel:AddChild(mesh("b")); invalidModel:AddChild(mesh("c"))
folder:AddChild(invalidModel)
assert(cache:Resolve("invalid__LOD1", "LOD1") == "invalid")

-- Folder Ready gates bounded missing-template retries; Ready=true misses are event-only.
cache:Resolve("never__LOD1", "LOD1")
now = 1.1; cache:Resolve("never__LOD1", "LOD1")
now = 2.2; cache:Resolve("never__LOD1", "LOD1")
now = 3.3; cache:Resolve("never__LOD1", "LOD1")
assert(cache:Stats().retryScans == 2, "missing prototypes retry only twice per cache folder")
folder:SetAttribute("Ready", true)
scansBefore = cache:Stats().retryScans
now = 10; cache:Resolve("permanent__LOD1", "LOD1")
now = 11; cache:Resolve("permanent__LOD1", "LOD1")
assert(cache:Stats().retryScans == scansBefore, "Ready folder missing entries must not poll")

-- Replacement keeps a distinct generation and only dependent listeners are notified.
folder:RemoveChild(sapling)
local replacement = mesh("sapling__LOD1")
folder:AddChild(replacement)
local replacementStatus, replacementCandidate, replacementMeta = cache:Resolve("sapling__LOD1", "LOD1")
assert(replacementStatus == "ready" and replacementCandidate == replacement)
assert(replacementMeta.generation > initialGeneration, "replacement template must have a newer generation")
assert((notifications["sapling__LOD1"] or 0) > 0)

changed:Disconnect()
cache:Destroy()
assert(root.ChildAdded:CountConnected() == 0 and root.ChildRemoved:CountConnected() == 0,
    "root connections cleaned")
assert(folder.ChildAdded:CountConnected() == 0 and folder.ChildRemoved:CountConnected() == 0,
    "folder connections cleaned")
assert(replacement.ChildAdded:CountConnected() == 0 and replacement.ChildRemoved:CountConnected() == 0,
    "prototype connections cleaned")
print("M621: readiness states, late folder, event invalidation, metadata/contract cache, retries and cleanup passed")
