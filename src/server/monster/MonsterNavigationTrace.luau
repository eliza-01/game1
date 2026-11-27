-- Studio-only opt-in observation. No additional spatial queries or movement.
local Workspace=game:GetService("Workspace")
local inStudio=game:GetService("RunService"):IsStudio()
local Trace={}
local records=setmetatable({}, {__mode="k"})
local owners=setmetatable({}, {__mode="kv"})
local serial=0
function Trace.Enabled(agent)
    if not inStudio or Workspace:GetAttribute("Game1MonsterNavTrace")~=true then return false end
    local filter=Workspace:GetAttribute("Game1MonsterNavTraceFilter")
    return not filter or filter=="" or string.find(agent.model.Name,tostring(filter),1,true)~=nil
end
local function record(agent)
    local rec=records[agent]
    if not rec then
        serial+=1; rec={id=serial,changes={},times={}}; records[agent]=rec
    end
    return rec
end
function Trace.V(v)
    if not v then return "nil" end
    return string.format("(%.2f,%.2f,%.2f)",v.X,v.Y,v.Z)
end
function Trace.Event(agent,event,...)
    if not Trace.Enabled(agent) then return end
    local rec=record(agent)
    print(string.format("[MONNAV #%d %s %.3f] %s",rec.id,agent.model.Name,os.clock(),event),...)
end
function Trace.Changed(agent,key,value,...)
    if not Trace.Enabled(agent) then return end
    local rec=record(agent)
    if rec.changes[key]==value then return end
    rec.changes[key]=value
    Trace.Event(agent,key,value,...)
end
function Trace.Rate(agent,key,seconds,...)
    if not Trace.Enabled(agent) then return end
    local rec=record(agent); local now=os.clock()
    if now<(rec.times[key] or -math.huge)+seconds then return end
    rec.times[key]=now
    Trace.Event(agent,key,...)
end
function Trace.Bind(params,agent)
    if Trace.Enabled(agent) then owners[params]=agent end
end
function Trace.Ray(params,label,origin,delta,result)
    local agent=owners[params]
    if not agent or not Trace.Enabled(agent) then return end
    local hit=result and result.Instance
    Trace.Event(agent,label,"from="..Trace.V(origin),"to="..Trace.V(origin+delta),
        string.format("length=%.2f",delta.Magnitude),"hit="..(hit and hit:GetFullName() or "NONE"),
        "hitPos="..Trace.V(result and result.Position),"distance="..tostring(result and result.Distance),
        "group="..tostring(params.CollisionGroup))
end
-- Detailed graph trace is separately opt-in: one search may have many
-- candidates. Edge metadata is observational; it never affects ranking.
function Trace.RouteObserver(agent,start,goal,radius)
    if not Trace.Enabled(agent) or Workspace:GetAttribute("Game1MonsterNavRouteTrace")~=true then return nil end
    Trace.Event(agent,"GRAPH_BEGIN","start="..Trace.V(start),"goal="..Trace.V(goal),
        string.format("searchRadius=%.2f exitLimit=%.2f",radius,(start-goal).Magnitude))
    local labels={}
    return function(stage,edge,point,distance,reason,result,cached)
        local label=labels[edge]
        if not label then
            local sources={}
            for source in pairs(edge.sources) do table.insert(sources,source) end
            table.sort(sources); label=table.concat(sources,","); labels[edge]=label
        end
        local hit=result and result.Instance
        Trace.Event(agent,stage,"edge="..edge.id,"route="..label,
            "point="..Trace.V(point),string.format("distance=%.3f",distance),
            "reason="..reason,"hit="..(hit and hit:GetFullName() or "NONE"),
            "hitPos="..Trace.V(result and result.Position),"cached="..tostring(cached==true))
    end
end
return table.freeze(Trace)
