-- Exclusive bounded resource pool. No Roblox dependencies; reservations include
-- factories that may yield, and idle resources count toward the resident limit.
local Pool = {}
Pool.__index = Pool

function Pool.new(limit, ttl, clock)
    assert(limit >= 1 and ttl >= 0)
    return setmetatable({limit = limit, ttl = ttl, clock = clock, resident = 0,
        records = {}, idle = {}, lastCleanup = -math.huge}, Pool)
end

function Pool:_destroy(sampler)
    self.idle[sampler] = nil
    self.records[sampler] = nil
    self.resident = self.resident - 1
    sampler:Destroy()
end

function Pool:Acquire(key, factory, speed, phase)
    local oldest, matching
    for sampler, record in pairs(self.idle) do
        if record.key == key then matching = sampler; break end
        if not oldest or record.releasedAt < self.idle[oldest].releasedAt then oldest = sampler end
    end
    if matching then
        self.idle[matching] = nil -- reserve before Resume (which may yield)
        local ok, err = pcall(matching.Resume, matching, speed, phase)
        if not ok then self:_destroy(matching); return nil, tostring(err) end
        return matching
    end
    if self.resident >= self.limit then
        if not oldest then return nil, "budget" end
        self:_destroy(oldest)
    end
    self.resident = self.resident + 1 -- reserve before factory/LoadAnimation
    local ok, sampler, reason = pcall(factory)
    if not ok or not sampler then
        self.resident = self.resident - 1
        return nil, tostring(ok and reason or sampler)
    end
    self.records[sampler] = {key = key}
    return sampler
end

function Pool:Release(sampler)
    local record = self.records[sampler]
    if not record or self.idle[sampler] then return end
    local ok = pcall(sampler.Suspend, sampler)
    if not ok then self:_destroy(sampler); return end
    record.releasedAt = self.clock()
    self.idle[sampler] = record
end

function Pool:Cleanup(now)
    if now - self.lastCleanup < 1 then return end
    self.lastCleanup = now
    for sampler, record in pairs(self.idle) do
        if now - record.releasedAt >= self.ttl then self:_destroy(sampler) end
    end
end

return Pool
