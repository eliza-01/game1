-- One server heartbeat for periodic combat decisions. Frame-rate attack
-- pursuit, damage events, timers and all navigation policies remain owned by
-- their existing services. The queue permits yielding Legacy path requests.
local RunService = game:GetService("RunService")
local PlayerSpatialIndex = require(script.Parent:WaitForChild("PlayerSpatialIndex"))
local Queue = require(script.Parent:WaitForChild("ActorAIScheduleQueue"))
local queue = Queue.new(os.clock, task.spawn, function(err)
    warn("[game1][actor-ai] decision failed: " .. tostring(err))
end)
local ActorAIScheduler = {}
local connection

function ActorAIScheduler.Register(agent, interval, delay, step, onStop, phaseLocked, cadence)
    local registered = queue:Register(agent, interval, delay, step, onStop, phaseLocked, cadence)
    if not connection then
        connection = RunService.Heartbeat:Connect(function()
            PlayerSpatialIndex.BeginBatch()
            local ok, err = pcall(queue.Pump, queue, os.clock())
            PlayerSpatialIndex.EndBatch()
            if not ok then error(err, 0) end
        end)
    end
    return registered
end

function ActorAIScheduler.Wake(agent)
    queue:Wake(agent)
end

function ActorAIScheduler.Remove(agent)
    queue:Remove(agent)
end

return table.freeze(ActorAIScheduler)
