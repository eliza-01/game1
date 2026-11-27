local Trace=require(script.Parent:WaitForChild("MonsterNavigationTrace"))
local Config=require(script.Parent:WaitForChild("MonsterNavigationConfig"))
-- Local geometry queries. Terrain remains physical, but is not an obstacle query hit.
local Workspace=game:GetService("Workspace")
local Players=game:GetService("Players")
local Geometry={}
local UP=Vector3.yAxis
local function horizontal(v) return Vector3.new(v.X,0,v.Z) end
Geometry.Horizontal=horizontal

-- Log the actual result of the same query, not a second diagnostic cast.
local function tracedRay(label,origin,delta,params)
    local result=Workspace:Raycast(origin,delta,params)
    Trace.Ray(params,label,origin,delta,result)
    return result
end
function Geometry.Body(agent)
    local root=agent.root
    local visual=agent.model:FindFirstChild("RootCollider")
    local foot=root.Position-UP*(root.Size.Y/2+agent.humanoid.HipHeight)
    local top=if visual and visual:IsA("BasePart") then visual.Position.Y+visual.Size.Y/2 else root.Position.Y+root.Size.Y/2
    return foot,math.max(root.Size.Y,top-foot.Y),math.max(root.Size.X,root.Size.Z)/2
end
function Geometry.Params(agent)
    local ignore={agent.model,Workspace.Terrain}
    for _,name in ipairs({"Monsters","NPCs","Npcs","Game1RescueRoutes"}) do
        local f=Workspace:FindFirstChild(name); if f then table.insert(ignore,f) end
    end
    for _,player in ipairs(Players:GetPlayers()) do if player.Character then table.insert(ignore,player.Character) end end
    local ray=RaycastParams.new()
    ray.FilterType=Enum.RaycastFilterType.Exclude; ray.FilterDescendantsInstances=ignore
    ray.RespectCanCollide=true; ray.CollisionGroup=agent.root.CollisionGroup
    Trace.Bind(ray,agent)
    return ray
end
function Geometry.Overlap(ray)
    local overlap=OverlapParams.new()
    overlap.FilterType=ray.FilterType; overlap.FilterDescendantsInstances=ray.FilterDescendantsInstances
    overlap.RespectCanCollide=true; overlap.CollisionGroup=ray.CollisionGroup; overlap.MaxParts=96
    return overlap
end
function Geometry.HeadClear(foot,height,targetPoint,params)
    local origin=foot+UP*(height-.05)
    local delta=targetPoint-origin
    return delta.Magnitude<.05 or tracedRay("HEEL_RAY",origin,delta,params)==nil
end
-- A slanted sight ray can pass above a fence while the melee body is still outside.
-- Use the current foot level and physical root, not the target's elevated Y.
function Geometry.MeleeClear(agent,targetPosition)
    local foot=Geometry.Body(agent)
    local delta=horizontal(targetPosition-agent.root.Position)
    if delta.Magnitude<.05 then return true end
    local params=Geometry.Params(agent)
    if Workspace:Raycast(foot+UP*.25,delta,params) then return false end
    return Workspace:Blockcast(agent.root.CFrame,agent.root.Size*.95,delta,params)==nil
end
function Geometry.Probe(foot,height,direction,distance,params)
    local delta=direction*distance
    local head=tracedRay("PROBE_HEAD",foot+UP*(height-.05),delta,params)
    local lower=tracedRay("PROBE_FOOT",foot+UP*.25,delta,params)
    return head,lower
end
-- Route connectors: two centre rays only. World geometry is authored without
-- gaps narrower than an actor; physical lift safety is owned by ClimbMotion.
function Geometry.Clear(agent,a,b,height,radius,params)
    local delta=b-a
    if delta.Magnitude<.05 then return true end
    if Workspace:Raycast(a+UP*(height-.05),delta,params) then return false end
    return Workspace:Raycast(a+UP*.25,delta,params)==nil
end
-- Primary direct-movement gate. Horizontal, no scan beyond the target.
function Geometry.HeadObstacle(foot,height,goal,attackRadius,params)
    local delta=horizontal(goal-foot)
    local distance=math.min(delta.Magnitude,attackRadius)
    if distance<.05 then return nil end
    return tracedRay("PRIMARY_HEAD",foot+UP*(height-.05),delta.Unit*distance,params)
end
-- A clear diagonal to the target's heels must never hide a high wall
-- farther than the normal short Direct lookahead. Both rays cover the goal.
function Geometry.RecoveryExitClear(foot,height,goal,params)
    return Geometry.HeadClear(foot,height,goal+UP*.1,params)
        and Geometry.HeadObstacle(foot,height,goal,horizontal(goal-foot).Magnitude,params)==nil
end
-- Probe the *actual* surface above the foot-ray hit, rather than trusting MeshPart bounds.
function Geometry.ClimbPoint(agent,foot,height,radius,direction,head,lower,params)
    if not lower or (head and head.Distance-lower.Distance<.35) then return nil end
    if lower.Distance>radius+2 then return nil end
    local landing=lower.Position+direction*(radius+.25)
    -- A thin fence can end before the centre of the landing point. Probe
    -- just beyond the contact as well as at the intended crossing point.
    -- The vertical lift must clear the highest measured top along the crossing.
    local rise=0
    for _,offset in ipairs({.04,.1,.35,radius+.25}) do
        local sample=lower.Position+direction*offset
        local surface=Workspace:Raycast(Vector3.new(sample.X,foot.Y+height-.06,sample.Z),-UP*(height-.1),params)
        if surface and surface.Normal.Y>=.45 then
            rise=math.max(rise,surface.Position.Y-foot.Y)
        end
    end
    if rise<.15 or rise>=height then return nil end
    return Vector3.new(landing.X,foot.Y+rise,landing.Z),rise
end
-- On a confirmed high hit, reuse it and cast only from the feet.
function Geometry.ProbeClimb(agent,foot,height,radius,direction,distance,params,knownHead)
    local head,lower
    if knownHead then
        head=knownHead
        lower=tracedRay("PROBE_FOOT",foot+UP*.25,direction*distance,params)
    else
        head,lower=Geometry.Probe(foot,height,direction,distance,params)
    end
    local landing,rise=Geometry.ClimbPoint(agent,foot,height,radius,direction,head,lower,params)
    return landing,rise,"Ray",head,lower
end
-- Thin head-level slab: only high parts are candidates for the sides of a passage.
-- Low objects are deliberately ignored here and can be climbed on approach.
function Geometry.ClimbContinues(landing,goal,height,radius,params)
    local delta=horizontal(goal-landing)
    if delta.Magnitude<=.05 then return math.abs(goal.Y-landing.Y)<=2 end
    local head,lower=Geometry.Probe(landing,height,delta.Unit,math.min(Config.searchDistance,delta.Magnitude),params)
    -- A second high wall immediately beyond a box is not a valid shortcut.
    -- Successive low steps are allowed, but remain a heuristic rather than a path guarantee.
    return head==nil or (lower~=nil and head.Distance-lower.Distance>=.35)
end
local function headPassage(a,b,height,radius,params)
    local delta=b-a
    if delta.Magnitude<.05 then return true end
    local origin=a+UP*(height-.05)
    return Workspace:Raycast(origin,delta,params)==nil
end
function Geometry.Detour(agent,foot,goal,height,radius,params,overlap,allowed)
    local delta=horizontal(goal-foot)
    if delta.Magnitude<.01 then return nil end
    local forward=delta.Unit
    local center=foot+UP*(height-.05)+forward*(Config.searchDistance/2)
    local parts=Workspace:GetPartBoundsInBox(CFrame.lookAt(center,center+forward),Vector3.new(Config.searchWidth,.2,Config.searchDistance),overlap)
    if Trace.Enabled(agent) then Trace.Event(agent,"DETOUR_SCAN","parts="..#parts,"foot="..Trace.V(foot),"goal="..Trace.V(goal)) end
    local points={}
    for _,part in ipairs(parts) do
        local half=part.Size/2
        for _,x in ipairs({-1,1}) do for _,z in ipairs({-1,1}) do
            local corner=part.CFrame:PointToWorldSpace(Vector3.new(x*(half.X+radius+.7),0,z*(half.Z+radius+.7)))
            local p=Vector3.new(corner.X,foot.Y,corner.Z)
            -- At contact the padded near corner can lie slightly behind the
            -- actor. The scan still only covers the forward half-space.
            if horizontal(p-foot):Dot(forward)>=-(radius+1) and (p-foot).Magnitude<=math.sqrt(Config.searchDistance^2+(Config.searchWidth/2)^2) and allowed(p) then
                table.insert(points,{point=p,part=part,cost=(p-foot).Magnitude+(goal-p).Magnitude})
            end
        end end
    end
    table.sort(points,function(a,b) return a.cost<b.cost end)
    -- A single corner cannot connect opposite faces of a solid box. Consider
    -- up to two corners of the same blocker, with cached entry/exit tests.
    -- No wall-follow, no arbitrary graph search over the world geometry.
    local count=math.min(8,#points)
    local best,bestCost=nil,math.huge
    local function passage(a,b) return headPassage(a,b,height,radius,params) end
    local function entry(c)
        if c.entry==nil then c.entry=passage(foot,c.point) end
        return c.entry
    end
    local function exit(c)
        if c.exit==nil then c.exit=Geometry.RecoveryExitClear(c.point,height,goal,params) end
        return c.exit
    end
    for i=1,count do
        local a=points[i]
        if a.cost<bestCost and entry(a) then
            if exit(a) then best,bestCost={a.point},a.cost end
            for j=1,count do
                local b=points[j]
                if i~=j and a.part==b.part then
                    local cost=(a.point-foot).Magnitude+(b.point-a.point).Magnitude+(goal-b.point).Magnitude
                    if cost<bestCost and exit(b) and passage(a.point,b.point) then
                        best,bestCost={a.point,b.point},cost
                    end
                end
            end
        end
    end
    if best then return {points=best,cost=bestCost} end
    return nil
end
return table.freeze(Geometry)
