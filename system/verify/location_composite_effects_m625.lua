-- Exercise the production event owner against a small Instance/signal model.
-- Not a claim about Roblox engine replication or deferred signal timing.
local Effects = dofile('src/client/world/LocationCompositeEffects.luau')
local Capture = dofile('src/client/world/LodDiagnostics.luau')
local connections, deferred, pending = 0, false, {}
local function flush()
    while #pending > 0 do
        local batch = pending; pending = {}
        for _, fn in ipairs(batch) do fn() end
    end
end
local function signal()
    local s = {listeners={}}
    function s:Connect(fn)
        local c = {active=true}
        self.listeners[c] = fn; connections = connections+1
        function c:Disconnect()
            if not self.active then return end
            self.active=false; s.listeners[self]=nil; connections=connections-1
        end
        return c
    end
    function s:Fire(...)
        local args = {...}
        local copy = {}; for c, fn in pairs(self.listeners) do copy[c]=fn end
        for c, fn in pairs(copy) do
            local call = function() if c.active then fn(table.unpack(args)) end end
            if deferred then pending[#pending+1]=call else call() end
        end
    end
    return s
end
local Node = {}
local mt = {__index=function(o,k) if k=='Enabled' then return o.enabled end return Node[k] end,
    __newindex=function(o,k,v)
        if k=='Enabled' then
            if o.enabled~=v then o.enabled=v; o.enabledChanged:Fire() end
        else rawset(o,k,v) end
    end}
local function node(class,name,enabled)
    return setmetatable({class=class,Name=name,enabled=enabled,children={},
        ChildAdded=signal(),ChildRemoved=signal(),DescendantAdded=signal(),DescendantRemoving=signal(),enabledChanged=signal()},mt)
end
function Node:IsA(class) return self.class==class or (class=='Light' and self.class=='PointLight') end
function Node:IsDescendantOf(parent)
    local p=self.Parent
    while p do if p==parent then return true end; p=p.Parent end
    return false
end
function Node:FindFirstChild(name)
    for _, child in ipairs(self.children) do if child.Name==name then return child end end
end
function Node:GetDescendants()
    local result={}
    for _, child in ipairs(self.children) do
        result[#result+1]=child
        for _, sub in ipairs(child:GetDescendants()) do result[#result+1]=sub end
    end
    return result
end
function Node:GetPropertyChangedSignal(property) assert(property=='Enabled'); return self.enabledChanged end
local function subtree(child)
    local list={child}; for _, sub in ipairs(child:GetDescendants()) do list[#list+1]=sub end; return list
end
local function add(parent, child)
    assert(not child.Parent); child.Parent=parent; parent.children[#parent.children+1]=child
    parent.ChildAdded:Fire(child)
    local p=parent; local list=subtree(child)
    while p do for _, obj in ipairs(list) do p.DescendantAdded:Fire(obj) end; p=p.Parent end
    return child
end
local function remove(child)
    local parent=assert(child.Parent); local p=parent; local list=subtree(child)
    while p do for _, obj in ipairs(list) do p.DescendantRemoving:Fire(obj) end; p=p.Parent end
    for i,v in ipairs(parent.children) do if v==child then table.remove(parent.children,i); break end end
    child.Parent=nil; parent.ChildRemoved:Fire(child)
end
local function scenario(useDeferred)
    deferred=useDeferred
    local workspace=node('Workspace','Workspace')
    local folder=add(workspace,node('Folder','Locations'))
    local root=add(folder,node('Model','Lantern1'))
    local proxy=add(root,node('Part','proxy'))
    local light=add(proxy,node('PointLight','light',true))
    local off=add(proxy,node('Fire','off',false))
    local record={modelPath={'Locations','Lantern1'},actual='UNLOADED'}
    local far={modelPath={'Locations','Late'},actual='UNLOADED'}
    local records={record,far}
    for i=1,100 do records[#records+1]={modelPath={'Locations','Missing'..i},actual='UNLOADED'} end
    local diagnostics=Capture.new(); diagnostics:Start({})
    local effects=Effects.new(workspace,records,diagnostics); flush()
    assert(not light.Enabled and not off.Enabled)
    -- Shared prefix: missing 100 roots do not allocate per-placement connections.
    assert(connections==8,connections) -- workspace+folder, root, 2 hidden effects
    local initial=diagnostics.counts.compositeDiscoveryVisits
    local initialPath=diagnostics.counts.compositePathEvents
    for i=1,100 do add(folder,node('Model','Unrelated'..i)) end; flush()
    assert(diagnostics.counts.compositeDiscoveryVisits==initial and diagnostics.counts.compositePathEvents==initialPath)
    local smoke=add(proxy,node('Smoke','late smoke',true)); flush(); assert(not smoke.Enabled)
    local late=add(folder,node('Model','Late')); local sparks=add(late,node('Sparkles','spark',true)); flush(); assert(not sparks.Enabled)
    local cloned=add(root,node('Folder','__Game1RuntimeVisuals'))
    local localEffect=add(cloned,node('Fire','local',true)); flush(); assert(localEffect.Enabled)
    -- Desired changes and failed work do not change actual visibility.
    record.desired='FULL'; effects:ActualChanged(record); flush(); assert(not light.Enabled)
    record.part=cloned; record.actual='FULL'; effects:ActualChanged(record); flush()
    assert(light.Enabled and smoke.Enabled and not off.Enabled and not sparks.Enabled)
    light.Enabled=false; off.Enabled=true; flush()
    local reduced=add(workspace,node('Folder','LOD1')); record.actual='LOD1'; record.part=reduced
    effects:ActualChanged(record); flush(); assert(not light.Enabled and off.Enabled and smoke.Enabled)
    record.actual='UNLOADED'; record.part=nil; effects:ActualChanged(record); flush()
    assert(not light.Enabled and not off.Enabled and not smoke.Enabled)
    -- Observable external enabling stays hidden and is restored next time.
    light.Enabled=true; flush(); assert(not light.Enabled)
    record.actual='LOD1'; record.part=reduced; effects:ActualChanged(record); flush()
    assert(light.Enabled and off.Enabled and smoke.Enabled)
    -- Late effect on already visible reduced geometry is not enabled by LOD.
    local beam=add(root,node('Beam','beam',false)); flush(); assert(not beam.Enabled)
    record.actual='UNLOADED'; record.part=nil; effects:ActualChanged(record); flush()
    remove(smoke); flush(); assert(smoke.Enabled and not light.Enabled)
    smoke.Enabled=false; flush(); assert(not smoke.Enabled)
    -- Ancestor streaming loss releases all root/effect subscriptions; stream in
    -- under the same path discovers new objects, including distant roots.
    remove(folder); flush(); assert(light.Enabled and off.Enabled and sparks.Enabled)
    assert(connections==2,connections)
    local newFolder=add(workspace,node('Folder','Locations'))
    local newRoot=add(newFolder,node('Model','Lantern1'))
    local newLight=add(newRoot,node('PointLight','new',true)); flush(); assert(not newLight.Enabled)
    record.actual='FULL'; record.part=cloned; effects:ActualChanged(record); flush(); assert(not newLight.Enabled)
    record.part=add(newRoot,node('Folder','__Game1RuntimeVisuals')); effects:ActualChanged(record); flush(); assert(newLight.Enabled)
    -- Native root removal and replacement at same path with independent LOD1.
    record.actual='LOD1'; record.part=reduced; effects:ActualChanged(record); flush()
    remove(newRoot); flush(); local third=add(newFolder,node('Model','Lantern1'))
    local thirdLight=add(third,node('Trail','trail',true)); flush(); assert(thirdLight.Enabled)
    record.actual='UNLOADED'; record.part=nil; effects:ActualChanged(record); flush(); assert(not thirdLight.Enabled)
    -- Stop restores original state and removes every subscription, including
    -- a deferred external true event not yet delivered.
    thirdLight.Enabled=true; effects:Destroy(); flush(); assert(thirdLight.Enabled)
    assert(connections==0,connections)
    effects:Destroy(); assert(connections==0)
    local nextEffect=add(third,node('ParticleEmitter','after stop',true)); flush(); assert(nextEffect.Enabled)
    -- Counters are event-only and the removed periodic key is absent.
    assert(diagnostics.counts.compositeVisits==nil)
    assert(diagnostics.counts.compositeRootChanges>0 and diagnostics.counts.compositeEffectWrites>0)
end
scenario(false); scenario(true)
print('M625 composite effects: immediate/deferred signals, 100 missing roots, late descendants, actual LOD, stream-in/out, restore and teardown PASS')
