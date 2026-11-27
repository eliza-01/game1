local Statistics = dofile('src/shared/dev/NetworkMotionStatistics.luau')
local function near(a,b) assert(math.abs(a-b)<1e-8, tostring(a)..' ~= '..tostring(b)) end
local constant = Statistics.New()
for i=1,480 do
    local dt = i%2==0 and 1/120 or 1/40
    assert(Statistics.Add(constant,dt,16*dt,16*dt,16))
end
local c = Statistics.Finish(constant)
near(c.physical.mean,16); near(c.render.p05,16); near(c.render.p95,16); near(c.velocity.mean,16)
assert(c.movingStops==0 and c.frames==480)
local pulse=Statistics.New()
for i=1,480 do local dt=1/60; Statistics.Add(pulse,dt,16*dt,(i%2==0 and 8 or 24)*dt,16) end
local p=Statistics.Finish(pulse)
near(p.render.mean,16); near(p.render.p05,8); near(p.render.p95,24); near(p.physical.p95,16)
local server=Statistics.New()
Statistics.Add(server,.05,.8,nil,16)
assert(Statistics.Finish(server).render==nil)
local cap=Statistics.New()
for i=1,Statistics.Limit do Statistics.Add(cap,.001,.016,.016,16) end
assert(not Statistics.Add(cap,.001,.016,.016,16))
assert(Statistics.Finish(cap).capped)
print('network motion statistics: constant speed, uneven dt, pulses, server channel and cap passed')

-- Validate bounded owner summaries and reject invalid or out-of-window values.
local owner = Statistics.Finish(constant)
owner.seconds=8; owner.actualStart=100; owner.actualEnd=108; owner.reason='complete'
local clean=assert(Statistics.ValidateOwner(owner,100))
assert(clean.bins==nil and clean.actualStart==100); near(clean.render.mean,16)
owner.render.p05=0/0; assert(not Statistics.ValidateOwner(owner,100))
owner.render.p05=16; owner.actualStart=99; assert(not Statistics.ValidateOwner(owner,100))
owner.actualStart=100; owner.frames=999999; assert(not Statistics.ValidateOwner(owner,100))
print('owner report validation: bounded fields, invalid numeric data and time window passed')
-- A synthetic slewed server clock must affect window scheduling, not speed.
local clock=0
local vecMT={__sub=function(a,b) return {X=a.X-b.X,Z=a.Z-b.Z} end}
local function vec(x) return setmetatable({X=x,Z=0},vecMT) end
local root={Position=vec(0),AssemblyLinearVelocity=vec(16)}
function root:IsA(name) return name=='BasePart' end
function root:IsDescendantOf() return true end
function root:GetRenderCFrame() return {Position=self.Position} end
local character={FindFirstChild=function(_,name) if name=='NavigationRoot' then return root end end}
root.Parent=character
local env=setmetatable({os={clock=function() return clock end},require=function() return Statistics end,
    script={Parent={WaitForChild=function() return true end}},workspace={}}, {__index=_G})
local Capture=assert(loadfile('src/shared/dev/NetworkMotionCapture.luau','t',env))()
local session=assert(Capture.New({Character=character,Name='Test'},100,true))
assert(not Capture.Step(session,100))
for i=1,480 do
    clock=i/60; root.Position=vec(clock*16)
    Capture.Step(session,100+clock*(1.005))
end
local captured=Capture.Finish(session)
near(captured.physical.mean,16); near(captured.render.p95,16)
print('capture: monotonic elapsed time independent of synchronized clock slew passed')
