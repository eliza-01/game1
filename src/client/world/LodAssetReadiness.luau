-- Admission to atomic visual commit, not another assembly scheduler.
-- A cancelled job never publishes and its shared fetch holds its real slot
-- until the engine returns. The shared preloader bounds waiting to 25 seconds.
local Readiness = {}
Readiness.__index = Readiness

function Readiness.new(preload, spawn, clock, report)
    return setmetatable({preload=preload, spawn=spawn, clock=clock, report=report}, Readiness)
end

function Readiness:Ready(job)
    local ticket = job.assetFetch
    if ticket then return ticket.done end
    ticket = {done=false}
    job.assetFetch = ticket
    self.spawn(function()
        local function current() return job.state == "ready" and job.assetFetch == ticket end
        if not current() then return end
        local ok, all, geometry = pcall(self.preload, job.bundle, current)
        if not current() then return end
        ticket.success = ok and all == true
        ticket.geometry = ok and geometry == true
        ticket.done = true
        -- Native rendering fallback after a real failure/deadline. Do not
        -- count this as confirmed ready, or permanently block the map.
        if not ticket.success then
            if not self.lastWarning or self.clock() - self.lastWarning >= 15 then
                self.lastWarning = self.clock()
                self.report(ok and "asset fetch failed or deadline reached; native fallback" or tostring(all))
            end
        end
    end)
    return ticket.done
end

return Readiness
