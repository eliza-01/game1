-- Execute the real graph algorithm outside Roblox with a minimal Vector3/Instance stub.
-- Only graph math is covered; no physics, engine spatial query, or Humanoid simulation.
local path=arg[1]
local V={}
V.__index=function(a,k)
    if k=='Magnitude' then return math.sqrt(a.X*a.X+a.Y*a.Y+a.Z*a.Z) end
    return V[k]
end
local function v(x,y,z) return setmetatable({X=x,Y=y,Z=z},V) end
V.__add=function(a,b) return v(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
V.__sub=function(a,b) return v(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
V.__mul=function(a,b) return v(a.X*b,a.Y*b,a.Z*b) end
function V:Dot(b) return self.X*b.X+self.Y*b.Y+self.Z*b.Z end
math.round=function(x) return math.floor(x+.5) end
math.clamp=function(x,a,b) return math.max(a,math.min(x,b)) end
table.freeze=function(t) return t end
warn=print
local function inst(class,name,children,value)
    return {Name=name,Value=value,IsA=function(_,c) return c==class end,GetChildren=function() return children or {} end}
end
local function route(name,points)
    local children={}
    for i,p in ipairs(points) do children[i]=inst('Vector3Value',tostring(i),nil,p) end
    return inst('Folder',name,children)
end
local function loadGraph(routes)
    local folder=inst('Folder','Game1RescueRoutes',routes)
    game={GetService=function() return {FindFirstChild=function() return folder end} end}
    script={Parent={WaitForChild=function() return 'config' end}}
    package.loaded.config={searchDistance=40}
    return assert(loadfile(path))()
end
local function close(a,b) assert(math.abs(a-b)<1e-5,tostring(a)..' != '..tostring(b)) end
-- Interior projections: a route need not enter/exit at vertices.
local g=loadGraph({route('one',{v(0,0,0),v(20,0,0)})})
local p=g.Find(v(3,0,-2),v(17,0,-2),function() return true end)
close(p.cost,18); close(p.points[1].X,3); close(p.points[#p.points].X,17)
-- Two levels above each other: nearby in XZ isn't sufficient.
g=loadGraph({route('upper',{v(0,8,0),v(20,8,0)})})
assert(g.Find(v(1,0,0),v(18,8,0),function() return true end)==nil)
-- Square around a wall with explicit junction to a stair branch. Only the
-- designated outside/inside connectors are admitted (simulated blocked LOS).
g=loadGraph({route('ring',{v(0,0,0),v(20,0,0),v(20,0,20),v(0,0,20),v(0,0,0)}),
    route('stairs',{v(20,0,20),v(20,3,17),v(20,6,14),v(10,6,14)})})
local start,goal=v(5,0,-2),v(10,6,12)
local function connect(a,b)
    if (a-start).Magnitude<.01 then return math.abs(b.Z)<.01 and b.Y==0 and b.X==5 end
    if (b-goal).Magnitude<.01 then return b.X==10 and b.Y==6 and b.Z==14 or a.X==10 and a.Y==6 and a.Z==14 end
    return false
end
p=g.Find(start,goal,connect)
assert(p and #p.points>=4)
close(p.cost,2+15+20+2*math.sqrt(18)+10+2)
-- Rejected connector/forbidden junction => no route instead of crossing walls.
assert(g.Find(start,goal,connect,function(q) return not(q.X==20 and q.Z==20) end)==nil)
assert(g.Find(start,goal,function() return false end)==nil)
print('OK rescue graph: projections, 3D floors, closed ring, stairs, blocked connectors, forbidden junction')
-- Exit height outranks total length. The lower route is a cheap shortcut,
-- but the upper branch reaches the target's exact foot level.
local s,t=v(0,0,0),v(12,4,0)
g=loadGraph({route('lower',{s,v(12,0,0)}),route('upper',{s,v(0,4,18),v(12,4,18)})})
local function startOnly(a,b)
    if (a-s).Magnitude<.001 then return (b-s).Magnitude<.001 end
    return true
end
p=g.Find(s,t,startOnly)
assert(p); close(p.exitHeightDelta,0); close(p.exitDistance,18)
close(p.cost,math.sqrt(340)+12+18)
-- At equal height, closer exit wins even if the route itself is longer.
g=loadGraph({route('near',{s,v(0,0,25),v(12,0,25),v(12,0,1)}),route('short',{s,v(8,0,0)})})
t=v(12,0,0)
p=g.Find(s,t,startOnly)
assert(p); close(p.exitDistance,1); close(p.cost,62)
-- Disconnected perfect exit must not suppress the reachable lower exit;
-- the old hard 2-stud exit cutoff is no longer applied.
t=v(12,4,0)
g=loadGraph({route('lower',{s,v(12,0,0)}),route('disconnected',{v(10,4,0),v(14,4,0)})})
p=g.Find(s,t,startOnly)
assert(p); close(p.exitHeightDelta,4); close(p.cost,16)
-- A sloped edge must select the target height instead of closest 3D point.
g=loadGraph({route('slope',{s,v(20,10,0)})})
t=v(2,5,0)
p=g.Find(s,t,startOnly)
assert(p); close(p.points[#p.points].X,10); close(p.points[#p.points].Y,5)
close(p.exitDistance,8); close(p.cost,math.sqrt(125)+8)
-- If the highest-ranked connector fails, use the next reachable exit.
g=loadGraph({route('lower',{s,v(12,0,0)}),route('upper',{s,v(0,4,18),v(12,4,18)})})
t=v(12,4,0)
p=g.Find(s,t,function(a,b)
    if (a-s).Magnitude<.001 then return (b-s).Magnitude<.001 end
    return a.Y<3
end)
assert(p); close(p.exitHeightDelta,4); close(p.cost,16)
print('OK M569: height-first, distance-second, reachable fallback, slope projection, full path cost')

-- M574: the exit can be farther than the 40-stud entry search radius.
s,t=v(0,0,0),v(90,8,0)
g=loadGraph({route('far',{s,v(20,0,0),v(20,8,0),v(30,8,0)})})
p=g.Find(s,t,function(a,b) return (a-s).Magnitude<.001 and (b-s).Magnitude<.001 or a.Y==8 end)
assert(p);close(p.exitHeightDelta,0);close(p.exitDistance,60);close(p.cost,98)
-- More than eight rejected nearby entry projections cannot starve a valid
-- farther entry; a blocked projection can fall back to an endpoint.
local many={}
for i=1,12 do many[i]=route('blocked'..i,{v(i,0,1),v(i,0,2)}) end
many[#many+1]=route('valid',{v(20,0,0),v(30,0,0),v(30,8,0),v(40,8,0)})
g=loadGraph(many);s,t=v(0,0,0),v(40,8,1)
local stats
p,stats=g.Find(s,t,function(a,b) return (a-s).Magnitude<.001 and b.X==20 and b.Z==0 end,nil,function(a,b) return a.Y==8 end)
assert(p and stats.entryChecks>8);close(p.exitHeightDelta,0);close(p.exitDistance,1)
g=loadGraph({route('endpoint',{v(0,0,0),v(20,0,0)})})
s,t=v(5,0,-2),v(20,0,2)
p=g.Find(s,t,function(a,b) return b.X==0 end,nil,function(a,b) return a.X==20 end)
assert(p);close(p.points[1].X,0);close(p.points[#p.points].X,20)
-- More than eight rejected high-ranked exit connectors cannot starve the
-- next reachable one. Disconnected candidates do not consume exit casts.
local chain={v(0,0,0),v(0,8,0)}
for i=1,20 do chain[#chain+1]=v(i,8,0) end
g=loadGraph({route('chain',chain),route('disconnected',{v(100,8,0),v(110,8,0)})})
s,t=v(0,0,0),v(100,8,1)
p,stats=g.Find(s,t,function(a,b) return (b-s).Magnitude<.001 end,nil,function(a,b) assert(a.X<100,'disconnected exit queried');return a.X==1 and a.Y==8 end)
assert(p and stats.exitChecks>8);close(p.points[#p.points].X,1)
print('OK M574: remote exit, rejected entries/exits, endpoint fallback, reachable-only search')
