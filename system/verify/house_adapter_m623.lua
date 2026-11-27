-- Exercise the actual adapter with mocked Roblox services/instances. Only
-- Luau-specific expressions are adapted to Lua 5.3; scheduler logic is real.
local Job=dofile('src/client/world/LodAssemblyJob.luau')
local Requests=dofile('src/client/world/HouseMeshRequests.luau')
local Queue=dofile('src/client/world/LodTransitionQueue.luau')
local Work=dofile('src/client/world/LodRuntimeWork.luau')
local sourceFile=assert(io.open('src/client/world/HouseVisualAdapter.luau'))
local source=sourceFile:read('*a'); sourceFile:close()
local function replace(old,new)
    local i,j=source:find(old,1,true); assert(i,old); source=source:sub(1,i-1)..new..source:sub(j+1)
end
replace('if visual.spec.moving then Enum.CollisionFidelity.Default else Enum.CollisionFidelity.Box','(visual.spec.moving and Enum.CollisionFidelity.Default or Enum.CollisionFidelity.Box)')
replace('if config.mode == "lod1" and spec.lod1ModelAssetId ~= "" then "lod1" else "full"','(config.mode == "lod1" and spec.lod1ModelAssetId ~= "" and "lod1" or "full")')
replace('self.errors += 1','self.errors = self.errors + 1')
replace('visual.generation += 1','visual.generation = visual.generation + 1')
replace('if transition.variant == "LOD1" then "__LOD1" else ""','transition.variant == "LOD1" and "__LOD1" or ""')
replace('if part then transition.variant else "UNLOADED"','(part and transition.variant or "UNLOADED")')
replace('if part then transition.prototype else nil','(part and transition.prototype or nil)')
replace('if part and transition.metadata then transition.metadata.generation else nil','(part and transition.metadata and transition.metadata.generation or nil)')
table.freeze=table.freeze or function(t) return t end
local function node(kind)
    local p={kind=kind,children={},Color='blue',Material='Wood',CFrame='authored',destroyed=false}
    function p:IsA(k) return self.kind==k end
    function p:FindFirstChild(k) return self.children[k] end
    function p:IsDescendantOf(root) return self.Parent==root or (self.Parent and self.Parent:IsDescendantOf(root)) or false end
    function p:Destroy() assert(not self.destroyed); self.destroyed=true; self.Parent=nil end
    function p:Clone() return node(self.kind) end
    return p
end
local workspace=node('Workspace')
local root=node('Model'); workspace.children.house=root; root.Parent=workspace
local proxy=node('Part'); root.children.door=proxy; proxy.Parent=root; proxy.CFrame='closed'
local tasks, binds, logs, loaded = {}, {}, {}, {}
local insert={CreateMeshPartAsync=function() local part=node('MeshPart'); loaded[#loaded+1]=part; return part end}
local ray={Bind=function(p,m) binds[p]=m end,Unbind=function(p,m) if binds[p]==m then binds[p]=nil end end}
local reject=false
local appearance={Apply=function(part,spec) part.applied=spec; return not reject end}
local chain={}; function chain:WaitForChild(k) return self end
local storage={}; function storage:WaitForChild(k) return chain end
local services={InsertService=insert, Workspace=workspace, ReplicatedStorage=storage}
game={GetService=function(_,name) return services[name] end}
script={Parent={WaitForChild=function(_,name) return name end}}
require=function(name) return ({[chain]=appearance,DoorInteractionRaycast=ray,LodAssemblyJob=Job,HouseMeshRequests=Requests})[name] end
Instance={new=node}; Enum={CollisionFidelity={Default=1,Box=2},RenderFidelity={Performance=1}}
task={spawn=function(fn) tasks[#tasks+1]=fn end}; warn=function(msg) logs[#logs+1]=msg end
local now=0; os.clock=function() return now end
local Adapter=assert(load(source))()
local prototype=node('MeshPart'); local generation=1; local status='ready'
local cache={ConnectChanged=function(_,fn) return {Disconnect=function() end} end,
    Resolve=function() return status, status=='ready' and prototype or nil, {generation=generation} end,
    FolderReady=function() return true end}
local adapter=Adapter.new({placements={}},cache,10,{})
local visual={house=true,slug='test',path={'house'},spec={name='door',path={'door'},moving=true,meshId='123',mode='material',material='Wood',color='red',alpha=0.2},worldSize='scaled',worldFrame='authored',generation=0,retryAt=0,actual='FULL',desired='LOD1',prototypeDirty=true,templateName='lod'}
local old=node('MeshPart'); old.Parent=adapter.folder; visual.part=old; visual.boundProxy=proxy; binds[proxy]=old
adapter.records={visual}; adapter.moving[visual]=true
local q=Queue.new(function() end); q:Begin({})
local work=Work.new()
adapter:Observe(visual,'FULL',q)
local entry=q.entries[visual]; assert(entry.variant=='LOD1')
local job=assert(adapter:Prepare(entry)); job:Advance(1); assert(job.state=='building' and old.Parent==adapter.folder)
job:Advance(12); assert(job.state=='ready' and not job.bundle.Parent and old.Parent==adapter.folder)
-- Old proxy streams out before commit. A new proxy must not inherit stale binding.
local previousProxy=proxy; previousProxy.Parent=nil; proxy=node('Part'); proxy.Parent=root; proxy.CFrame='open'; root.children.door=proxy
assert(not adapter:Valid(entry,job)); assert(not adapter:Commit(entry,job,work))
work.active={job=job}; work:Cancel(); work:Cleanup(8); assert(job.bundle.destroyed)
adapter:FollowMoving(); assert(binds[previousProxy]==nil and binds[proxy]==old and old.CFrame=='open')
job=assert(adapter:Prepare(entry)); job:Advance(12)
assert(adapter:Commit(entry,job,work)); q:Remove(visual)
assert(visual.actual=='LOD1' and visual.part~=old and visual.part.Parent==adapter.folder and old.Parent==nil)
assert(binds[proxy]==visual.part and visual.part.applied.alpha==0.2 and visual.part.Size=='scaled')
work:Cleanup(8); assert(old.destroyed)
-- Native stream-out hides moving visual without stale raycast, stream-in rebinds.
local lod=visual.part; root.children.door=nil; proxy.Parent=nil; adapter:FollowMoving()
assert(not lod.Parent and binds[proxy]==nil)
proxy=node('Part'); proxy.Parent=root; root.children.door=proxy; proxy.Color='green'; proxy.Material='Metal'; proxy.CFrame='moved'
adapter:FollowMoving(); assert(lod.Parent==adapter.folder and binds[proxy]==lod and lod.CFrame=='moved' and lod.Color=='green' and lod.Material=='Metal')
-- FULL fetch is detached and cannot remove the previous LOD. A failed appearance
-- also leaves the previous representation and binding intact.
visual.desired='FULL'; adapter:Observe(visual,'LOD1',q); entry=q.entries[visual]
assert(not adapter:Prepare(entry)); assert(#tasks==1 and lod.Parent==adapter.folder)
table.remove(tasks,1)(); assert(not loaded[1].Parent and visual.part==lod)
job=assert(adapter:Prepare(entry)); reject=true; job:Advance(12); assert(job.state=='failed'); adapter:Failed(entry,job.problem,false)
work.active={job=job}; work:Cancel(); work:Cleanup(8); assert(loaded[1].destroyed and visual.part==lod and binds[proxy]==lod)
assert(not adapter:Prepare(entry)); assert(#tasks==0)
now=15; reject=false; assert(not adapter:Prepare(entry)); table.remove(tasks,1)(); job=assert(adapter:Prepare(entry)); job:Advance(12)
assert(adapter:Commit(entry,job,work)); q:Remove(visual); work:Cleanup(8)
assert(visual.actual=='FULL' and visual.part==loaded[2] and lod.destroyed and binds[proxy]==loaded[2])
-- A missing preferred prototype preserves FULL; readiness later replaces it.
visual.desired='LOD1'; status='missing'; adapter:Observe(visual,'FULL',q); assert(not q.entries[visual] and visual.part==loaded[2])
status='ready'; generation=2; visual.prototypeDirty=true; adapter:Observe(visual,'LOD1',q)
entry=q.entries[visual]; job=assert(adapter:Prepare(entry)); job:Advance(12); assert(adapter:Commit(entry,job,work)); q:Remove(visual); work:Cleanup(8)
assert(visual.actualPrototypeGeneration==2 and visual.actual=='LOD1')
-- Stale same-tier prototype generation is replaced atomically as well.
generation=3; visual.prototypeDirty=true; visual.prototypeEpoch=1; adapter:Observe(visual,'LOD1',q)
entry=q.entries[visual]; assert(entry.force); job=assert(adapter:Prepare(entry)); job:Advance(12); assert(adapter:Commit(entry,job,work)); q:Remove(visual); work:Cleanup(8)
assert(visual.actualPrototypeGeneration==3)
visual.desired='UNLOADED'; adapter:Observe(visual,'LOD1',q); assert(adapter:Commit(q.entries[visual],nil,work))
assert(not visual.part and next(adapter.moving)==nil and binds[proxy]==nil); work:Cleanup(8); adapter:Destroy()
print('M623 house adapter atomic transitions, appearance, proxy identity and raycast lifecycle PASS')
