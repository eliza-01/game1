-- Execute actual shared demand state machine with deterministic Studio doubles.
table.freeze = function(t) return t end
local now, pilot, studio, queries = 0, false, true, 0
local players, queued = {}, {}
local workspace = {GetAttribute=function(_, key) assert(key == "Game1MnpcDemandPilot"); return pilot end}
game = {GetService=function(_, key)
    if key == "RunService" then return {IsStudio=function() return studio end} end
    assert(key == "Workspace"); return workspace
end}
script = {Parent={WaitForChild=function(_, key) return key end}}
local originalRequire = require
require = function(key)
    if key == "PlayerSpatialIndex" then return {Query=function() queries=queries+1; return players end} end
    if key == "ActorTargetRoot" then return {Get=function(character) return character end} end
    return originalRequire(key)
end
local vectorMT={__sub=function(a,b) return {X=a.X-b.X,Z=a.Z-b.Z} end}
local function vec(x,z) return setmetatable({X=x,Z=z},vectorMT) end
local function player(x,z) return {Character={Position=vec(x,z)}} end
local function advance(t) now=t end
os.clock=function() return now end
warn=function() end
task={spawn=function(f) table.insert(queued,f) end}
local function dispatch() local f=table.remove(queued,1); assert(f); f() end
local Demand = dofile(arg[1])
local function actor(kind,x)
    local attrs={LifeState="Alive", Damageable=true, HP=77}
    local model={Parent=true, GetAttribute=function(_, k) return attrs[k] end,SetAttribute=function(_, k,v) attrs[k]=v end}
    local a={model=model,root={Position=vec(x,0)},state="Idle",kind=kind}
    local data={release=0,acquire=0,ready=true,allow=true,fail=false}
    Demand.Register(model,{
        canRelease=function() return data.allow end,
        release=function() data.release=data.release+1; attrs.Damageable=false; return true end,
        acquire=function(alive) data.acquire=data.acquire+1; if data.cancel then data.cancel(); assert(not alive()) end; return not data.fail end,
        ready=function() return data.ready end,
    })
    return a,attrs,data
end
local m,ma,md=actor("Monster",0)
local n,na,nd=actor("NPC",100)
local function step(a,t) advance(t); Demand.Step(a,now) end
step(m,0); step(n,0); assert(queries==0 and md.release==0 and nd.release==0)
pilot=true
players={player(630,0),player(5000,0)}
step(m,1); step(m,8); assert(md.release==0) -- inside exit, regardless of other distant players
players={player(10000,0)}
step(m,9); step(n,9); step(m,13.9); assert(md.release==0)
n.attacking=true; step(n,15); assert(nd.release==0)
step(m,14); assert(md.release==1 and ma.Game1MnpcDemandStage=="shell" and ma.HP==77)
n.attacking=false; step(n,16); step(n,21); assert(nd.release==1 and na.Game1MnpcDemandStage=="shell")
players={player(0,0)}; md.ready=false
step(m,22); step(n,22); assert(#queued==1 and ma.Game1MnpcDemandStage=="loading")
dispatch(); step(m,23); step(n,23); assert(#queued==0 and not ma.Damageable) -- readiness holds shared slot
md.ready=true; step(m,24); assert(ma.Game1MnpcDemandStage=="full" and ma.Damageable)
step(n,24); assert(#queued==1); dispatch(); step(n,25); assert(na.Damageable and na.HP==77)
-- Release hysteresis, pinned effects, and disabled pilot restores dormant actors.
players={}; ma.ActiveSkillEffects="Bleed"; step(m,26); step(m,32); assert(md.release==1)
ma.ActiveSkillEffects=nil; step(m,33); step(m,38); assert(md.release==2)
pilot=false; step(m,39); dispatch(); step(m,40); assert(ma.Damageable and md.acquire==2)
-- A failed preparation is cleaned and retried only after delay.
pilot=true; step(m,41); step(m,46); players={player(0,0)}; md.fail=true
step(m,47); dispatch(); assert(ma.Game1MnpcDemandStage=="shell" and not ma.Damageable)
step(m,48); assert(#queued==0); md.fail=false; md.ready=false; step(m,52); dispatch()
step(m,68); assert(ma.Game1MnpcDemandStage=="shell")
-- Removal while a request is pending releases the slot after callback returns.
step(m,73); md.cancel=function() Demand.Remove(m.model); m.model.Parent=nil end; dispatch()
-- A second domain can subsequently load: no stale generation may consume admission.
players={}; step(n,74); step(n,79); players={player(100,0)}; step(n,80); dispatch(); step(n,81)
assert(na.Damageable and na.HP==77)
print("M632 demand oracle: shared admission, hysteresis, pin, retry, timeout, cancellation, rollback passed")
