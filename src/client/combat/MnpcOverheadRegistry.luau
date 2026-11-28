-- Identity and FULL readiness only. No GUI/HP subscriptions.
local Visibility = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("MnpcLocalVisibility"))
local Registry = {}
Registry.__index = Registry
local ATTRIBUTES = {Game1MonsterRuntime=true, Game1NpcRuntime=true, MonsterSlug=true, NpcSlug=true,
    LifeState=true, Game1MnpcKind=true, Game1MnpcRigReady=true, Game1MnpcDemandStage=true, Game1MnpcLocalLod=true}
local FOLDERS = {Monsters="Monster", NPCs="NPC"}
function Registry.new(workspace, changed)
    return setmetatable({workspace=workspace, changed=changed, records={}, ready={}, readyMonsters={}, folders={}, connections={}, epoch=0}, Registry)
end
local function disconnect(connections)
    for _, connection in ipairs(connections) do connection:Disconnect() end
    table.clear(connections)
end
function Registry:_refresh(record)
    local model = record.model
    local monster = record.kind == "Monster"
    local anchor = model:FindFirstChild("RootCollider")
    local rig = model:FindFirstChild("ImportedRig")
    local rigReady = model:GetAttribute("Game1MnpcRigReady")
    local demand = model:GetAttribute("Game1MnpcDemandStage")
    local ready = model.Parent == record.folder and model:GetAttribute("LifeState") == "Alive"
        and model:GetAttribute(monster and "Game1MonsterRuntime" or "Game1NpcRuntime") == true
        and type(model:GetAttribute(monster and "MonsterSlug" or "NpcSlug")) == "string"
        and Visibility.Full(model) and anchor and anchor:IsA("BasePart")
        and (demand == nil or demand == "full")
        and ((rigReady == nil and model:GetAttribute("Game1MnpcKind") == nil) or (rigReady == true and rig and rig:IsA("Model") and rig:FindFirstChildWhichIsA("MeshPart", true)))
    if not ready then anchor, rig = nil, nil end
    if record.anchor == anchor and record.rig == rig then return end
    record.anchor, record.rig = anchor, rig
    self.ready[model] = anchor and record or nil
    self.readyMonsters[model] = monster and anchor and record or nil
    self.changed(model) -- release obsolete lease immediately; new eligibility on next common tick
end
function Registry:_add(model, kind, folder)
    if not self.folders[kind] or self.folders[kind].folder ~= folder then return end
    if not model:IsA("Model") or model.Parent ~= folder or self.records[model] then return end
    local record = {model=model, kind=kind, folder=folder, connections={}}
    self.records[model] = record
    local function refresh()
        if self.records[model] == record then self:_refresh(record) end
    end
    table.insert(record.connections, model.AttributeChanged:Connect(function(attribute)
        if ATTRIBUTES[attribute] then refresh() end
    end))
    table.insert(record.connections, model.ChildAdded:Connect(refresh))
    table.insert(record.connections, model.ChildRemoved:Connect(refresh))
    -- A streaming ImportedRig can arrive before its first MeshPart. Only observe
    -- geometry additions/removals to recover readiness; no per-frame bounds walk.
    table.insert(record.connections, model.DescendantAdded:Connect(function(child)
        if not child:IsA("MeshPart") or self.records[model] ~= record then return end
        if not record.anchor then
            refresh()
        elseif record.rig and child:IsDescendantOf(record.rig) then
            -- Replication can deliver further meshes after FULL becomes ready.
            -- Coalesce geometry changes; only an active view needs new bounds.
            record.offsetDirty = true
        end
    end))
    table.insert(record.connections, model.DescendantRemoving:Connect(function(child)
        if child == record.anchor or child == record.rig or (child:IsA("MeshPart") and record.rig and child:IsDescendantOf(record.rig)) then
            if self.records[model] ~= record then return end
            -- DescendantRemoving fires before parent changes. Invalidate now;
            -- refresh after the tree mutation, guarding the record generation.
            record.anchor, record.rig = nil, nil
            self.ready[model], self.readyMonsters[model] = nil, nil
            self.changed(model)
            task.defer(refresh)
        end
    end))
    refresh()
end
function Registry:_remove(model)
    local record = self.records[model]
    if not record then return end
    self.records[model], self.ready[model], self.readyMonsters[model] = nil, nil, nil
    disconnect(record.connections)
    self.changed(model)
end
function Registry:_unwatch(kind)
    local state = self.folders[kind]
    if not state then return end
    self.folders[kind] = nil
    disconnect(state.connections)
    for model, record in pairs(self.records) do
        if record.folder == state.folder then self:_remove(model) end
    end
end
function Registry:_watch(folder, kind)
    self:_unwatch(kind)
    local state = {folder=folder, connections={}}
    self.folders[kind] = state
    table.insert(state.connections, folder.ChildAdded:Connect(function(model)
        if self.folders[kind] == state then self:_add(model, kind, folder) end
    end))
    table.insert(state.connections, folder.ChildRemoved:Connect(function(model)
        if self.folders[kind] == state and model.Parent ~= folder and self.records[model] and self.records[model].folder == folder then self:_remove(model) end
    end))
    for _, model in ipairs(folder:GetChildren()) do self:_add(model, kind, folder) end
end
function Registry:Start()
    if #self.connections > 0 then return end
    self.epoch = self.epoch + 1
    local epoch = self.epoch
    for name, kind in pairs(FOLDERS) do
        local folder = self.workspace:FindFirstChild(name)
        if folder and folder:IsA("Folder") then self:_watch(folder, kind) end
    end
    table.insert(self.connections, self.workspace.ChildAdded:Connect(function(folder)
        if self.epoch ~= epoch then return end
        local kind = FOLDERS[folder.Name]
        if kind and folder:IsA("Folder") and folder.Parent == self.workspace then self:_watch(folder, kind) end
    end))
    table.insert(self.connections, self.workspace.ChildRemoved:Connect(function(folder)
        if self.epoch ~= epoch or folder.Parent == self.workspace then return end
        for kind, state in pairs(self.folders) do
            if state.folder == folder then self:_unwatch(kind) end
        end
    end))
end
function Registry:Stop()
    self.epoch = self.epoch + 1
    disconnect(self.connections)
    for kind in pairs(self.folders) do self:_unwatch(kind) end
end
return table.freeze(Registry)
