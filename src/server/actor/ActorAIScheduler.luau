-- One server heartbeat for periodic combat decisions. Frame-rate attack
-- pursuit, damage events, timers and all navigation policies remain owned by
-- their existing services. The queue permits yielding Legacy path requests.
local RunService = game:GetService("RunService")
local Queue = require(script.Parent:WaitForChild("ActorAIScheduleQueue"))
local queue = Queue.new(os.clock, task.spawn, function(err)
    warn("[game1][actor-ai] decision failed: " .. tostring(err))
end)
local ActorAIScheduler = {}
local connection

function ActorAIScheduler.Register(agent, interval, delay, step, onStop, phaseLocked)
    local registered = queue:Register(agent, interval, delay, step, onStop, phaseLocked)
    if not connection then
        connection = RunService.Heartbeat:Connect(function()
            queue:Pump(os.clock())
        end)
    end
    return registered
end

function ActorAIScheduler.Remove(agent)
    queue:Remove(agent)
end

return table.freeze(ActorAIScheduler)
