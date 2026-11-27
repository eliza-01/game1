local Config=require(script.Parent:WaitForChild("MonsterNavigationConfig"))
local Trace=require(script.Parent:WaitForChild("MonsterNavigationTrace"))
local Workspace=game:GetService("Workspace")
local Geometry=require(script.Parent:WaitForChild("MonsterRecoveryGeometry"))
-- Kinematic lift only during a verified low-obstacle climb. No force, jump or
-- gravity compensation. The root remains collidable; every displacement is swept.
local Climb={}
local UP=Vector3.yAxis
local PROGRESS_STEP=.15
local NO_PROGRESS_SECONDS=7
local ARRIVAL_DISTANCE=.45
local CLEARANCE=.05
local MAX_STEP_TIME=.2

local function safetyParams(agent)
    local ray=RaycastParams.new()
    ray.FilterType=Enum.RaycastFilterType.Exclude
    ray.FilterDescendantsInstances={agent.model}
    ray.RespectCanCollide = true
    ray.CollisionGroup=agent.root.CollisionGroup
    return ray
end

function Climb.Stop(state)
    local c=state.climb
    if not c then return end
    state.climb=nil
    local root=c.root
    -- Death presentation owns its anchored root. Never release it on cleanup.
    if root.Parent and c.model:GetAttribute("LifeState")=="Alive" then
        root.Anchored=false
        root.AssemblyLinearVelocity=Vector3.zero
        root.AssemblyAngularVelocity=Vector3.zero
        pcall(function() root:SetNetworkOwner(nil) end)
    end
end

local function shift(c,delta)
    local distance=delta.Magnitude
    if distance<=.001 then return 0 end
    local root=c.root
    local hit=Workspace:Blockcast(root.CFrame,root.Size,delta,c.params)
    local allowed=hit and math.max(0,math.min(distance,hit.Distance-CLEARANCE)) or distance
    if allowed>.001 then root.CFrame=root.CFrame+delta.Unit*allowed end
    return allowed
end

function Climb.Begin(agent,state,landing,rise,_params,now)
    local root=agent.root
    if state.climb or rise<=0 or root.Anchored then return false end
    local _,height=Geometry.Body(agent)
    -- Never turn a low-obstacle climb into unrestricted flight over high walls.
    local maxRise=math.max(0,height-.05)
    if rise>=height then return false end
    local c={root=root,model=agent.model,params=safetyParams(agent),landing=landing,
        targetY=root.Position.Y+math.min(rise+.12,maxRise),maxY=root.Position.Y+maxRise,
        lastAt=now,bestY=root.Position.Y,bestDistance=Geometry.Horizontal(landing-root.Position).Magnitude,
        progressAt=now,crossing=false}
    state.climb=c
    agent.humanoid:Move(Vector3.zero,false)
    agent.humanoid:MoveTo(root.Position)
    root.AssemblyLinearVelocity=Vector3.zero
    root.AssemblyAngularVelocity=Vector3.zero
    root.Anchored=true
    agent.navigating=true
    Trace.Event(agent,"CLIMB_LEVITATE","targetY="..tostring(c.targetY),"maxY="..tostring(c.maxY))
    return true
end

function Climb.Step(agent,state,speed,_params,now)
    local c=state.climb
    if not c then return "Failed" end
    local root=c.root
    local dt=math.clamp(now-c.lastAt,0,MAX_STEP_TIME); c.lastAt=now
    local delta=Geometry.Horizontal(c.landing-root.Position)
    local distance=delta.Magnitude
    if distance<=ARRIVAL_DISTANCE and root.Position.Y>=c.targetY-CLEARANCE then
        Climb.Stop(state); return "Done"
    end
    if root.Position.Y>=c.bestY+PROGRESS_STEP then c.bestY=root.Position.Y; c.progressAt=now end
    if distance<=c.bestDistance-PROGRESS_STEP then c.bestDistance=distance; c.progressAt=now end
    if now-c.progressAt>=NO_PROGRESS_SECONDS then
        Trace.Event(agent,"CLIMB_STALLED","distance="..tostring(distance),"height="..tostring(root.Position.Y))
        return "Failed"
    end
    -- Rise to the measured surface first. Once horizontal movement is possible,
    -- hold that height instead of falling back between impulses. If the lip is
    -- still blocking the physical root, add a little more height within the cap.
    local lift=0
    if root.Position.Y<c.targetY-CLEARANCE then
        lift=math.min(c.targetY-root.Position.Y,Config.climbSpeed*dt)
    elseif distance>ARRIVAL_DISTANCE then
        local step=math.min(distance,speed*dt)
        local moved=shift(c,delta.Unit*step)
        if moved>.001 then
            if not c.crossing then Trace.Event(agent,"CLIMB_CROSS","height="..tostring(root.Position.Y)); c.crossing=true end
        elseif step>.001 then
            lift=math.min(math.max(0,c.maxY-root.Position.Y),Config.climbSpeed*dt)
        end
    end
    if lift>.001 then shift(c,UP*lift) end
    agent.navigating=true
    return "Moving"
end
return table.freeze(Climb)
