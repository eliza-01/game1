-- Shared, event-driven readiness cache for immutable Runtime LOD templates.
-- No scheduler, Workspace scan, Instance creation, or per-placement ownership.
local Cache = {}
Cache.__index = Cache

local RETRY_SECONDS = 1
local MAX_RETRIES = 2
local RELEVANT_ATTRIBUTES = {
    "Game1LodVisualCount",
    "Game1LodPublishedPivot",
    "Game1LodSourceName",
}


local function disconnectAll(connections)
    for _, connection in ipairs(connections) do
        pcall(function() connection:Disconnect() end)
    end
    for index = #connections, 1, -1 do connections[index] = nil end
end


local function connect(signal, callback, connections)
    if not signal or not signal.Connect then return end
    local ok, connection = pcall(function() return signal:Connect(callback) end)
    if ok and connection then table.insert(connections, connection) end
end


local function isCFrame(value)
    return typeof(value) == "CFrame"
end


local function componentSignature(components)
    if not components then return "" end
    local names = {}
    for _, component in ipairs(components) do
        table.insert(names, tostring(component.name or ""))
    end
    return table.concat(names, "\30")
end


local function countMap(map)
    local count = 0
    for _ in pairs(map) do count = count + 1 end
    return count
end


local function freezeMetadata(metadata)
    if not metadata or not table.freeze then return metadata end
    if metadata.parts then
        for _, descriptor in ipairs(metadata.parts) do table.freeze(descriptor) end
        table.freeze(metadata.parts)
    end
    if metadata.childrenByName then table.freeze(metadata.childrenByName) end
    return table.freeze(metadata)
end


function Cache.new(root, folderName, assembly, clock)
    local self = setmetatable({
        root = root,
        folderName = folderName,
        assembly = assembly,
        clock = clock or os.clock,
        folder = nil,
        folderReady = nil,
        folderGeneration = 0,
        folderRetryCount = 0,
        folderRetryAt = 0,
        folderConnections = {},
        rootConnections = {},
        rootChildConnections = {},
        prototypeEntries = {},
        byName = {},
        knownNames = {},
        nameGeneration = {},
        listeners = {},
        stats = {prototypeRefreshes = 0, contractChecks = 0, retryScans = 0},
    }, Cache)
    self:_watchRoot()
    self:_refreshFolder()
    return self
end


function Cache:ConnectChanged(callback)
    if type(callback) ~= "function" then return {Disconnect = function() end} end
    self.listeners[callback] = true
    local cache = self
    return {Disconnect = function()
        cache.listeners[callback] = nil
    end}
end


function Cache:_notify(name)
    if type(name) ~= "string" or name == "" then return end
    self.nameGeneration[name] = (self.nameGeneration[name] or 0) + 1
    for callback in pairs(self.listeners) do
        pcall(callback, name, self.nameGeneration[name])
    end
end


function Cache:_notifyAll(refreshEntries)
    for name in pairs(self.knownNames) do
        self:_notify(name)
        if refreshEntries then self:_syncGenerationForName(name) end
    end
end


function Cache:_watchRootChild(child)
    if self.rootChildConnections[child] then return end
    local connections = {}
    connect(child:GetPropertyChangedSignal("Name"), function()
        self:_refreshFolder()
    end, connections)
    self.rootChildConnections[child] = connections
end


function Cache:_unwatchRootChild(child)
    local connections = self.rootChildConnections[child]
    if not connections then return end
    disconnectAll(connections)
    self.rootChildConnections[child] = nil
end


function Cache:_watchRoot()
    for _, child in ipairs(self.root:GetChildren()) do self:_watchRootChild(child) end
    connect(self.root.ChildAdded, function(child)
        self:_watchRootChild(child)
        self:_refreshFolder()
    end, self.rootConnections)
    connect(self.root.ChildRemoved, function(child)
        self:_unwatchRootChild(child)
        self:_refreshFolder()
    end, self.rootConnections)
end


function Cache:_findFolder()
    for _, child in ipairs(self.root:GetChildren()) do
        if child.Name == self.folderName then return child end
    end
    return nil
end


function Cache:_refreshFolder()
    self:_attachFolder(self:_findFolder())
end


function Cache:_detachEntry(entry)
    disconnectAll(entry.connections)
    disconnectAll(entry.childConnections)
    self.prototypeEntries[entry.prototype] = nil
end


function Cache:_detachFolder()
    disconnectAll(self.folderConnections)
    for _, entry in pairs(self.prototypeEntries) do
        disconnectAll(entry.connections)
        disconnectAll(entry.childConnections)
    end
    self.prototypeEntries = {}
    self.byName = {}
    self.folder = nil
    self.folderReady = nil
end


function Cache:_syncGenerationForName(name)
    local prototype = self.byName[name]
    local entry = prototype and self.prototypeEntries[prototype]
    if entry then
        entry.generation = self.nameGeneration[name] or entry.generation
        entry.dirty = true
        entry.metadata = nil
        entry.snapshot = nil
        entry.contracts = {}
        entry.variantResults = {}
        entry.retries = 0
        entry.retryAt = 0
    end
end


function Cache:_rebuildMap(notifyChanges)
    local previous = self.byName
    local nextMap = {}
    local folder = self.folder
    if folder and folder:IsA("Folder") then
        for _, child in ipairs(folder:GetChildren()) do
            if nextMap[child.Name] == nil then nextMap[child.Name] = child end
        end
    end
    self.byName = nextMap
    if notifyChanges ~= false then
        local changed = {}
        for name, prototype in pairs(previous) do
            if nextMap[name] ~= prototype then changed[name] = true end
        end
        for name, prototype in pairs(nextMap) do
            if previous[name] ~= prototype then changed[name] = true end
        end
        for name in pairs(changed) do
            self:_notify(name)
            self:_syncGenerationForName(name)
        end
    end
end


function Cache:_watchChild(entry, child)
    local connections = {}
    local function invalidate()
        self:_invalidateEntry(entry)
    end
    connect(child:GetPropertyChangedSignal("Name"), invalidate, connections)
    if child:IsA("BasePart") then
        connect(child:GetPropertyChangedSignal("Size"), invalidate, connections)
        connect(child:GetPropertyChangedSignal("CFrame"), invalidate, connections)
        if child:IsA("MeshPart") then
            connect(child:GetPropertyChangedSignal("MeshId"), invalidate, connections)
        end
        connect(child:GetAttributeChangedSignal("Game1LodSourceName"), invalidate, connections)
        connect(child.ChildAdded, invalidate, connections)
        connect(child.ChildRemoved, invalidate, connections)
    end
    entry.childConnections[child] = connections
end


function Cache:_refreshChildWatchers(entry)
    for _, connections in pairs(entry.childConnections) do disconnectAll(connections) end
    entry.childConnections = {}
    local prototype = entry.prototype
    if prototype:IsA("Model") then
        for _, child in ipairs(prototype:GetChildren()) do self:_watchChild(entry, child) end
    end
end


function Cache:_invalidateEntry(entry, notifyName)
    if not entry or self.prototypeEntries[entry.prototype] ~= entry then return end
    entry.dirty = true
    entry.metadata = nil
    entry.snapshot = nil
    entry.contracts = {}
    entry.variantResults = {}
    entry.retries = 0
    entry.retryAt = 0
    if notifyName ~= false then
        self:_notify(entry.name)
        entry.generation = self.nameGeneration[entry.name] or (entry.generation + 1)
    end
    self:_refreshChildWatchers(entry)
end


function Cache:_watchPrototype(prototype)
    if self.prototypeEntries[prototype] then return self.prototypeEntries[prototype] end
    local entry = {
        prototype = prototype,
        name = prototype.Name,
        generation = self.nameGeneration[prototype.Name] or 0,
        dirty = true,
        status = "incomplete",
        metadata = nil,
        snapshot = nil,
        contracts = {},
        variantResults = {},
        retries = 0,
        retryAt = 0,
        connections = {},
        childConnections = {},
    }
    self.prototypeEntries[prototype] = entry
    connect(prototype:GetPropertyChangedSignal("Name"), function()
        local oldName = entry.name
        entry.name = prototype.Name
        self:_invalidateEntry(entry, false)
        self:_rebuildMap(true)
        if oldName == entry.name then
            self:_notify(entry.name)
            entry.generation = self.nameGeneration[entry.name] or entry.generation
        end
    end, entry.connections)
    connect(prototype.ChildAdded, function()
        self:_invalidateEntry(entry)
    end, entry.connections)
    connect(prototype.ChildRemoved, function()
        self:_invalidateEntry(entry)
    end, entry.connections)
    for _, attribute in ipairs(RELEVANT_ATTRIBUTES) do
        connect(prototype:GetAttributeChangedSignal(attribute), function()
            self:_invalidateEntry(entry)
        end, entry.connections)
    end
    if prototype:IsA("BasePart") then
        connect(prototype:GetPropertyChangedSignal("Size"), function() self:_invalidateEntry(entry) end, entry.connections)
        connect(prototype:GetPropertyChangedSignal("CFrame"), function() self:_invalidateEntry(entry) end, entry.connections)
        if prototype:IsA("MeshPart") then
            connect(prototype:GetPropertyChangedSignal("MeshId"), function() self:_invalidateEntry(entry) end, entry.connections)
        end
    end
    self:_refreshChildWatchers(entry)
    return entry
end


function Cache:_attachFolder(folder)
    if self.folder == folder then return end
    local known = {}
    for name in pairs(self.knownNames) do known[name] = true end
    for name in pairs(self.byName) do known[name] = true end
    self:_detachFolder()
    self.folder = folder
    self.folderGeneration = self.folderGeneration + 1
    self.folderRetryCount = 0
    self.folderRetryAt = 0
    if folder then
        if folder:IsA("Folder") then
            connect(folder.ChildAdded, function(child)
                self:_watchPrototype(child)
                self:_rebuildMap(true)
            end, self.folderConnections)
            connect(folder.ChildRemoved, function(child)
                local entry = self.prototypeEntries[child]
                if entry then self:_detachEntry(entry) end
                self:_rebuildMap(true)
            end, self.folderConnections)
            connect(folder:GetAttributeChangedSignal("Ready"), function()
                self.folderReady = folder:GetAttribute("Ready") == true
                self.folderRetryCount = 0
                self.folderRetryAt = 0
                self:_notifyAll(false)
            end, self.folderConnections)
            for _, child in ipairs(folder:GetChildren()) do self:_watchPrototype(child) end
            self.folderReady = folder:GetAttribute("Ready") == true
            self:_rebuildMap(false)
        else
            self.folderReady = false
        end
    end
    for name in pairs(known) do self.knownNames[name] = true end
    self:_notifyAll(true)
end


function Cache:_refreshEntry(entry)
    local prototype = entry.prototype
    self.stats.prototypeRefreshes = self.stats.prototypeRefreshes + 1
    entry.dirty = false
    entry.contracts = {}
    entry.variantResults = {}
    entry.snapshot = nil
    entry.metadata = nil
    entry.status = "invalid"
    entry.retryAt = 0
    local snapshot = {kind = nil, children = {}, childrenByName = {}, duplicateNames = {}, childCount = 0}
    if prototype:IsA("MeshPart") then
        snapshot.kind = "meshpart"
        snapshot.sourceName = prototype:GetAttribute("Game1LodSourceName") or prototype.Name
        snapshot.sourceFrame = prototype:GetAttribute("Game1LodPublishedPivot")
        snapshot.status = "ready"
        snapshot.count = 1
        entry.snapshot = snapshot
        entry.status = "ready"
        local metadata, reason = nil, nil
        if self.assembly and self.assembly.BuildMetadata then
            local ok, result, detail = pcall(self.assembly.BuildMetadata, prototype)
            if ok then metadata, reason = result, detail else reason = "invalid" end
        end
        if metadata then
            metadata.generation = entry.generation
            entry.metadata = freezeMetadata(metadata)
        elseif reason == "incomplete" then
            entry.status = "incomplete"
            entry.retryAt = self.clock() + RETRY_SECONDS
        else
            entry.status = "invalid"
        end
        return
    end
    if not prototype:IsA("Model") then
        entry.snapshot = snapshot
        entry.status = "invalid"
        return
    end
    snapshot.kind = "model"
    local children = prototype:GetChildren()
    snapshot.childCount = #children
    local invalidChild = false
    for _, child in ipairs(children) do
        table.insert(snapshot.children, child)
        if not child:IsA("MeshPart") then invalidChild = true end
        if snapshot.childrenByName[child.Name] then
            snapshot.duplicateNames[child.Name] = true
        else
            snapshot.childrenByName[child.Name] = child
        end
    end
    snapshot.expectedCount = prototype:GetAttribute("Game1LodVisualCount")
    snapshot.sourceFrame = prototype:GetAttribute("Game1LodPublishedPivot")
    snapshot.invalidChild = invalidChild
    snapshot.status = "incomplete"
    if invalidChild then
        snapshot.status = "invalid"
    elseif snapshot.expectedCount ~= nil and (type(snapshot.expectedCount) ~= "number"
        or snapshot.expectedCount < 2 or snapshot.expectedCount > 64
        or snapshot.expectedCount ~= math.floor(snapshot.expectedCount)) then
        snapshot.status = "invalid"
    elseif snapshot.expectedCount ~= nil and snapshot.childCount > snapshot.expectedCount then
        snapshot.status = "invalid"
    elseif snapshot.expectedCount ~= nil and snapshot.childCount == snapshot.expectedCount
        and isCFrame(snapshot.sourceFrame) then
        snapshot.status = "ready"
    end
    entry.snapshot = snapshot
    entry.status = snapshot.status
    if snapshot.status == "ready" then
        local metadata, reason = nil, nil
        if self.assembly and self.assembly.BuildMetadata then
            local ok, result, detail = pcall(self.assembly.BuildMetadata, prototype)
            if ok then metadata, reason = result, detail else reason = "invalid" end
        end
        if metadata then
            metadata.generation = entry.generation
            entry.metadata = freezeMetadata(metadata)
        else
            if reason == "incomplete" then entry.status = "incomplete" else entry.status = "invalid" end
        end
    end
    if entry.status == "incomplete" then entry.retryAt = self.clock() + RETRY_SECONDS end
end


function Cache:_retryIncomplete(entry)
    if entry.status ~= "incomplete" or entry.retries >= MAX_RETRIES then return end
    local now = self.clock()
    if now < entry.retryAt then return end
    entry.retries = entry.retries + 1
    entry.retryAt = now + RETRY_SECONDS
    entry.dirty = true
end


function Cache:_retryMissing(name)
    if not self.folder or not self.folder:IsA("Folder") or self.folderReady == true then return end
    local now = self.clock()
    if self.folderRetryCount >= MAX_RETRIES or now < self.folderRetryAt then return end
    self.folderRetryCount = self.folderRetryCount + 1
    self.folderRetryAt = now + RETRY_SECONDS
    self.stats.retryScans = self.stats.retryScans + 1
    self:_rebuildMap(true)
end


function Cache:_validateComponents(entry, components, contractKey)
    local snapshot = entry.snapshot
    if not snapshot or snapshot.kind ~= "model" then return "invalid", nil end
    local signature = tostring(contractKey or componentSignature(components))
    local key = "FULL\31" .. signature
    local cached = entry.contracts[key]
    local retryCount = 0
    if cached and cached.generation == entry.generation then
        local now = self.clock()
        if cached.status ~= "incomplete" or cached.retries >= MAX_RETRIES or now < cached.retryAt then
            return cached.status, cached.metadata
        end
        retryCount = cached.retries + 1
    end
    entry.contracts[key] = nil
    self.stats.contractChecks = self.stats.contractChecks + 1
    local expected = {}
    local duplicateExpected = false
    for _, component in ipairs(components or {}) do
        local name = tostring(component.name or "")
        if name == "" or expected[name] then duplicateExpected = true end
        expected[name] = true
    end
    local expectedCount = countMap(expected)
    local status = "ready"
    if snapshot.invalidChild then
        status = "invalid"
    elseif duplicateExpected then
        status = "invalid"
    elseif snapshot.childCount < expectedCount then
        status = "incomplete"
    elseif snapshot.childCount > expectedCount then
        status = "invalid"
    elseif next(snapshot.duplicateNames) ~= nil then
        status = "invalid"
    else
        for name in pairs(expected) do
            local child = snapshot.childrenByName[name]
            if not child then status = "incomplete"; break end
            if not child:IsA("MeshPart") then status = "invalid"; break end
        end
    end
    local metadata = nil
    if status == "ready" then
        metadata = freezeMetadata({prototype = entry.prototype, kind = "composite", count = expectedCount,
            childrenByName = snapshot.childrenByName, generation = entry.generation,
            sourceFrame = snapshot.sourceFrame})
    end
    local retryAt = 0
    if status == "incomplete" then retryAt = self.clock() + RETRY_SECONDS end
    entry.contracts[key] = {generation = entry.generation, status = status, metadata = metadata,
        retries = retryCount, retryAt = retryAt}
    return status, metadata
end


function Cache:Resolve(name, variant, components, contractKey)
    self.knownNames[name] = true
    local folder = self.folder
    if not folder then return "missing", nil, nil, self.nameGeneration[name] or 0 end
    if not folder:IsA("Folder") then return "invalid", nil, nil, self.nameGeneration[name] or 0 end
    local prototype = self.byName[name]
    if not prototype then
        self:_retryMissing(name)
        prototype = self.byName[name]
        if not prototype then return "missing", nil, nil, self.nameGeneration[name] or 0 end
    end
    local entry = self.prototypeEntries[prototype] or self:_watchPrototype(prototype)
    if entry.dirty then self:_refreshEntry(entry) end
    if not (variant == "FULL" and components) then
        self:_retryIncomplete(entry)
        if entry.dirty then self:_refreshEntry(entry) end
    end
    if variant == "FULL" and components then
        local status, metadata = self:_validateComponents(entry, components, contractKey)
        return status, prototype, metadata, entry.generation
    end
    local cachedVariant = entry.variantResults[variant]
    if cachedVariant and cachedVariant.generation == entry.generation then
        return cachedVariant.status, prototype, cachedVariant.metadata, entry.generation
    end
    local status, metadata = entry.status, nil
    if variant == "FULL" and not prototype:IsA("MeshPart") then
        status = "invalid"
    elseif entry.status == "ready" and entry.metadata then
        status, metadata = "ready", entry.metadata
    end
    entry.variantResults[variant] = {generation = entry.generation, status = status, metadata = metadata}
    return status, prototype, metadata, entry.generation
end


function Cache:Folder()
    return self.folder
end


function Cache:FolderReady()
    return self.folderReady
end


function Cache:Stats()
    local ready, incomplete, invalid = 0, 0, 0
    for _, entry in pairs(self.prototypeEntries) do
        if entry.status == "ready" then ready = ready + 1
        elseif entry.status == "incomplete" then incomplete = incomplete + 1
        else invalid = invalid + 1 end
    end
    return {prototypeRefreshes = self.stats.prototypeRefreshes,
        contractChecks = self.stats.contractChecks, retryScans = self.stats.retryScans,
        ready = ready, incomplete = incomplete, invalid = invalid,
        folderGeneration = self.folderGeneration, folderReady = self.folderReady}
end


function Cache:Destroy()
    self:_detachFolder()
    disconnectAll(self.rootConnections)
    for child, connections in pairs(self.rootChildConnections) do disconnectAll(connections) end
    self.rootChildConnections = {}
    self.listeners = {}
    self.knownNames = {}
end


if table.freeze then return table.freeze(Cache) end
return Cache
