-- Execute real pure policy, registry and pool in standalone Lua with signal/Instance doubles.
table.freeze = function(t) return t end
table.clear = function(t) for k in pairs(t) do t[k]=nil end end
warn = function() end
local root = arg[1] .. '/src/client/combat/'
local Policy = dofile(root..'OverheadVisibilityPolicy.luau')
local Pool = dofile(root..'OverheadViewPool.luau')
local function model(attrs) return {attrs=attrs, GetAttribute=function(self,k) return self.attrs[k] end} end
-- Independent M645 oracle of all visible segments (including disabled style and GP).
local count=0
for _,zone in ipairs({false, 1, 7}) do
 for _,owner in ipairs({false,42,99}) do
  for _,group in ipairs({false,true}) do
   for _,same in ipairs({false,true}) do
    for _,inRange in ipairs({false,true}) do
     for _,focus in ipairs({false,true}) do
      for _,aggro in ipairs({false,true}) do
       for _,enabled in ipairs({false,true}) do
        for _,recall in ipairs({false,true}) do
         for _,preview in ipairs({false,true}) do
          local m=model({GameplayTestZone=zone or nil,Game1GameplayTestOwner=owner or nil,GameplayTestKind=group and 'group' or nil,
            MonsterCombatActive=aggro,MonsterTargetUserId=42,MonsterHomeRecalling=recall})
          local c={userId=42,playerZone=same and zone or 9,aimed=focus and m or nil,showAll=preview,hpEnabled=enabled}
          local release=type(zone)=='number' and zone<=6
          local sameZone=release and c.playerZone==zone and owner==42
          local isGroup=group and owner==42
          local engaged=focus or aggro or preview
          local n,h,i
          if isGroup then n=inRange;h=inRange and engaged
          elseif release then n=sameZone and inRange;h=n and engaged
          else n=inRange and engaged and enabled;h=n end
          if owner and not (group or release) then n=false end
          i=sameZone or (isGroup and inRange)
          n,h,i=n and not recall,h and enabled and not recall,i and not recall
          local a,b,d=Policy.Monster(m,c,inRange)
          assert(a==n and b==h and d==i,'monster visibility mismatch')
          count=count+1
         end
        end
       end
      end
     end
    end
   end
  end
 end
end
for _,distance in ipairs({0,49,50,99,100,101}) do
 for _,hp in ipairs({0,99,100}) do
  for _,hostile in ipairs({false,true}) do
   for _,enabled in ipairs({false,true}) do
    local m=model({MaxHP=100,HP=hp,NpcTargetUserId=hostile and 42 or 0,NpcAIState='Attack'})
    local a,b=Policy.Npc(m,{userId=42,nameSq=2500,hpSq=10000,hpEnabled=enabled},distance^2)
    assert(a==(distance<=50) and b==(enabled and distance<=100 and (hp<99.999 or hostile)))
    count=count+1
   end
  end
 end
end
local made,destroyed=0,0
local function factory()
 made=made+1
 local v={}
 function v.Bind(_,owner) assert(not v.owner);v.owner=owner;if owner.fail then error('bind fault') end end
 function v.Unbind() assert(v.owner);v.owner=nil end
 function v.Destroy() v.owner=nil;destroyed=destroyed+1 end
 return v
end
local p=Pool.new(factory,8,5)
local a,b={},{}
local first=p:Acquire(a,{},nil,{},0);assert(first and first.owner==a)
p:Release(a,0);p:Release(a,0);assert(#p.idle==1 and first.owner==nil)
assert(p:Acquire(b,{},nil,{},1)==first and first.owner==b)
p:Release(b,1);p:Expire(5.9);assert(#p.idle==1);p:Expire(6);assert(#p.idle==0 and destroyed==1)
local owners={};for i=1,40 do owners[i]={};assert(p:Acquire(owners[i],{},nil,{},7)) end
for _,o in ipairs(owners) do p:Release(o,7) end
assert(#p.idle==8 and next(p.active)==nil)
assert(p:Acquire({fail=true},{},nil,{},8)==nil and next(p.active)==nil)
p:Clear();assert(#p.idle==0 and made==destroyed)
-- Registry is the actual module; no GUI ever created by registration.
local Vis=dofile(arg[1]..'/src/client/actor/MnpcLocalVisibility.luau')
local node={};node.Parent=node;function node:WaitForChild(k) if k=="actor" then return self end; return k end
script={Parent=node};require=function(k) assert(k=='MnpcLocalVisibility');return Vis end
local deferred={};task={defer=function(fn) deferred[#deferred+1]=fn end}
local function flush() local q=deferred;deferred={};for _,fn in ipairs(q) do fn() end end
local function signal()
 local s={listeners={}}
 function s:Connect(fn) self.listeners[fn]=true;return {Disconnect=function() self.listeners[fn]=nil end} end
 function s:Fire(arg) local copy={};for fn in pairs(self.listeners) do copy[#copy+1]=fn end;for _,fn in ipairs(copy) do fn(arg) end end
 return s
end
local function instance(class,name)
 local o=model({});o.class=class;o.Name=name;o.children={}
 for _,s in ipairs({'ChildAdded','ChildRemoved','AttributeChanged','DescendantAdded','DescendantRemoving'}) do o[s]=signal() end
 function o:IsA(c) return self.class==c or (c=='BasePart' and (self.class=='Part' or self.class=='MeshPart')) end
 function o:FindFirstChild(n) return self.children[n] end
 function o:GetChildren() local list={};for _,x in pairs(self.children) do list[#list+1]=x end;return list end
 function o:FindFirstChildWhichIsA(c,recursive) for _,x in pairs(self.children) do if x:IsA(c) then return x end;if recursive then local found=x:FindFirstChildWhichIsA(c,true);if found then return found end end end end
 function o:FindFirstAncestorOfClass(c) local x=self.Parent;while x do if x:IsA(c) then return x end;x=x.Parent end end
 function o:IsDescendantOf(p) local x=self.Parent;while x do if x==p then return true end;x=x.Parent end;return false end
 function o:SetAttribute(k,v) self.attrs[k]=v;self.AttributeChanged:Fire(k) end
 function o:Add(x) self.children[x.Name]=x;x.Parent=self;self.ChildAdded:Fire(x);local p=self;while p do p.DescendantAdded:Fire(x);p=p.Parent end end
 function o:Remove(x) local p=self;while p do p.DescendantRemoving:Fire(x);p=p.Parent end;self.children[x.Name]=nil;x.Parent=nil;self.ChildRemoved:Fire(x);flush() end
 return o
end
local R=dofile(root..'MnpcOverheadRegistry.luau')
local ws=instance('Workspace','Workspace');local folder=instance('Folder','Monsters');ws:Add(folder)
local r=R.new(ws,function(o) p:Release(o,10) end);r:Start();r:Start()
local m=instance('Model','monster');folder:Add(m);assert(not r.ready[m])
m:SetAttribute('Game1MnpcKind','Monster');m:SetAttribute('Game1MonsterRuntime',true);m:SetAttribute('MonsterSlug','gremlin');m:SetAttribute('LifeState','Alive')
local anchor=instance('Part','RootCollider');m:Add(anchor);assert(not r.ready[m])
local rig=instance('Model','ImportedRig');m:Add(rig);m:SetAttribute('Game1MnpcRigReady',true);assert(not r.ready[m])
local mesh=instance('MeshPart','mesh');rig:Add(mesh);assert(r.ready[m].anchor==anchor)
assert(p:Acquire(m,{},anchor,{},10));local extra=instance('MeshPart','extra');rig:Add(extra);assert(r.ready[m].offsetDirty and p.active[m]);rig:Remove(extra);assert(r.ready[m] and not p.active[m]);assert(p:Acquire(m,{},anchor,{},10));m:SetAttribute('Game1MnpcLocalLod','LOD1');assert(not r.ready[m] and not p.active[m])
m:SetAttribute('Game1MnpcLocalLod','FULL');assert(r.ready[m]);assert(p:Acquire(m,{},anchor,{},11))
m:SetAttribute('Game1MnpcRigReady',false);assert(not r.ready[m] and not p.active[m]);m:SetAttribute('Game1MnpcRigReady',true);assert(r.ready[m]);rig:Remove(mesh);assert(not r.ready[m]);rig:Add(mesh);assert(r.ready[m])
m:Remove(anchor);assert(not r.ready[m]);m:Add(anchor);assert(r.ready[m]);m:SetAttribute('LifeState','Dead');assert(not r.ready[m]);m:SetAttribute('LifeState','Alive');assert(r.ready[m])
folder:Remove(m);assert(not r.records[m]);assert(next(m.AttributeChanged.listeners)==nil)
-- Replaced folder, old signals and deferred callbacks must not own new leases.
folder:Add(m);assert(r.ready[m]);assert(p:Acquire(m,{},anchor,{},12))
ws:Remove(folder);assert(not r.records[m] and not p.active[m]);assert(next(folder.ChildAdded.listeners)==nil)
local replacement=instance('Folder','Monsters');ws:Add(replacement);folder:Remove(m);replacement:Add(m);assert(r.ready[m]);assert(p:Acquire(m,{},anchor,{},13))
local staleRemove=next(replacement.ChildRemoved.listeners);local staleAdd=next(replacement.ChildAdded.listeners)
r:Stop();assert(next(ws.ChildAdded.listeners)==nil and next(r.records)==nil and not p.active[m]);r:Start();assert(r.ready[m]);assert(p:Acquire(m,{},anchor,{},14))
staleRemove(m);staleAdd(instance('Model','stale'));assert(r.ready[m] and p.active[m]);r:Stop();p:Clear()
print('M646 actual policy oracle '..count..' cases; pool and registry lifecycle OK')

-- The actual coordinator (Luau syntax adapted by Python) with actual registry,
-- pool and policies, plus Roblox signal, spatial and view doubles.
if arg[2] then
 local controllerPath=arg[2]
 local function vec(x,y,z)
  return setmetatable({X=x,Y=y,Z=z},{__sub=function(a,b)return vec(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end,
   __mul=function(a,b)return vec(a.X*b,a.Y*b,a.Z*b) end,
   __index={Dot=function(a,b)return a.X*b.X+a.Y*b.Y+a.Z*b.Z end}})
 end
 local workspace=instance('Workspace','Workspace');local monsters=instance('Folder','Monsters');local npcs=instance('Folder','NPCs')
 workspace:Add(monsters);workspace:Add(npcs)
 local player=instance('Player','LocalPlayer');player.UserId=42;player.CharacterAdded=signal();player.CharacterRemoving=signal()
 function player:FindFirstChildOfClass(c)return self:FindFirstChildWhichIsA(c,false) end
 local character=instance('Model','player');character:SetAttribute('LifeState','Alive');character:SetAttribute('HP',100);character:SetAttribute('MaxHP',100)
 local rootPart=instance('Part','RootCollider');rootPart.Position=vec(0,0,0);character:Add(rootPart);player.Character=character
 local playerGui=instance('PlayerGui','PlayerGui');player:Add(playerGui)
 local function spawn(folder,kind,name,x)
  local actor=instance('Model',name);actor:SetAttribute('Game1'..kind..'Runtime',true);actor:SetAttribute(kind..'Slug',name)
  actor:SetAttribute('LifeState','Alive');actor:SetAttribute('HP',100);actor:SetAttribute('MaxHP',100)
  local anchor=instance('Part','RootCollider');anchor.Position=vec(x,0,0)
  function anchor:FindFirstAncestorOfClass(c) if actor:IsA(c) then return actor end end
  actor:Add(anchor);folder:Add(actor);return actor,anchor
 end
 local monster,hitPart=spawn(monsters,'Monster','test',15)
 local distant=spawn(monsters,'Monster','distant',1000)
 local hit=nil;function workspace:Raycast()return hit and {Instance=hit} or nil end
 local views={};local created=0;local offsetRefresh=0
 local function create()
  created=created+1;local v={}
  function v.Bind(parent,owner,anchor) assert(not v.owner);v.parent=parent;v.owner=owner;v.anchor=anchor;views[owner]=v end
  function v.Unbind() if v.owner then views[v.owner]=nil end;v.owner=nil;v.parent=nil;v.anchor=nil end
  function v.Destroy() v.Unbind() end
  function v.IsAttached(gui)return v.parent==gui and v.anchor.Parent==v.owner end
  function v.SetSegments(n,h)v.name=n;v.hp=h end
  function v.SetIcon(i)v.icon=i end
  function v.SetVisible(i)v.name=i;v.hp=i end
  function v.SetMaxDistance(d)v.maxDistance=d end
  function v.ApplyStyle()end
  function v.RefreshVisualOffset()offsetRefresh=offsetRefresh+1 end
  return v
 end
 local profile={nameRadiusStuds=70,healthRadiusStuds=70};local style={monster={enabled=true,maxDistanceStuds=100},self={enabled=true}}
 local changed=signal();local settings={Current=function()return style end,RuntimeDevice=function()return 'desktop' end,
  ShowAllMonsters=function()return false end,IsPreviewing=function()return false end,Changed=function(fn)return changed:Connect(fn)end}
 local run={Heartbeat=signal()};local shared={WaitForChild=function(self,k)if k=='GameOptions' or k=='CharacterSpatialRoot' then return k end;return self end}
 game={GetService=function(_,k)return ({Players={LocalPlayer=player},RunService=run,Workspace=workspace,ReplicatedStorage=shared})[k]end}
 RaycastParams={new=function()return {}end};Enum={RaycastFilterType={Exclude='Exclude'}};math.clamp=function(x,a,b)return math.max(a,math.min(x,b)) end
 local modules={GameOptions={NpcOverheadSettings=function()return profile end},CharacterSpatialRoot={Get=function()return rootPart end},
  HealthBarView={Create=create},HealthUiSettings=settings,CameraController={GetAimRay=function()return vec(0,0,0),vec(1,0,0)end,AutoAimTarget=function()return nil end},
  MnpcOverheadRegistry=R,OverheadVisibilityPolicy=Policy,OverheadViewPool=Pool}
 local scriptNode={};scriptNode.Parent=scriptNode;function scriptNode:WaitForChild(k)if k=='character' then return self end;return k end
 script={Parent=scriptNode};require=function(k)return assert(modules[k],k) end
 modules.SelfOverhead=dofile(root..'SelfOverhead.luau')
 local controller=assert(loadfile(controllerPath))()
 local time=0;local oldClock=os.clock;os.clock=function()return time end
 local function tick(dt)time=time+dt;run.Heartbeat:Fire(dt)end
 controller.Start();controller.Start();assert(created==1 and views[character] and not views[monster] and not views[distant])
 hit=hitPart;tick(.1);assert(views[monster] and views[monster].hp and created==2)
 local original=views[monster];monster:SetAttribute('Game1MnpcLocalLod','LOD1');assert(not views[monster]);tick(.1)
 monster:SetAttribute('Game1MnpcLocalLod','FULL');tick(.1);assert(views[monster]==original)
 local actors={};for i=1,6 do actors[i]=spawn(npcs,'Npc','npc'..i,20+i) end
 local before=created;tick(.1);assert(created-before==4);tick(.1);assert(created-before==6)
 for _,actor in ipairs(actors)do assert(views[actor].name and not views[actor].hp and views[actor].maxDistance==150) end
 actors[1]:SetAttribute('HP',80);tick(.1);assert(views[actors[1]].hp)
 -- A managed FULL rig with several late meshes updates the bound view once.
 monster:SetAttribute('Game1MnpcKind','Monster');local imported=instance('Model','ImportedRig');monster:Add(imported)
 imported:Add(instance('MeshPart','first'));monster:SetAttribute('Game1MnpcRigReady',true);tick(.1)
 local bound=views[monster];assert(bound);local oldOffset=offsetRefresh
 imported:Add(instance('MeshPart','late1'));imported:Add(instance('MeshPart','late2'));tick(.1)
 assert(views[monster]==bound and offsetRefresh==oldOffset+1);tick(.1);assert(offsetRefresh==oldOffset+1)
 -- GUI replacement releases all leases and creates fresh trees for the new owner.
 player:Remove(playerGui);assert(next(views)==nil);local replacementGui=instance('PlayerGui','PlayerGui');player:Add(replacementGui);tick(.1);tick(.1)
 assert(views[monster] and views[monster].parent==replacementGui and views[actors[1]].hp)
 local oldTick=next(run.Heartbeat.listeners);controller.Stop();assert(next(views)==nil and next(run.Heartbeat.listeners)==nil and next(changed.listeners)==nil)
 controller.Start();local newSelf=views[character];oldTick(1);assert(views[character]==newSelf);controller.Stop();assert(next(views)==nil)
 os.clock=oldClock;print('M647 actual coordinator: lazy first focus, FULL rebind, 4/tick, NPC HP, PlayerGui reset, stop/restart OK')
end
