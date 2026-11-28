table.freeze = function(t) return t end
local rootPath = arg[1]
local Policy = dofile(rootPath .. '/src/shared/world/MnpcLodPolicy.luau')
local Visibility = dofile(rootPath .. '/src/client/actor/MnpcLocalVisibility.luau')
local p = {enabled=true,full=100,hide=200,hysteresis=10}
assert(Policy.Valid(p))
assert(Policy.Key('Monster','same') ~= Policy.Key('NPC','same'))
for _, test in ipairs({{0,nil,'FULL'},{100,nil,'LOD1'},{200,nil,'UNLOADED'},
    {109,'FULL','FULL'},{110,'FULL','LOD1'},{91,'LOD1','LOD1'},{90,'LOD1','FULL'},
    {209,'LOD1','LOD1'},{210,'LOD1','UNLOADED'},{191,'UNLOADED','UNLOADED'},
    {190,'UNLOADED','LOD1'},{0,'UNLOADED','FULL'},{500,'FULL','UNLOADED'}}) do
    assert(Policy.Resolve(test[1],test[2],p,false)==test[3])
end
assert(Policy.Resolve(1000,nil,p,true)=='FULL')
assert(not Policy.Valid({enabled=true,full=100,hide=105,hysteresis=10}))
local v = {LocalTransparencyModifier=.3}; local a,b={},{}
Visibility.Set(v,a,true); Visibility.Set(v,b,true); Visibility.Set(v,a,false)
assert(v.LocalTransparencyModifier==1)
Visibility.Set(v,b,false); assert(v.LocalTransparencyModifier==.3)
local function signal()
    local s={listeners={}}
    function s:Connect(fn) self.listeners[fn]=true; return {Disconnect=function() self.listeners[fn]=nil end} end
    function s:Fire(x) for fn in pairs(self.listeners) do fn(x) end end
    return s
end
local vectorMT={__sub=function(a,b) return {Magnitude=math.abs(a.x-b.x)} end}
Vector3={new=function(x,y,z) return setmetatable({x=x,Magnitude=math.sqrt(x*x+y*y+z*z)},vectorMT) end}
local function vec(x) return Vector3.new(x,0,0) end
local frame={__mul=function(a,b) return a end};CFrame={new=function() return setmetatable({},frame) end}
Color3={fromRGB=function(r,g,b) return {r,g,b} end}
Enum={Material={SmoothPlastic='smooth'}}
local function instance(class,name)
    local i={class=class,Name=name,children={},attrs={},ChildAdded=signal(),ChildRemoved=signal(),Parent=true,Position=vec(0),CFrame=CFrame.new(),Size=Vector3.new(2,4,2)}
    function i:IsA(c) return c==self.class or (c=='BasePart' and (self.class=='Part' or self.class=='MeshPart')) end
    function i:GetChildren() local out={};for _,c in pairs(self.children) do out[#out+1]=c end;return out end
    function i:FindFirstChild(n) return self.children[n] end
    function i:FindFirstChildWhichIsA(c) for _,o in pairs(self.children) do if o:IsA(c) then return o end end end
    function i:FindFirstChildOfClass(c) return self:FindFirstChildWhichIsA(c) end
    function i:IsDescendantOf(parent) return self.Parent ~= nil end
    function i:GetAttribute(k) return self.attrs[k] end
    function i:SetAttribute(k,v) self.attrs[k]=v end
    function i:Destroy() self.Parent=nil;self.destroyed=true end
    function i:Clone() return instance(self.class,self.Name) end
    return i
end
Instance={new=function(c) return instance(c,c) end}
local function actor(kind,slug,x)
    local a=instance('Model',slug);a.attrs={Game1MnpcKind=kind,LifeState='Alive',Game1MnpcRigReady=true,Game1MnpcFullModelId='101'}
    a.attrs[kind=='NPC' and 'NpcSlug' or 'MonsterSlug']=slug
    local r=instance('Part','HumanoidRootPart');r.Position=vec(x)
    local c=instance('Part','RootCollider');c.Position=vec(x)
    local rig=instance('Model','ImportedRig');rig.children.mesh=instance('MeshPart','mesh')
    a.children={HumanoidRootPart=r,RootCollider=c,ImportedRig=rig};return a
end
local player={UserId=42,Character=actor('Monster','self',0)}
-- Real custom ControllerManager avatar has no HumanoidRootPart or Humanoid.
player.Character.attrs.CustomCharacter=true
player.Character.children.HumanoidRootPart=nil
player.Character.children.NavigationRoot=instance('Part','NavigationRoot')
player.Character.PrimaryPart=player.Character.children.RootCollider
local ws=instance('Workspace','Workspace')
local m,n=actor('Monster','same',130),actor('NPC','same',140)
local monsters,npcs=instance('Folder','Monsters'),instance('Folder','NPCs')
monsters.children.m=m;npcs.children.n=n;ws.children={Monsters=monsters,NPCs=npcs}
local spec={meshId='50',imageId='60',size={1,2,3},rootCFrame={0,0,0,1,0,0,0,1,0,0,0,1},fullModelId='101'}
local registry={defaults=p,actors={['npc:same']={profile=p,asset=spec}}}
local prototype=nil
local cache={Get=function(_,key,asset) if asset then return prototype end end,YieldOutside=function() end,Destroy=function() end}
local mask={new=function(model) model.hidden=true;return {Destroy=function() model.hidden=false end} end}
local folder={WaitForChild=function(_,key) if key=='world' or key=='combat' or key=='character' or key=='Game1Shared' then return folder end return key end}
-- Lua local scope does not extend into its own initializer.
folder.WaitForChild=function(_,key) if key=='world' or key=='combat' or key=='character' or key=='Game1Shared' then return folder end return key end
script={Parent=folder}
game={GetService=function(_,k) if k=='Players' then return {LocalPlayer=player} elseif k=='Workspace' then return ws else return folder end end}
-- Run the actual shared resolver, removing only Luau syntax for the Lua CLI.
local f=assert(io.open(rootPath..'/src/shared/character/CharacterSpatialRoot.luau','r'))
local rootSource=f:read('*a');f:close()
rootSource=rootSource:gsub('player: Player','player'):gsub('%): boolean',')'):gsub('%): BasePart%?',')')
rootSource=rootSource:gsub('return if root and root:IsA%("BasePart"%) then root else nil','if root and root:IsA("BasePart") then return root end; return nil')
local SpatialRoot=assert(load(rootSource))()
local original=require
require=function(key) return ({CharacterSpatialRoot=SpatialRoot,MnpcLodRegistry=registry,MnpcLodPolicy=Policy,AttackConfig={MaxAimDistance=420,Range=7},MnpcLodMask=mask,MnpcLodPrototypeCache={new=function() return cache end}})[key] or original(key) end
math.clamp=function(v,lo,hi) return math.min(hi,math.max(lo,v)) end
local Controller=dofile(rootPath..'/src/client/actor/MnpcLodController.luau')
local ctl=Controller.new()
local custom=player.Character; player.Character=nil
ctl:Step(.25);assert(ctl:Describe().counts.UNTRACKED==2 and ctl:Describe().waitingForPlayerRoot)
player.Character=custom;ctl:Step(.25)
assert(m.hidden and n.hidden and ctl.records[m].part.Name=='MNPC_LOD1_RED_DUMMY' and ctl.records[n].part.Name=='MNPC_LOD1_RED_DUMMY')
assert(ctl:Describe().playerRoot=='RootCollider')
local savedCollider=custom.children.RootCollider
custom.children.RootCollider=nil
ctl:Step(.25);assert(ctl:Describe().playerRoot=='NavigationRoot' and ctl:Describe().counts.LOD1==2)
custom.children.RootCollider=savedCollider
ctl:Step(.25);assert(ctl:Describe().playerRoot=='RootCollider')
assert(ctl:Describe().counts.LOD1==2 and ctl:Describe().rows[1].reason=='distance')
assert(not ctl.records[m].part.CanCollide and not ctl.records[m].part.CanQuery and not ctl.records[m].part.CanTouch)
player.Character.attrs.AttackRadius=200;ctl:Step(.25);assert(ctl:Describe().counts.FULL==2 and ctl:Describe().rows[1].reason=='attack reach')
player.Character.attrs.AttackRadius=nil;m.attrs.Game1GameplayTestOwner=42;ctl:Step(.25);assert(ctl:Describe().rows[1].reason=='gameplay test' and not m.hidden)
m.attrs.Game1GameplayTestOwner=nil;player.UserId=0;m.attrs.MonsterTargetUserId=0;ctl:Step(.25);assert(m.hidden and ctl:Describe().rows[1].reason=='distance');player.UserId=42
prototype=instance('MeshPart','proto');ctl:Step(.25);assert(ctl.records[n].part.Name=='MNPC_LOD1')
player.Character.children.RootCollider.Position=vec(130);ctl:Step(.25)
assert(not m.hidden and not n.hidden and not ctl.records[m].part and m.attrs.Game1MnpcLocalLod=='FULL')
player.Character.children.RootCollider.Position=vec(500);ctl:Step(.25)
assert(m.hidden and n.hidden and not ctl.records[m].part and m.attrs.Game1MnpcLocalLod=='UNLOADED')
player.Character.children.RootCollider.Position=vec(130);m.attrs.Game1MnpcRigReady=false;ctl:Step(.25)
assert(m.hidden and ctl.records[m].part.Name=='MNPC_LOD1_RED_DUMMY')
m.attrs.Game1MnpcRigReady=true;m.attrs.Game1MnpcDemandStage="preparing";ctl:Step(.25);assert(m.hidden and ctl.records[m].part)
m.attrs.Game1MnpcDemandStage="full";ctl:Step(.25);assert(not m.hidden and not ctl.records[m].part)
player.Character.children.RootCollider.Position=vec(0);ctl:Step(.25);monsters.ChildRemoved:Fire(m)
assert(not ctl.records[m] and not m.hidden and not m.attrs.Game1MnpcLocalLod)
-- Replacement with a standard Humanoid, and temporarily absent player root.
player.Character=nil;ctl:Step(.25);assert(ctl:Describe().waitingForPlayerRoot and ctl:Describe().rows[1].reason=='waiting for player root')
player.Character=actor('Monster','standard',0)
local humanoid=instance('Humanoid','Humanoid');humanoid.Health=100;player.Character.children.Humanoid=humanoid
ctl:Step(.25);assert(ctl:Describe().playerRoot=='HumanoidRootPart' and ctl:Describe().counts.LOD1==1)
ctl:Destroy();assert(not n.hidden and not n.attrs.Game1MnpcLocalLod)
print('M638 policy, visibility ownership, mixed dynamic actor dummy/real/FULL/unload and cleanup oracle passed')
