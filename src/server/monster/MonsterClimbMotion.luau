local Shared=game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local CharacterConfig=require(Shared:WaitForChild("character"):WaitForChild("CharacterConfig"))
local JumpSettings=require(Shared:WaitForChild("GameOptions")).PlayerJumpSettings()
local Trace=require(script.Parent:WaitForChild("MonsterNavigationTrace"))
local Geometry=require(script.Parent:WaitForChild("MonsterRecoveryGeometry"))
-- One ordinary ballistic jump. The Humanoid keeps moving in the approach
-- direction; world gravity and normal physical collision remain in charge.
local Climb={}
local UP=Vector3.yAxis
local MAX_JUMP_SECONDS=1
local JUMP_VELOCITY=CharacterConfig.JumpVelocity*math.sqrt(JumpSettings.heightMultiplier)

local function grounded(agent)
    return agent.humanoid.FloorMaterial~=Enum.Material.Air
end
local function drive(agent,c,speed)
    agent.humanoid.WalkSpeed=speed
    agent.humanoid.AutoRotate=true
    agent.humanoid:Move(c.direction,false)
    agent.navigating=true
end
local function launch(agent,c,speed,now)
    local root=agent.root
    -- Same takeoff vertical speed as the character. Add only the velocity
    -- difference, so an existing upward velocity cannot stack extra height.
    local velocity=root.AssemblyLinearVelocity
    local delta=c.direction*speed-Geometry.Horizontal(velocity)
        +UP*math.max(0,JUMP_VELOCITY-velocity.Y)
    c.launchedAt=now
    -- The navigation rig disables native Humanoid jumping. Use the same
    -- physical impulse as the character, not a second native jump impulse.
    agent.humanoid:ChangeState(Enum.HumanoidStateType.Freefall)
    root:ApplyImpulse(delta*root.AssemblyMass)
    Trace.Event(agent,"CLIMB_JUMP","verticalSpeed="..tostring(JUMP_VELOCITY),"forwardSpeed="..tostring(speed))
end

function Climb.Stop(state)
    local c=state.climb
    if not c then return end
    state.climb=nil
    -- Do not anchor, reposition, or erase airborne vertical momentum.
    if c.root.Parent and c.model:GetAttribute("LifeState")=="Alive" then
        c.humanoid:Move(Vector3.zero,false)
    end
end

function Climb.Begin(agent,state,landing,_rise,_params,now,speed)
    local root=agent.root
    if state.climb or root.Anchored or speed<=.01 then return false end
    local delta=Geometry.Horizontal(landing-root.Position)
    if delta.Magnitude<=.05 then return false end
    local c={root=root,model=agent.model,humanoid=agent.humanoid,landing=landing,direction=delta.Unit,startedAt=now}
    state.climb=c
    -- Replace the old MoveTo command before taking off.
    agent.humanoid:MoveTo(root.Position)
    drive(agent,c,speed)
    if grounded(agent) then launch(agent,c,speed,now) end
    return true
end

function Climb.Step(agent,state,speed,_params,now)
    local c=state.climb
    if not c or agent.root.Anchored or speed<=.01 then return "Failed" end
    if now-c.startedAt>=MAX_JUMP_SECONDS then
        Trace.Event(agent,"CLIMB_TIMEOUT")
        Climb.Stop(state)
        return "Timeout"
    end
    if c.launchedAt then
        -- FloorMaterial can remain stale immediately after the impulse.
        -- End only on landing, not on reaching the old estimated top point.
        if now-c.launchedAt>=CharacterConfig.JumpGroundIgnoreTime and grounded(agent)
            and agent.root.AssemblyLinearVelocity.Y<=0 then
            Trace.Event(agent,"CLIMB_LAND")
            Climb.Stop(state)
            return "Done"
        end
    elseif grounded(agent) then
        launch(agent,c,speed,now)
    end
    drive(agent,c,speed)
    return "Moving"
end
return table.freeze(Climb)
