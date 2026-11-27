-- Encounter-local fallback policy. No world queries, movement or background task.
local Blocked={}
local function horizontal(v) return Vector3.new(v.X,0,v.Z) end
local function distance(a,b) return horizontal(a-b).Magnitude end
local ARRIVAL=1
local PROGRESS=.25
local STALL_SECONDS=2

function Blocked.Begin(state)
    state.blockedPursuit={phase="Retreat"}
end

local function waitAt(b,d,range,now)
    b.phase="Wait"; b.waitAt=now; b.point=nil; b.armed=d>range
    return "Wait"
end

function Blocked.Step(state,position,target,range,buffer,now,speed,findPoint)
    local b=state.blockedPursuit
    local d=distance(position,target)
    if b.phase=="Wait" then
        if d>range then b.armed=true end
        if b.armed and d<=range then return "Reengage" end
        return "Wait"
    end
    if d>=range+buffer then return waitAt(b,d,range,now) end
    if speed<=.01 then
        b.point=nil; b.progressAt=nil
        return "Retreat"
    end
    if b.point then
        if distance(position,b.anchor)>=PROGRESS then b.anchor=position; b.progressAt=now end
        if now-b.progressAt>=STALL_SECONDS then return waitAt(b,d,range,now) end
        if distance(position,b.point)>ARRIVAL then return "Retreat",b.point end
    end
    local point=findPoint(position,target,range+buffer)
    if not point then return waitAt(b,d,range,now) end
    b.point=point; b.anchor=position; b.progressAt=now
    return "Retreat",point
end

function Blocked.WaitSeconds(state,now)
    local b=state.blockedPursuit
    return b and b.waitAt and math.max(0,now-b.waitAt) or 0
end

function Blocked.IsRetreating(state)
    return state~=nil and state.blockedPursuit~=nil and state.blockedPursuit.phase=="Retreat"
end
return table.freeze(Blocked)
