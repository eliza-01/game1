-- Actual shared M639 lifecycle with deterministic Lua doubles (no native engine).
table.freeze = function(t) return t end
math.clamp = function(v, lo, hi) return math.max(lo, math.min(hi, v)) end
local now, enabled, queries = 0, false, 0
local players, queued = {}, {}
local tree = {WaitForChild=function(self,key) if key=='Game1Shared' or key=='world' or key=='combat' or key=='balance' or key=='dev' then return self end return key end}
game = {GetService=function(_, key)
    if key == "ReplicatedStorage" then return tree end
    error("Unexpected service: " .. key)
end}
script = {Parent={WaitForChild=function(_, key) return key end}}
local policy = dofile(arg[2])
local profiles = {defaults={enabled=true,full=100,hide=200,hysteresis=10},actors={['npc:disabled']={profile={enabled=false,full=100,hide=200,hysteresis=10}},['npc:long']={profile={enabled=true,full=300,hide=500,hysteresis=10}}}}
local originalRequire = require
require = function(key)
    if key == "GameOptions" then return {MnpcDemandEnabled=function() return enabled end} end
    if key == "PlayerSpatialIndex" then return {Query=function(_,radius) queries=queries+1; return players end} end
    if key == "ActorTargetRoot" then return {Get=function(character) return character end} end
    if key == "MnpcLodPolicy" then return policy end
    if key == "MnpcLodRegistry" then return profiles end
    if key == "AttackConfig" then return {Range=7,MaxAimDistance=420} end
    if key == "Balance" then return {Weapons={{radius=40}}} end
    if key == "PublishedDebugAccess" then return {ServerEnabled=function() return arg[3]=='debug' end} end
    return originalRequire(key)
end
local vectorMT={__sub=function(a,b) return {X=a.X-b.X,Z=a.Z-b.Z} end}
local function vec(x,z) return setmetatable({X=x,Z=z},vectorMT) end
local function player(x,z) return {Character={Position=vec(x,z)}} end
os.clock=function() return now end
warn=function() end
task={spawn=function(f) table.insert(queued,f) end}
local function dispatch() local f=table.remove(queued,1); assert(f); f() end
local Demand = dofile(arg[1])
local function actor(kind,x,slug,initial,template)
    local attrs={LifeState="Alive", Damageable=not initial, HP=77,Game1MnpcKind=kind}
    attrs[kind=='NPC' and 'NpcSlug' or 'MonsterSlug']=slug or 'same'
    local model={Parent=true, GetAttribute=function(_, k) return attrs[k] end,SetAttribute=function(_, k,v) attrs[k]=v end,
        FindFirstChild=function(_,k) assert(k=='RootCollider'); return {Size={Magnitude=10}} end}
    local a={model=model,root={Position=vec(x,0)},state="Idle",kind=kind}
    local data={release=0,acquire=0,ready=true,allow=true,fail=false}
    if initial then assert(Demand.CanSpawnShell(model,a.root,template)) end
    Demand.Register(model,{
        canRelease=function() return data.allow end,
        release=function() data.release=data.release+1; attrs.Damageable=false; return true end,
        acquire=function(alive) data.acquire=data.acquire+1; if data.cancel then data.cancel(); assert(not alive()) end; return not data.fail end,
        ready=function() return data.ready end,
    },initial,template)
    return a,attrs,data
end
local function step(a,t) now=t; Demand.Step(a,now) end
local template={}
local m,ma,md=actor("Monster",0,nil,false,template)
local n,na,nd=actor("NPC",100)
step(m,0); step(n,0); Demand.Pump(); assert(queries==0 and md.release==0 and nd.release==0)
enabled=true
-- Debug controls can change reach to 420 at any moment. Test both modes.
local edge = arg[3]=='debug' and 510 or 185
players={player(edge,0),player(5000,0)}
step(m,1); step(m,8); assert(md.release==0)
players={player(10000,0)}
assert(not Demand.CanSpawnShell(m.model,m.root,template))
step(m,9); step(n,9); step(m,13.9); assert(md.release==0)
n.attacking=true; step(n,14); assert(nd.release==0)
step(m,14); assert(md.release==1 and ma.Game1MnpcDemandStage=="shell" and ma.HP==77)
assert(Demand.CanSpawnShell(m.model,m.root,template))
assert(not Demand.CanSpawnShell(m.model,m.root,{}))
local s,sa,sd=actor('Monster',200,nil,true,template)
assert(sa.Game1MnpcDemandStage=='shell' and not sa.Damageable and sd.release==0)
Demand.Remove(s.model)
n.attacking=false; step(n,16); step(n,21); assert(nd.release==1 and na.Game1MnpcDemandStage=="shell")
-- Nearest wins even if far actor's AI tick arrived first.
players={player(100,0)}; nd.ready=false
step(m,22); step(n,22); Demand.Pump(); assert(#queued==1 and na.Game1MnpcDemandStage=="loading")
dispatch(); step(n,23); step(m,23); Demand.Pump(); assert(#queued==0 and not na.Damageable and na.Game1MnpcDemandStage=='preparing')
nd.ready=true; step(n,24); assert(na.Game1MnpcDemandStage=="full" and na.Damageable)
Demand.Pump(); assert(#queued==1); dispatch(); step(m,25); assert(ma.Damageable and ma.HP==77)
-- Release hysteresis, pinned effects, and disabled switch restores dormant actors.
players={}; ma.ActiveSkillEffects="Bleed"; step(m,26); step(m,32); assert(md.release==1)
ma.ActiveSkillEffects=nil; step(m,33); step(m,38); assert(md.release==2)
enabled=false; step(m,39); Demand.Pump(); dispatch(); step(m,40); assert(ma.Damageable and md.acquire==2)
-- Failed preparation cleanup, retry and ready timeout.
enabled=true; step(m,41); step(m,46); players={player(0,0)}; md.fail=true
step(m,47); Demand.Pump(); dispatch(); assert(ma.Game1MnpcDemandStage=="shell" and not ma.Damageable)
step(m,48); Demand.Pump(); assert(#queued==0); md.fail=false; md.ready=false; step(m,52); Demand.Pump(); dispatch()
step(m,68); assert(ma.Game1MnpcDemandStage=="shell")
step(m,73); Demand.Pump(); md.cancel=function() Demand.Remove(m.model); m.model.Parent=nil end; dispatch()
players={}; step(n,74); step(n,79); players={player(100,0)}; step(n,80); Demand.Pump(); dispatch(); step(n,81)
assert(na.Damageable and na.HP==77)
-- Disabled profile cannot release; authored full distance and monster aggro can extend admission.
local d,da,dd=actor('NPC',0,'disabled'); players={}; step(d,82); step(d,90); assert(dd.release==0)
local l,la,ld=actor('NPC',0,'long'); players={player(355,0)}; step(l,91); step(l,99); assert(ld.release==0)
local a,aa,ad=actor('Monster',0); aa.MonsterAggroRadius=600; players={player(620,0)}; step(a,100); step(a,108); assert(ad.release==0)
print('M639 demand oracle: opt-in, policy, catalog/debug reach, qualified spawn, mixed nearest admission, pin, retry, timeout, cancellation passed')
