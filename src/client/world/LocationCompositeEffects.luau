-- Client visibility of authored effects in compiled Location composite roots.
-- One path-prefix subscription per resident parent; no Workspace descendant
-- listener, distance policy, timer or effect reconstruction.
local Effects = {}
Effects.__index = Effects

local function count(self, key)
    if self.diagnostics and self.diagnostics.enabled then self.diagnostics:Add(key) end
end

local function visualEffect(obj)
    return obj:IsA("Light") or obj:IsA("Fire") or obj:IsA("Smoke")
        or obj:IsA("Sparkles") or obj:IsA("ParticleEmitter")
        or obj:IsA("Beam") or obj:IsA("Trail")
end

local function write(self, obj, enabled)
    if obj.Enabled == enabled then return end
    obj.Enabled = enabled
    count(self, "compositeEffectWrites")
end

local function restore(self, obj, entry)
    if entry.connection then
        entry.connection:Disconnect()
        entry.connection = nil
    end
    if entry.saved ~= nil then
        -- A deferred external true notification may not have run yet.
        local saved = entry.saved or obj.Enabled
        entry.saved = nil
        write(self, obj, saved)
    end
end

local function hide(self, state, obj, entry)
    if entry.saved ~= nil then return end
    -- Capture the current state, not a permanent default from initial bind.
    entry.saved = obj.Enabled
    entry.connection = obj:GetPropertyChangedSignal("Enabled"):Connect(function()
        -- Handles both immediate and deferred property signals. Our own false
        -- writes are no-ops here; observable external true writes stay hidden.
        if state.entries[obj] ~= entry or entry.saved == nil or not obj.Enabled then return end
        entry.saved = true
        count(self, "compositeEffectEvents")
        write(self, obj, false)
    end)
    write(self, obj, false)
end

local function addEffect(self, state, obj)
    if not visualEffect(obj) or state.entries[obj] or not obj:IsDescendantOf(state.root) then return end
    -- Runtime FULL bundles are client-owned geometry, not authored effects.
    local parent = obj.Parent
    while parent and parent ~= state.root do
        if parent.Name == "__Game1RuntimeVisuals" then return end
        parent = parent.Parent
    end
    local entry = {}
    state.entries[obj] = entry
    count(self, "compositeEffectEvents")
    if not state.active then hide(self, state, obj, entry) end
end

local function removeEffect(self, state, obj)
    local entry = state.entries[obj]
    if not entry then return end
    state.entries[obj] = nil
    restore(self, obj, entry)
    count(self, "compositeEffectEvents")
end

local function unbindRoot(self, state)
    if not state.root then return end
    state.added:Disconnect()
    state.removing:Disconnect()
    state.root = nil
    for obj, entry in pairs(state.entries) do
        state.entries[obj] = nil
        restore(self, obj, entry)
    end
end

local function activeFor(record, root)
    if record.actual == "UNLOADED" or not record.part then return false end
    -- A FULL bundle follows its technical root; a replacement root must not
    -- light up until its own FULL geometry is committed. Reduced geometry is
    -- independent of the technical root and may already be visible.
    return record.actual ~= "FULL" or record.part:IsDescendantOf(root)
end

local function bindRoot(self, state, root)
    if state.root == root then return end
    unbindRoot(self, state)
    count(self, "compositeRootChanges")
    if not root then return end
    state.root = root
    state.active = activeFor(state.record, root)
    state.added = root.DescendantAdded:Connect(function(obj)
        if state.root == root then addEffect(self, state, obj) end
    end)
    state.removing = root.DescendantRemoving:Connect(function(obj)
        if state.root == root then removeEffect(self, state, obj) end
    end)
    -- One initial discovery per streamed-in root. Afterwards only changed
    -- descendants and the cached effect set on actual LOD transitions.
    for _, obj in ipairs(root:GetDescendants()) do
        count(self, "compositeDiscoveryVisits")
        addEffect(self, state, obj)
    end
end

local bindNode
local function unbindNode(self, node)
    if not node.instance then return end
    if node.added then node.added:Disconnect(); node.added = nil end
    if node.removed then node.removed:Disconnect(); node.removed = nil end
    node.instance = nil
    for _, child in pairs(node.children) do unbindNode(self, child) end
    for _, state in ipairs(node.states) do bindRoot(self, state, nil) end
end

bindNode = function(self, node, instance)
    if node.instance == instance then return end
    unbindNode(self, node)
    if not instance then return end
    node.instance = instance
    for _, state in ipairs(node.states) do
        if instance:IsA("Model") then bindRoot(self, state, instance) end
    end
    if next(node.children) == nil then return end
    -- Manifest paths use immutable compiled names. Filter direct child events
    -- by the shared prefix trie: unrelated objects do not resolve any path.
    local function changed(child)
        if node.instance ~= instance then return end
        local branch = node.children[child.Name]
        if not branch then return end
        count(self, "compositePathEvents")
        bindNode(self, branch, instance:FindFirstChild(child.Name))
    end
    node.added = instance.ChildAdded:Connect(changed)
    node.removed = instance.ChildRemoved:Connect(changed)
    for name, branch in pairs(node.children) do
        bindNode(self, branch, instance:FindFirstChild(name))
    end
end

local function newNode()
    return {children={}, states={}}
end

function Effects.new(workspace, records, diagnostics)
    local self = setmetatable({tree=newNode(), states={}, diagnostics=diagnostics}, Effects)
    for _, record in ipairs(records) do
        local node = self.tree
        for _, name in ipairs(record.modelPath) do
            if not node.children[name] then node.children[name] = newNode() end
            node = node.children[name]
        end
        local state = {record=record, entries={}, active=false}
        self.states[record] = state
        node.states[#node.states+1] = state
    end
    bindNode(self, self.tree, workspace)
    return self
end

function Effects:ActualChanged(record)
    local state = self.states[record]
    if not state or not state.root then return end
    local active = activeFor(record, state.root)
    if state.active == active then return end
    state.active = active
    for obj, entry in pairs(state.entries) do
        count(self, "compositeEffectVisits")
        if active then restore(self, obj, entry) else hide(self, state, obj, entry) end
    end
end

function Effects:Destroy()
    unbindNode(self, self.tree)
    self.states = {}
    self.tree = newNode()
end

return Effects
