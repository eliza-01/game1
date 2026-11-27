local Trace=require(script.Parent:WaitForChild("MonsterNavigationTrace"))
local Config=require(script.Parent:WaitForChild("MonsterNavigationConfig"))
-- Experimental monster-only navigation. One 3D progress sample/second while moving.
-- State is owned by this module; combat, spawn, death and leash remain external.
local Geometry=require(script.Parent:WaitForChild("MonsterRecoveryGeometry"))
local Graph=require(script.Parent:WaitForChild("MonsterRescueGraph"))
local Climb=require(script.Parent:WaitForChild("MonsterClimbMotion"))
local Watchdog=require(script.Parent:WaitForChild("MonsterStuckWatchdog"))
local DeathChase=require(script.Parent:WaitForChild("MonsterDeathChasePolicy"))
local Blocked=require(script.Parent:WaitForChild("MonsterBlockedPursuit"))
local RetreatGeometry=require(script.Parent:WaitForChild("MonsterBlockedRetreatGeometry"))
local Speed=require(script.Parent:WaitForChild("MonsterNavigationSpeed"))
local diagnosticAttributes=game:GetService("RunService"):IsStudio()
local Navigation={}
Navigation.Initialize=Graph.Initialize
local UP=Vector3.yAxis
local horizontal=Geometry.Horizontal

local function mode(agent,state,value)
    if state.mode==value then return end
    Trace.Event(agent,"MODE",state.mode or "None","->",value)
    state.mode=value
    agent.model:SetAttribute("MonsterRecoveryMode",value)
end
local function movementSpeed(state,speed)
    return speed*Speed.Multiplier(state,Config)
end
local function resetSample(agent,state,now)
    state.position=agent.root.Position; state.sampleAt=now
    state.expected=0; state.lastAt=now
end
local function clearPlan(agent,state,now)
    Climb.Stop(state)
    state.noAccessiblePlan=nil
    state.blockedPursuit=nil
    state.plan=nil; state.index=1; state.nextCheck=now+Config.recheckSeconds
    state.retryClimb=nil
    agent.model:SetAttribute("MonsterRecoveryPlanIndex",nil); agent.model:SetAttribute("MonsterRecoveryPlanSize",nil)
    state.moveAt=0; state.movePoint=nil
    resetSample(agent,state,now)
    mode(agent,state,"Direct")
end
function Navigation.Clear(agent)
    local state=agent.recoveryNavigation
    if not state then return end
    Trace.Event(agent,"CLEAR","mode="..tostring(state.mode),"index="..tostring(state.index),"returning="..tostring(agent.returning))
    Climb.Stop(state)
    agent.recoveryNavigation=nil
    if agent.model.Parent then
        if state.plan or state.mode=="Climb" or state.mode=="Retry" or state.blockedPursuit then
            agent.model:SetAttribute("MonsterLastRecoveryEvent","ExternalNavigationStop")
        end
        agent.model:SetAttribute("MonsterRecoveryMode",nil); agent.model:SetAttribute("MonsterRecoveryPoint",nil)
        agent.model:SetAttribute("MonsterRecoveryStuckSeconds",nil)
        agent.model:SetAttribute("MonsterRecoveryPlanIndex",nil); agent.model:SetAttribute("MonsterRecoveryPlanSize",nil)
    end
end
local function allowed(agent,point)
    if agent.returning then return true end -- Return may start outside leash.
    return DeathChase.AllowsPursuitPosition(agent,point)
end
local function goalFoot(agent,destination,foot)
    local target=agent.target
    if not agent.returning and target then
        local collider=target:FindFirstChild("RootCollider")
        if collider and collider:IsA("BasePart") then
            return collider.Position-UP*(collider.Size.Y/2)
        end
        local root=target:FindFirstChild("NavigationRoot") or target:FindFirstChild("HumanoidRootPart")
        local humanoid=target:FindFirstChildOfClass("Humanoid")
        if root and root:IsA("BasePart") then
            local hip=tonumber(target:GetAttribute("NavigationHipHeight")) or (humanoid and humanoid.HipHeight) or 0
            return root.Position-UP*(root.Size.Y/2+hip)
        end
    end
    return destination-(agent.root.Position-foot)
end
local function move(agent,state,point,speed,now)
    agent.navigating=true
    agent.humanoid.WalkSpeed=speed
    agent.humanoid.AutoRotate=true
    if now>=state.moveAt or not state.movePoint or (state.movePoint-point).Magnitude>1 then
        state.moveAt=now+.3; state.movePoint=point
        if Trace.Enabled(agent) then
            Trace.Changed(agent,"MOVE_OWNER",state.mode..":"..tostring(state.index),"point="..Trace.V(point))
            Trace.Rate(agent,"MOVE_TO",1,"mode="..state.mode,"root="..Trace.V(agent.root.Position),"point="..Trace.V(point),"speed="..tostring(speed))
        end
        agent.humanoid:MoveTo(point)
    end
end
local function pointKey(p)
    return string.format("%d:%d:%d",math.round(p.X),math.round(p.Y),math.round(p.Z))
end
local function eligible(state,point,now)
    return (state.failed[pointKey(point)] or 0)<=now
end
local function waitRetry(agent,state,now,reason)
    agent.model:SetAttribute("MonsterLastRecoveryEvent",reason or "NoPlan")
    Trace.Event(agent,"RETRY",reason or "NoPlan","index="..tostring(state.index))
    local retryClimb=state.climb~=nil or state.retryClimb
    local failed=(state.climb and state.climb.landing) or (state.plan and state.plan[state.index])
    if failed then state.failed[pointKey(failed)]=now+8 end
    clearPlan(agent,state,now)
    state.retryClimb=retryClimb
    state.noAccessiblePlan=reason=="NoAccessiblePlan"
    state.retryAt=now+1.5
    mode(agent,state,"Retry")
    agent.humanoid:Move(Vector3.zero,false); agent.humanoid:MoveTo(agent.root.Position)
    agent.model:SetAttribute("MonsterRecoveryPoint",nil)
    if state.noAccessiblePlan and not agent.returning and agent.target then
        Blocked.Begin(state)
        state.stuckWatchdog=nil
        agent.model:SetAttribute("MonsterRecoveryStuckSeconds",0)
        mode(agent,state,"BlockedRetreat")
    end
end
local function probeClimb(agent,state,foot,point,height,radius,ray,now,knownHead,knownDistance)
    local delta=horizontal(point-foot)
    if delta.Magnitude<=.05 then return nil end
    local landing,rise,probe,head,lower=Geometry.ProbeClimb(agent,foot,height,radius,delta.Unit,knownDistance or math.min(Config.searchDistance,math.max(radius+2,delta.Magnitude)),ray,knownHead)
    if diagnosticAttributes then
        agent.model:SetAttribute("MonsterRecoveryProbe",probe)
        agent.model:SetAttribute("MonsterRecoveryHeadDistance",head and head.Distance or nil)
        agent.model:SetAttribute("MonsterRecoveryFootDistance",lower and lower.Distance or nil)
    end
    if Trace.Enabled(agent) then Trace.Event(agent,"CLIMB_CANDIDATE","landing="..Trace.V(landing),"rise="..tostring(rise),"probe="..tostring(probe)) end
    if landing and allowed(agent,landing) and (not head or eligible(state,landing,now)) then return landing,rise,lower,head end
    return nil,nil,lower,head
end
-- Low obstacles are a movement primitive, not a route candidate. In particular,
-- do not run Detour/Graph.Find or consult the failed-route cooldown here.
local function beginLowClimb(agent,state,foot,point,height,radius,ray,now,landing,rise,speed)
    if not landing then
        -- A missing top sample must not send a stuck actor into path search.
        -- Use a short forward target for the ordinary physical jump.
        -- The target supplies direction, not an artificial lift height.
        local delta=horizontal(point-foot)
        if delta.Magnitude>.05 then
            rise=math.min(.25,height*.25)
            landing=foot+delta.Unit*math.min(delta.Magnitude,radius+.5)+UP*rise
        end
    end
    if landing and allowed(agent,landing) and Climb.Begin(agent,state,landing,rise,ray,now,movementSpeed(state,speed)) then
        state.planKind=state.plan and state.mode or "Direct"
        state.retryClimb=nil
        agent.model:SetAttribute("MonsterLastRecoveryEvent","LowClimbSelected")
        Trace.Event(agent,"LOW_CLIMB","landing="..Trace.V(landing))
        mode(agent,state,"Climb"); agent.model:SetAttribute("MonsterRecoveryPoint",landing)
        return
    end
    waitRetry(agent,state,now,"LowClimbUnavailable")
    state.retryClimb=true
end
local function choosePlan(agent,state,foot,goal,height,radius,ray,now,landing,rise,speed)
    local function policy(p)
        if not allowed(agent,p) then return false,"Leash" end
        if not eligible(state,p,now) then return false,"Cooldown" end
        return true
    end
    local function connect(a,b)
        if not allowed(agent,b) then return false,"Leash" end
        if not eligible(state,a,now) then return false,"CooldownOrigin" end
        if not eligible(state,b,now) then return false,"Cooldown" end
        return Geometry.RouteEntryClear(a,b,ray)
    end
    local detour=Geometry.Detour(agent,foot,goal,height,radius,ray,Geometry.Overlap(ray),function(p) return allowed(agent,p) and eligible(state,p,now) end)
    local observe=Trace.RouteObserver(agent,foot,goal,Config.searchDistance)
    local route,graphStats=Graph.Find(foot,goal,connect,policy,
        function(a,b)
            if not allowed(agent,b) then return false,"Leash" end
            if not eligible(state,a,now) then return false,"Cooldown" end
            return Geometry.RecoveryExitClear(a,height,b,ray)
        end,observe,function(a,b) return Geometry.RouteEntryClear(a,b,ray) end)
    if graphStats and Trace.Enabled(agent) then
        Trace.Event(agent,"GRAPH_SEARCH","entryCandidates="..graphStats.entryCandidates,"entries="..graphStats.entries,"entryChecks="..graphStats.entryChecks,"reachableExits="..graphStats.reachableExits,"exitChecks="..graphStats.exitChecks,"transferChecks="..graphStats.transferChecks)
    end
    if route then
        for _,p in ipairs(route.points) do
            local ok,reason=policy(p)
            if not ok then
                if observe then Trace.Event(agent,"GRAPH_PLAN_REJECTED","point="..Trace.V(p),"reason="..reason) end
                route=nil; break
            end
        end
    end
    if Trace.Enabled(agent) then
        Trace.Event(agent,"CANDIDATES","collisionCost="..tostring(detour and detour.cost),"routeCost="..tostring(route and route.cost),"routeId="..tostring(route and route.routeId),"entryRouteId="..tostring(route and route.entryRouteId),"exitHeightDelta="..tostring(route and route.exitHeightDelta),"exitDistance="..tostring(route and route.exitDistance),"climb="..Trace.V(landing))
    end
    local plan,kind=detour,"Collision"
    if route and (not detour or route.cost<detour.cost) then plan,kind=route,"RescueRoute" end
    -- A local climb is another candidate, not a compulsory detour.
    if landing then
        local localCost=horizontal(landing-foot).Magnitude+rise+(goal-landing).Magnitude
        if (not plan or Geometry.ClimbContinues(landing,goal,height,radius,ray)) and (not plan or localCost<=plan.cost) then
            if Climb.Begin(agent,state,landing,rise,ray,now,movementSpeed(state,speed)) then
                agent.model:SetAttribute("MonsterLastRecoveryEvent","ClimbSelected")
                state.retryClimb=nil; state.planKind="Direct"; mode(agent,state,"Climb")
                agent.model:SetAttribute("MonsterRecoveryPoint",landing); return
            end
        end
    end
    if not plan then waitRetry(agent,state,now,"NoAccessiblePlan"); return end
    agent.model:SetAttribute("MonsterLastRecoveryEvent",kind.."Selected")
    if Trace.Enabled(agent) then
        local points={}
        for i,p in ipairs(plan.points) do points[i]=Trace.V(p) end
        Trace.Event(agent,"PLAN",kind,"cost="..tostring(plan.cost),table.concat(points," -> "))
    end
    state.retryClimb=nil; state.plan=plan.points; state.index=1; state.nextCheck=now+Config.recheckSeconds; state.moveAt=0
    agent.model:SetAttribute("MonsterRecoveryPlanIndex",1)
    agent.model:SetAttribute("MonsterRecoveryPlanSize",#state.plan)
    resetSample(agent,state,now); mode(agent,state,kind)
end

local function attackRadius(agent)
    return math.max(0,tonumber(agent.model:GetAttribute("MonsterAttackRadius")) or 3)
end
-- Recovery exit is intentionally asymmetric: head -> target heels first,
-- then a full-length horizontal gate, not the short Direct lookahead.
local function directClear(agent,foot,goal,height,ray)
    return Geometry.RecoveryExitClear(foot,height,goal,ray)
end

-- Only player-targeted NoAccessiblePlan enters this policy. Returning home
-- retains the original watchdog and recall path.
local function stepBlocked(agent,state,destination,speed,now)
    local range=Config.bowRange
    local before=state.blockedPursuit.phase
    local findPoint
    if before~="Wait" then
        findPoint=function(position,target,desired)
            return RetreatGeometry.FindPoint(agent,position,target,desired,function(p) return allowed(agent,p) end)
        end
    end
    local phase,point=Blocked.Step(state,agent.root.Position,destination,range,Config.blockedRetreatBuffer,now,movementSpeed(state,speed),findPoint)
    if phase=="Reengage" then
        Trace.Event(agent,"BLOCKED_REENGAGE")
        clearPlan(agent,state,now); state.reengaging=true; state.stuckWatchdog=nil
        state.nextCheck=now; agent.lastDamageAt=now
        return false
    end
    if phase=="Wait" then
        if before~="Wait" then
            agent.lastDamageAt=now
            agent.humanoid:Move(Vector3.zero,false); agent.humanoid:MoveTo(agent.root.Position)
            Trace.Event(agent,"BLOCKED_WAIT","range="..tostring(range))
        end
        mode(agent,state,"BlockedWait")
        local seconds=math.floor(Blocked.WaitSeconds(state,now))
        if agent.model:GetAttribute("MonsterRecoveryStuckSeconds")~=seconds then
            agent.model:SetAttribute("MonsterRecoveryStuckSeconds",seconds)
        end
        if seconds>=Config.stuckReturnSeconds then
            Trace.Event(agent,"STUCK_TIMEOUT","seconds="..tostring(seconds),"mode="..state.mode)
            return true,"StuckTimeout"
        end
    else
        mode(agent,state,"BlockedRetreat")
        if point then move(agent,state,point,movementSpeed(state,speed),now)
        else agent.humanoid:Move(Vector3.zero,false); agent.humanoid.WalkSpeed=0 end
    end
    return true
end

function Navigation.NavigateTo(agent,destination,speed)
    if not agent.active or not agent.root.Parent then return end
    speed=math.max(0,speed)*math.clamp(tonumber(agent.model:GetAttribute("SkillMoveMultiplier")) or 1,0,1)
    local now=os.clock()
    local state=agent.recoveryNavigation
    if not state or state.target~=agent.target or state.returning~=agent.returning then
        if state then Trace.Event(agent,"RESET_CONTEXT","targetChanged="..tostring(state.target~=agent.target),"returnChanged="..tostring(state.returning~=agent.returning)) end
        Navigation.Clear(agent)
        state={target=agent.target,returning=agent.returning,moveAt=0,index=1,retryAt=0,nextCheck=now,failed={}}
        agent.recoveryNavigation=state; resetSample(agent,state,now); mode(agent,state,"Direct")
    end
    if state.blockedPursuit then
        local handled,result=stepBlocked(agent,state,destination,speed,now)
        if handled then return result end
    end
    if speed<=.01 then
        Navigation.Clear(agent); agent.humanoid:Move(Vector3.zero,false); agent.humanoid.WalkSpeed=0; return
    end
    -- A chase-level watchdog survives plan changes, local climb failures and
    -- Retry. Return is owned by AI, not by the navigation module.
    do
        local expired,seconds=Watchdog.Step(state,agent.root.Position,now,Config.stuckReturnSeconds)
        if agent.model:GetAttribute("MonsterRecoveryStuckSeconds")~=seconds then
            agent.model:SetAttribute("MonsterRecoveryStuckSeconds",seconds)
        end
        if expired then
            Trace.Event(agent,"STUCK_TIMEOUT","seconds="..tostring(seconds),"mode="..state.mode)
            return "StuckTimeout"
        end
    end
    local foot,height,radius=Geometry.Body(agent)
    local goal=goalFoot(agent,destination,foot)
    local offset=agent.root.Position-foot
    if Trace.Enabled(agent) then
        local collider=agent.model:FindFirstChild("RootCollider")
        Trace.Rate(agent,"BODY_GOAL",1,"root="..Trace.V(agent.root.Position),"foot="..Trace.V(foot),"height="..tostring(height),"rootSize="..Trace.V(agent.root.Size),"collider="..Trace.V(collider and collider.Position),"colliderSize="..Trace.V(collider and collider.Size),"goalFoot="..Trace.V(goal),"attackRadius="..tostring(attackRadius(agent)),"returning="..tostring(agent.returning))
    end
    if state.climb then
        if not allowed(agent,state.climb.landing) then waitRetry(agent,state,now,"ClimbOutsidePursuitBoundary"); return end
        local result=Climb.Step(agent,state,movementSpeed(state,speed),nil,now)
        Trace.Changed(agent,"CLIMB_STEP",result)
        if result=="Failed" then waitRetry(agent,state,now,"ClimbFailed")
        elseif result=="Timeout" then
            clearPlan(agent,state,now); state.nextCheck=now
            agent.model:SetAttribute("MonsterLastRecoveryEvent","ClimbTimeout")
            agent.model:SetAttribute("MonsterRecoveryPoint",nil)
        elseif result=="Done" then resetSample(agent,state,now); state.moveAt=0; state.nextCheck=now; mode(agent,state,state.plan and state.planKind or "Direct") end
        return
    end
    if now<state.retryAt then return end
    if state.mode=="Retry" then
        -- Retry searches again from rest, rather than charging the same wall.
        local ray=Geometry.Params(agent)
        local landing,rise,lower,head
        -- A low obstacle may be invisible to both route-exit rays. After a
        -- stalled climb, never recharge it until the near foot contact clears.
        if state.retryClimb then
            landing,rise,lower,head=probeClimb(agent,state,foot,goal,height,radius,ray,now)
            if not head and lower and lower.Distance<=radius+2 then
                beginLowClimb(agent,state,foot,goal,height,radius,ray,now,landing,rise,speed)
                return
            end
        end
        if (not lower or lower.Distance>radius+2) and directClear(agent,foot,goal,height,ray) then
            Trace.Event(agent,"EXIT_ROUTE","DirectPathClear")
            agent.model:SetAttribute("MonsterLastRecoveryEvent","DirectPathClear")
            clearPlan(agent,state,now)
        else
            if not state.retryClimb then landing,rise,lower,head=probeClimb(agent,state,foot,goal,height,radius,ray,now) end
            if not head and (state.retryClimb or (lower and lower.Distance<=radius+2)) then
                beginLowClimb(agent,state,foot,goal,height,radius,ray,now,landing,rise,speed)
                return
            end
            if state.noAccessiblePlan then
                state.retryAt=now+1.5 -- direct/low-climb checks only; no repeated graph search
                return
            end
            choosePlan(agent,state,foot,goal,height,radius,ray,now,landing,rise,speed)
            if state.climb or not state.plan then return end
            state.planKind=state.mode
        end
    end
    local point=goal
    if state.plan then
        local previousIndex=state.index
        while state.plan[state.index] and (state.plan[state.index]-foot).Magnitude<=1.25 do state.index+=1 end
        if not state.plan[state.index] then
            -- The target can move while we are following a route. Completion
            -- is not permission to run into a newly blocked exit.
            local ray=Geometry.Params(agent)
            if directClear(agent,foot,goal,height,ray) then
                Trace.Event(agent,"EXIT_ROUTE","RouteComplete")
                agent.model:SetAttribute("MonsterLastRecoveryEvent","RouteComplete")
                clearPlan(agent,state,now)
            else
                waitRetry(agent,state,now,"RouteExitBlocked"); return
            end
        else
            point=state.plan[state.index]
            -- The chord across a sharp corner underestimates distance travelled.
            -- Start the next sample at the new segment, not the previous turn.
            if state.index~=previousIndex then resetSample(agent,state,now); state.moveAt=0 end
            if state.index~=previousIndex then
                Trace.Event(agent,"WAYPOINT",previousIndex,"->",state.index)
                agent.model:SetAttribute("MonsterRecoveryPlanIndex",state.index)
            end
            if now>=state.nextCheck then
                state.nextCheck=now+Config.recheckSeconds
                local ray=Geometry.Params(agent)
                if directClear(agent,foot,goal,height,ray) then
                    Trace.Event(agent,"EXIT_ROUTE","DirectPathClear")
                    agent.model:SetAttribute("MonsterLastRecoveryEvent","DirectPathClear")
                    clearPlan(agent,state,now); point=goal
                end
            end
        end
    end
    -- First check before issuing Direct movement, then once per recheck interval.
    -- A high obstacle starts recovery without waiting for the speed sample.
    if not state.plan and now>=state.nextCheck then
        state.nextCheck=now+Config.recheckSeconds
        local ray=Geometry.Params(agent)
        local reach=attackRadius(agent)
        local head=Geometry.HeadObstacle(foot,height,goal,reach,ray)
        if head then
            local distance=math.min(horizontal(goal-foot).Magnitude,reach)
            local landing,rise=probeClimb(agent,state,foot,goal,height,radius,ray,now,head,distance)
            choosePlan(agent,state,foot,goal,height,radius,ray,now,landing,rise,speed)
            if state.climb or not state.plan then return end
            state.planKind=state.mode; point=state.plan[1]
        end
    end
    if not allowed(agent,point) then waitRetry(agent,state,now,"PointOutsidePursuitBoundary"); return end
    -- Accumulate expected displacement with actual effective speed (Slow/Root/Stun).
    state.expected+=movementSpeed(state,speed)*math.max(0,now-state.lastAt)
    state.lastAt=now
    if now-state.sampleAt>=Config.sampleSeconds then
        for k,untilTime in pairs(state.failed) do if untilTime<=now then state.failed[k]=nil end end
        local actual=(agent.root.Position-state.position).Magnitude
        local elapsed=now-state.sampleAt
        if diagnosticAttributes then
            agent.model:SetAttribute("MonsterRecoveryActualSpeed",math.round(actual/elapsed*100)/100)
            agent.model:SetAttribute("MonsterRecoveryExpectedSpeed",math.round(state.expected/elapsed*100)/100)
        end
        local stuck=actual<state.expected*Config.stuckPercent/100 and (point-foot).Magnitude>1.25
        if Trace.Enabled(agent) then Trace.Event(agent,"SAMPLE",string.format("actual=%.2f expected=%.2f elapsed=%.2f stuck=%s",actual,state.expected,elapsed,tostring(stuck)),"point="..Trace.V(point)) end
        resetSample(agent,state,now)
        if stuck then
            local ray=Geometry.Params(agent)
            local landing,rise,_,head=probeClimb(agent,state,foot,point,height,radius,ray,now)
            if not head then
                beginLowClimb(agent,state,foot,point,height,radius,ray,now,landing,rise,speed)
                return
            end
            if state.plan and landing and Climb.Begin(agent,state,landing,rise,ray,now,movementSpeed(state,speed)) then
                state.planKind=state.mode
                mode(agent,state,"Climb"); agent.model:SetAttribute("MonsterRecoveryPoint",landing); return
            end
            -- A failed route segment must not be selected forever. Retry after a
            -- bounded pause; ordinary local obstacles are handled above.
            if state.plan then waitRetry(agent,state,now,"RouteSegmentStuck"); return end
            choosePlan(agent,state,foot,goal,height,radius,ray,now,landing,rise,speed)
            if state.climb or not state.plan then return end
            state.planKind=state.mode; point=state.plan[1]
        end
    end
    if diagnosticAttributes then
        local debugPoint=if state.plan then point else nil
        if agent.model:GetAttribute("MonsterRecoveryPoint")~=debugPoint then agent.model:SetAttribute("MonsterRecoveryPoint",debugPoint) end
    end
    move(agent,state,point+offset,movementSpeed(state,speed),now)
end
return table.freeze(Navigation)
