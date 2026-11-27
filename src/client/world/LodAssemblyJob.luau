-- Detached visual preparation. A work unit is an explicit non-yielding operation
-- (clone, configure, parent, bounds contribution, weld creation, etc.).
-- The coroutine is resumed only by the owning scheduler, never by task.spawn.
local Job = {}
Job.__index = Job

function Job.new(build)
    local self = setmetatable({state = "building", owned = {}, units = 0}, Job)
    self.thread = coroutine.create(function() build(self) end)
    return self
end

function Job:Own(instance, kind)
    self.owned[#self.owned+1] = instance
    if kind and self.diagnostics and self.diagnostics.enabled then self.diagnostics:Add(kind) end
    return instance
end

function Job:Unit()
    coroutine.yield()
end

function Job:Advance(limit)
    local used = 0
    while self.state == "building" and used < limit do
        used = used + 1
        local ok, problem = coroutine.resume(self.thread)
        if not ok then
            self.state, self.problem = "failed", problem
        elseif coroutine.status(self.thread) == "dead" then
            self.state = "ready"
        end
    end
    self.units = self.units + used
    return used
end

function Job:Release()
    assert(self.state == "ready", "only a ready assembly may be published")
    self.state = "committed"
    self.owned = {}
    self.thread = nil
    return self.bundle
end

-- Ownership list is creation ordered: children are disposed before containers.
-- On cancellation even a clone not yet parented belongs to the job.
function Job:Cancel()
    assert(self.state ~= "committed", "committed assembly belongs to placement")
    self.state = "cancelled"
    self.thread = nil
    local owned = self.owned
    self.owned = {}
    return owned
end

-- Studio authoring uses the same builder without Runtime's frame scheduler.
function Job:Finish()
    while self.state == "building" do self:Advance(64) end
    if self.state == "ready" then return self:Release() end
    local problem = self.problem
    local owned = self:Cancel()
    for i = #owned, 1, -1 do owned[i]:Destroy() end
    return nil, problem
end

return Job
