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
local function loadGraph(routes,maxHeightDelta)
    local folder=inst('Folder','Game1RescueRoutes',routes)
    game={GetService=function() return {FindFirstChild=function() return folder end} end}
    local directory=path:match('^(.*[/\\])') or ''
    script={Parent={WaitForChild=function(_,name) return name end}}
    package.loaded.MonsterNavigationConfig={searchDistance=40,routeConnectionHeight=maxHeightDelta or 2}
    for _,name in ipairs({'Segments','Topology','Routes','Queries','Entries','Paths','Exits','Connections','Sampling'}) do
        local module='MonsterRescue'..name
        package.loaded[module]=nil
        package.preload[module]=function() return assert(loadfile(directory..module..'.luau'))() end
    end
    return assert(loadfile(path))()
end
local function close(a,b) assert(math.abs(a-b)<1e-5,tostring(a)..' != '..tostring(b)) end
-- Interior projections: a route need not enter/exit at vertices.
local g=loadGraph({route('one',{v(0,0,0),v(20,0,0)})})
local p=g.Find(v(3,0,-2),v(17,0,-2),function() return true end)
close(p.cost,18); close(p.points[1].X,3); close(p.points[#p.points].X,17)
-- Two levels above each other: connector validation, not height alone, rejects a blocked floor.
g=loadGraph({route('upper',{v(0,8,0),v(20,8,0)})})
assert(g.Find(v(1,0,0),v(18,8,0),function(a,b) return b.Y==a.Y end)==nil)
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
-- M586: nearest authored route to target outranks another route at exact height.
local s,t=v(0,0,0),v(12,4,0)
g=loadGraph({route('lower',{s,v(12,0,0)}),route('upper',{s,v(0,4,8),v(12,4,8)})})
local function startOnly(a,b)
    if (a-s).Magnitude<.001 then return (b-s).Magnitude<.001 end
    return true
end
p=g.Find(s,t,startOnly)
assert(p and p.routeId=="lower"); close(p.exitHeightDelta,4); close(p.exitDistance,4)
close(p.cost,16)
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
-- A sloped edge must select the target height instead of closest 3D point
-- when the height match is within the progress sphere.
g=loadGraph({route('slope',{s,v(20,10,0)})})
t=v(7,5,0)
p=g.Find(s,t,startOnly)
assert(p); close(p.points[#p.points].X,10); close(p.points[#p.points].Y,5)
close(p.exitDistance,3); close(p.cost,math.sqrt(125)+3)
-- If the highest-ranked connector fails, use the next reachable exit.
g=loadGraph({route('lower',{s,v(12,0,0)}),route('upper',{s,v(0,4,18),v(12,4,18)})})
t=v(12,4,0)
p=g.Find(s,t,function(a,b)
    if (a-s).Magnitude<.001 then return (b-s).Magnitude<.001 end
    return a.Z==0
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
assert(p and p.routeId=="valid");close(p.exitHeightDelta,0);close(p.exitDistance,1)
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

-- M588 replaces the former proximity/interior crossing topology. Exact
-- endpoint-to-interior contacts are still valid, and nonzero transfers must
-- pass their own collision test. No authored routes are merged.
s,t=v(0,0,0),v(10,5,10)
local function atStart(a,b) return (b-s).Magnitude<.001 end
local function atGoal(a,b) return (a-t).Magnitude<.001 end
g=loadGraph({route('main',{s,v(20,0,0)}),route('stairs',{v(10,0,0),t})})
p=g.Find(s,t,atStart,nil,atGoal)
assert(p);close(p.cost,10+math.sqrt(125));assert(p.routeId=='stairs' and p.entryRouteId=='main')
s,t=v(5,0,-6),v(15,0,8)
g=loadGraph({route('main',{v(0,0,0),v(20,0,0)}),route('entry',{s,v(5,0,0)}),route('exit',{v(15,0,0),t})})
p=g.Find(s,t,atStart,nil,atGoal);assert(p);close(p.cost,24)
-- An endpoint over 10 studs from the next line connects to its interior.
s,t=v(0,0,0),v(10,0,22)
g=loadGraph({route('main',{s,v(20,0,0)}),route('far',{v(10,0,12),t})})
local transfers={}
p,stats=g.Find(s,t,atStart,nil,atGoal,nil,function(a,b)
    local k=string.format('%g:%g:%g:%g',a.X,a.Z,b.X,b.Z)
    assert(not transfers[k]);transfers[k]=true
    return a.X==10 and b.X==10
end)
assert(p and p.routeId=='far' and p.entryRouteId=='main');close(p.cost,32)
assert(g.Find(s,t,atStart,nil,atGoal,nil,function() return false end)==nil)
assert(g.Find(s,t,atStart,nil,atGoal)==nil)
-- Distinct floors are not passable when the transition callback rejects them.
s,t=v(0,0,0),v(10,8,10)
g=loadGraph({route('main',{s,v(20,0,0)}),route('upstairs',{v(10,8,0),t})})
assert(g.Find(s,t,atStart,nil,atGoal,nil,function(a,b) return a.Y==b.Y end)==nil)
print('OK M588: endpoint projections, gaps over 10, separate route IDs, blocked transfers')

-- M581: a route above the old 2-stud limit is still eligible. The existing
-- connector policy decides whether this is physically accessible.
for _,rise in ipairs({2.58,4.83,5.97}) do
    s,t=v(0,0,0),v(20,rise,0)
    g=loadGraph({route('raised',{v(8,rise,0),t})})
    p,stats=g.Find(s,t,function(a,b) return true end)
    assert(p and stats.entries>0);close(p.points[1].Y,rise)
end
-- M588 coarse scan begins at the projection, then +/-20 arc studs.
-- Once an opening is found, only its next 20 studs toward the goal are refined.
s,t=v(30,0,-2),v(75,0,0)
for _,points in ipairs({{v(0,0,0),v(80,0,0)}, {v(0,0,0),v(12,0,0),v(33,0,0),v(80,0,0)}}) do
    g=loadGraph({route('opening',points)})
    local checks={}
    p,stats=g.Find(s,t,function(a,b)
        checks[#checks+1]=b.X
        return b.X>=50 and b.X<=58
    end,nil,function(a,b) return true end)
    assert(p);close(p.points[1].X,58)
    assert(#checks==5);for i,x in ipairs({30,50,54,58,62}) do close(checks[i],x) end
end
local checked={}
-- Normal success does not run the fallback samples.
p,stats=g.Find(s,t,function() return true end)
assert(p and stats.entryChecks==1)
-- An arbitrarily long edge only samples inside the 40-stud 3D sphere.
s,t=v(0,0,0),v(10000,5,0)
g=loadGraph({route('long',{v(-10000,5,0),t})})
p,stats=g.Find(s,t,function(a,b)
    assert((b-a).Magnitude<=40+1e-6,'entry outside radius')
    return false
end)
assert(not p and stats.entryChecks<=5 and stats.entryChecks>1)
-- Leash/cooldown policy and blocked connectors remain mandatory.
assert(g.Find(s,t,function() error('forbidden point cast') end,function() return false end)==nil)
g=loadGraph({route('outside',{v(0,41,0),v(20,41,0)})})
p,stats=g.Find(s,t,function() error('out-of-radius cast') end)
assert(not p and stats.entryCandidates==0 and stats.entryChecks==0)
print('OK M581: raised entries, slope height match, bounded fallback, dedup, radius and policy')

-- M582: a better height outside the initial foot-to-foot distance must
-- not win, even if its connector is clear. No cast for an invalid exit.
s,t=v(0,0,0),v(12,4,0)
g=loadGraph({route('lower',{s,v(12,0,0)}),route('upper',{s,v(0,4,18),v(12,4,18)})})
p,stats=g.Find(s,t,atStart,nil,function(a,b)
    assert((a-b).Magnitude<=(s-t).Magnitude+1e-6,'exit outside progress sphere')
    return a.Z==0 or a.Y==4
end)
assert(p);close(p.exitHeightDelta,4);close(p.exitDistance,4)
-- A slope crossing the sphere has a feasible interior height optimum,
-- even if its unrestricted height match and far endpoint are outside.
s,t=v(0,0,0),v(2,5,0)
g=loadGraph({route('slope',{s,v(20,10,0)})})
p=g.Find(s,t,atStart,nil,function() return true end)
assert(p);close(p.points[#p.points].X,7.2);close(p.points[#p.points].Y,3.6)
close(p.exitDistance,(s-t).Magnitude)
-- A route can go away from the goal temporarily before a useful exit.
s,t=v(0,0,0),v(12,4,0)
g=loadGraph({route('detour',{s,v(-20,0,0),v(-20,4,20),v(12,4,20),v(12,4,1)})})
p=g.Find(s,t,atStart,nil,function(a,b) return a.X==12 and a.Z==1 end)
assert(p);close(p.exitDistance,1);assert(p.points[2].X==-20)
-- If all exits inside the progress sphere are blocked, reject the route
-- rather than casting to/choosing a farther clear exit.
g=loadGraph({route('away',{v(1,0,0),v(0,4,20),v(12,4,20)})})
p,stats=g.Find(s,t,function() return true end,nil,function(a,b)
    assert((a-b).Magnitude<=(s-t).Magnitude+1e-6)
    return a.Y==4
end)
assert(not p and stats.exitChecks>0)
-- Entire edge outside the progress sphere: no exit casts at all.
s,t=v(0,0,0),v(1,0,0)
g=loadGraph({route('outside',{v(0,0,5),v(20,0,5)})})
p,stats=g.Find(s,t,function() return true end,nil,function() error('far exit queried') end)
assert(not p and stats.entries==0 and stats.exitChecks==0)
print('OK M582: progress sphere, clipped height match, allowed detour, blocked fallback, no far casts')

-- M584: an unobstructed projection wins over a cheaper distant vertex,
-- even when the same straight line is split into many authored segments.
s,t=v(3,0,-2),v(17,0,-2)
for _,points in ipairs({{v(0,0,0),v(20,0,0)}, {v(0,0,0),v(8,0,0),v(12,0,0),v(20,0,0)}}) do
    g=loadGraph({route('continuous',points)})
    p,stats=g.Find(s,t,function() return true end)
    assert(p); close(p.points[1].X,3);close(p.points[#p.points].X,17);close(p.cost,18)
    assert(stats.entryChecks==1)
end
-- If the projection is blocked, another route's accepted entry must not
-- suppress the bounded search for an opening on this particular edge.
s,t=v(4,0,-2),v(18,0,-2)
g=loadGraph({route('near',{v(0,0,0),v(20,0,0)}),route('other',{v(0,3,10),v(20,3,10)})})
p,stats=g.Find(s,t,function(a,b) return b.Z==10 or (b.Z==0 and math.abs(b.X-20)<.01) end,nil,function() return true end)
assert(p);close(p.points[1].X,20);close(p.points[1].Z,0);close(p.points[#p.points].X,18)
-- An unobstructed entry on a slope remains the nearest 3D projection, not
-- the height match; the exit still gives priority to the target foot height.
s,t=v(5,0,-2),v(15,8,2)
g=loadGraph({route('slope',{v(0,0,0),v(20,10,0)})})
p,stats=g.Find(s,t,function() return true end)
assert(p);close(p.points[1].X,4);close(p.points[1].Y,2);close(p.points[#p.points].X,16);close(p.exitHeightDelta,0)
assert(stats.entryChecks==1)
-- Exit projection and interval boundaries blocked: a clear interior opening
-- can still be selected. The same connector is never cast twice.
s,t=v(0,0,0),v(20,0,0)
g=loadGraph({route('exit opening',{s,t})})
checked={}
p,stats=g.Find(s,t,function() return true end,nil,function(a,b)
    local k=string.format('%.5f:%.5f:%.5f',a.X,a.Y,a.Z)
    assert(not checked[k],'exit connector repeated');checked[k]=true
    assert((a-b).Magnitude<=(s-t).Magnitude+1e-6)
    return math.abs(a.X-12)<.01
end)
assert(p and stats.exitChecks>2);close(p.points[#p.points].X,12);close(p.cost,20)
print('OK M584: nearest entry, subdivision, per-edge fallback, slope, bounded interior exit')

-- M585: diagnostic observer must not alter the plan, statistics or the number
-- and order of callbacks. Route IDs survive graph splitting/deduplication.
s,t=v(3,0,-2),v(17,0,-2)
g=loadGraph({route('near',{v(0,0,0),v(20,0,0)}),route('overlap',{v(0,0,0),v(20,0,0)}),
    route('outside',{v(0,0,25),v(20,0,25)}),route('blocked',{v(10,0,-5),v(18,0,-5)})})
local events,calls={},{}
local wall={Instance='Wall'}
local function entry(a,b)
    calls[#calls+1]='entry:'..b.X..':'..b.Y..':'..b.Z
    if b.Z==0 and math.abs(b.X-3)<.01 then return false,'HeadBlocked',wall end
    return true
end
local function policy(q)
    calls[#calls+1]='policy:'..q.X..':'..q.Y..':'..q.Z
    return true
end
local function exit(a,b)
    calls[#calls+1]='exit:'..a.X..':'..a.Y..':'..a.Z
    return true
end
local plain,plainStats=g.Find(s,t,entry,policy,exit)
local expected=table.concat(calls,'|');calls={}
local traced,tracedStats=g.Find(s,t,entry,policy,exit,function(stage,edge,q,distance,reason,hit,cached)
    events[#events+1]={stage=stage,edge=edge,point=q,reason=reason,hit=hit,cached=cached}
end)
assert(table.concat(calls,'|')==expected,'diagnostic changed checks')
for k,val in pairs(plainStats) do assert(tracedStats[k]==val,k) end
assert(#traced.points==#plain.points);close(traced.cost,plain.cost)
for i,q in ipairs(plain.points) do close((q-traced.points[i]).Magnitude,0) end
local found={}
for _,e in ipairs(events) do
    if e.reason=='HeadBlocked' then assert(e.hit==wall);found.blocked=true end
    if e.stage=='GRAPH_SELECTED_ENTRY' then
        assert(e.edge.sources['near:1-2'] and not e.edge.sources['overlap:1-2']);found.entry=true
    end
    if e.stage=='GRAPH_SELECTED_EXIT' then found.exit=true end
end
assert(found.blocked and found.entry and found.exit)
-- Reject a point before casting; diagnostics must identify policy even if the
-- candidate was never included in entryCandidates/exitChecks.
g=loadGraph({route('policy',{v(0,0,0),v(20,0,0)})})
local seenPolicy=false
p=g.Find(s,t,function() return true end,function(q)
    if q.X==3 then return false,'Cooldown' end
    return true
end,function() return true end,function(stage,edge,q,distance,reason)
    if stage=='GRAPH_ENTRY' and reason=='Cooldown' then seenPolicy=true end
end)
assert(p and seenPolicy)
print('OK M585: route identities, rejection causes, observer preserves query sequence and plan')

-- M586 target-first route; a nearer entry on a worse route must not win.
s,t=v(0,0,-2),v(17,0,2)
g=loadGraph({route('near_target',{v(0,0,2),v(8,0,2),v(20,0,2)}),route('near_monster',{v(0,0,-1),v(20,0,-1)})})
local checked={}
p,stats=g.Find(s,t,function(a,b)
    local k=string.format('%.5f:%.5f:%.5f',b.X,b.Y,b.Z)
    assert(not checked[k],'entry recast');checked[k]=true
    assert(b.Z==2,'worse route tested before valid target route')
    return b.X>=9.5
end,nil,function() return true end)
assert(p and p.routeId=='near_target');close(p.points[1].X,17);close(p.points[#p.points].X,17)
-- If nearest route cannot be entered, use the next ranked route.
p=g.Find(s,t,function(a,b) return b.Z==-1 end,nil,function() return true end,nil,function() return true end)
assert(p and p.routeId=='near_target' and p.entryRouteId=='near_monster')
print('OK M586: target-first, cross-segment opening, distance-ordered entry and fallback')

-- The detailed trace still identifies unreachable and out-of-sphere lines
-- when those routes are actually considered (successful searches stop early).
s,t=v(0,0,0),v(10,0,0)
g=loadGraph({route('blocked',{v(8,0,2),v(12,0,2)}),route('too_far',{v(0,0,20),v(12,0,20)})})
local reasons={}
p,stats=g.Find(s,t,function() return false,'HeadBlocked',wall end,nil,function() error('unreachable exit cast') end,
    function(stage,edge,q,distance,reason) reasons[reason]=true end)
assert(not p and reasons.Unreachable and reasons.ExitDistance and reasons.HeadBlocked and stats.exitChecks==0)

-- M589: inspect the actual topology, independently of route selection.
local function topology(lines,maxHeightDelta)
    loadGraph(lines,maxHeightDelta)
    local Topology=require('MonsterRescueTopology')
    return Topology.Build(inst('Folder','Game1RescueRoutes',lines),maxHeightDelta or 2)
end
local function connectors(lines)
    local result,seen={},{}
    for _,line in pairs(lines) do
        for _,edge in ipairs(line.edges) do
            for _,node in ipairs({edge.a,edge.b}) do
                for _,link in ipairs(node.links) do
                    if link.edge.connector and not seen[link.edge] then
                        seen[link.edge]=true; table.insert(result,link.edge)
                    end
                end
            end
        end
    end
    return result
end
local function at(p,x,y,z) return (p-v(x,y,z)).Magnitude<1e-5 end
-- Interior authored vertices do not originate a transfer. Receiving one
-- inside an edge is allowed. In particular this does not depend on subdivision.
local lines=topology({route('a',{v(0,0,0),v(10,0,0),v(20,0,0)}),
    route('b',{v(12,0,5),v(15,0,5)})})
local edges=connectors(lines)
assert(#edges>0)
local interior=false
for _,edge in ipairs(edges) do
    for _,n in ipairs({edge.a,edge.b}) do
        assert(not at(n.position,10,0,0),'internal vertex originated a bridge')
        if at(n.position,12,0,0) or at(n.position,15,0,0) then interior=true end
    end
end
assert(interior)
-- A terminal touching another line already has a connection; do not add
-- an extra bridge from it. Its opposite end can still connect.
lines=topology({route('a',{v(0,0,0),v(-10,0,0)}),route('b',{v(0,0,-5),v(0,0,5)})})
local contacts=0
for _,edge in ipairs(connectors(lines)) do
    if at(edge.a.position,0,0,0) or at(edge.b.position,0,0,0) then
        if edge.length<1e-6 then contacts=contacts+1 end
        assert(edge.length<1e-6 or not at(edge.a.position,0,0,0),
            "connected terminal originated a new bridge")
    end
end
-- Incoming bridges may end at a contact; it must not originate a nonzero one.
assert(contacts==1)
-- The 2-stud threshold is inclusive, and excludes larger differences even
-- when all physical queries would accept the bridge.
for _,dy in ipairs({2,2.01,8}) do
    lines=topology({route('a',{v(0,0,0),v(20,0,0)}),route('b',{v(10,dy,12),v(10,dy,22)})})
    edges=connectors(lines)
    assert((#edges>0)==(dy<=2))
    for _,edge in ipairs(edges) do assert(math.abs(edge.a.position.Y-edge.b.position.Y)<=2+1e-6) end
end
-- If the unrestricted projection is too high, use the closest point on
-- the allowed portion of a sloped edge, rather than discarding the edge.
lines=topology({route('a',{v(0,0,0),v(0,0,-20)}),route('b',{v(1,5,0),v(11,0,0)})})
local clipped=false
for _,edge in ipairs(connectors(lines)) do
    assert(math.abs(edge.a.position.Y-edge.b.position.Y)<=2+1e-6)
    if at(edge.a.position,7,2,0) or at(edge.b.position,7,2,0) then clipped=true end
end
assert(clipped,'height-clipped interior projection missing')
-- Closed polylines have no free terminals, and do not generate bridges.
lines=topology({route('a',{v(0,0,0),v(10,0,0),v(10,0,10),v(0,0,0)}),
    route('b',{v(30,0,0),v(40,0,0),v(40,0,10),v(30,0,0)})})
assert(#connectors(lines)==0)
print('OK M589: free route terminals, interior projection, inclusive height limit, slope clipping, closed lines')
-- M590: custom height limit reaches the actual connection geometry.
for _,limit in ipairs({0,1.5,4}) do
    for _,dy in ipairs({0,1.5,4,4.01}) do
        lines=topology({route('a',{v(0,0,0),v(20,0,0)}),route('b',{v(10,dy,12),v(10,dy,22)})},limit)
        edges=connectors(lines)
        assert((#edges>0)==(dy<=limit))
        for _,edge in ipairs(edges) do assert(math.abs(edge.a.position.Y-edge.b.position.Y)<=limit+1e-6) end
    end
end
-- Exercise the public graph entry point with a non-default setting.
local separated={route('a',{v(0,0,0),v(20,0,0)}),route('b',{v(20,3,5),v(40,3,5)})}
local function entryOnly(a,b) return b.Y==0 end
local function exitOnly(a,b) return a.Y==3 end
s,t=v(0,0,-2),v(38,3,5)
assert(not loadGraph(separated,2).Find(s,t,entryOnly,nil,exitOnly,nil,function() return true end))
assert(loadGraph(separated,4).Find(s,t,entryOnly,nil,exitOnly,nil,function() return true end))
print('OK M590: configured height limit, zero, fractional and public graph propagation')
