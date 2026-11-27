-- The only ComputeAsync admission point. Results are consumed by the original
-- navigation owner on its next decision; workers never write movement state.
local PathfindingService = game:GetService("PathfindingService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Options = require(Shared:WaitForChild("GameOptions"))
local Queue = require(script.Parent:WaitForChild("NavigationRequestQueue"))
local settings = Options.NavigationBudgetSettings()
local queue = Queue.new(os.clock, task.spawn, function(err)
    warn("[game1][navigation] " .. tostring(err))
end, settings.concurrent, settings.startsPerSecond)
local Scheduler = {}

function Scheduler.Dispose(result)
    if result and result.path then result.path:Destroy() end
end

function Scheduler.Request(owner, root, destination)
    local ticket = queue:Request(owner, function(request)
        if not root.Parent then return nil end
        local origin = root.Position
        local goal = request.destination
        local path = PathfindingService:CreatePath({AgentRadius = 1, AgentHeight = 4, AgentCanJump = false, WaypointSpacing = 3})
        local ok, err = pcall(function() path:ComputeAsync(origin, goal) end)
        if not ok or path.Status ~= Enum.PathStatus.Success then
            path:Destroy()
            if not ok then warn("[game1][navigation] ComputeAsync: " .. tostring(err)) end
            return {origin=origin, destination=goal}
        end
        return {origin=origin, destination=goal, path=path}
    end, Scheduler.Dispose)
    if ticket then ticket.destination = destination end
    return ticket
end

function Scheduler.UpdateQueued(ticket, destination)
    if ticket.status == "Queued" then ticket.destination = destination end
end

function Scheduler.Cancel(ticket) queue:Cancel(ticket) end
function Scheduler.Take(ticket) return queue:Take(ticket) end
function Scheduler.Pump() queue:Pump() end

-- Movement of either endpoint invalidates a computed path. Consumers also
-- check goal identity and lifecycle before taking a result.
function Scheduler.IsStale(result, root, requested, current, tolerance)
    return ((result and result.destination or requested)-current).Magnitude >= tolerance
        or (result and (result.origin-root.Position).Magnitude >= tolerance)
end

return table.freeze(Scheduler)
