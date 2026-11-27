-- Bounded async FULL acquisition. Slots include detached results waiting for
-- the shared scheduler; completion never publishes geometry. No frame loop.
local Requests = {}
Requests.__index = Requests
local MAX_PENDING = 4
local RETRY_SECONDS = 15
Requests.RetrySeconds = RETRY_SECONDS

function Requests.new(clock, spawn, load, dispose, report)
    return setmetatable({clock=clock, spawn=spawn, load=load, dispose=dispose,
        report=report, slots={}, count=0, destroyed=false}, Requests)
end

function Requests:_release(record, slot)
    if self.slots[record] ~= slot then return end
    self.slots[record] = nil
    self.count = self.count - 1
    if slot.result then self.dispose(slot.result); slot.result = nil end
end

function Requests:Invalidate(record)
    local slot = self.slots[record]
    -- In-flight calls cannot be cancelled. Keep their concurrency reservation
    -- until they return; invalidate their ticket instead of starting duplicates.
    if slot then
        slot.cancelled = true
        if not slot.loading then self:_release(record, slot) end
    end
end

function Requests:Prune(record)
    local slot = self.slots[record]
    if slot and not slot.cancelled and not slot.current(slot.ticket) then self:Invalidate(record) end
end

function Requests:TakeOrStart(record, current)
    if self.destroyed then return nil end
    self:Prune(record)
    local slot = self.slots[record]
    if slot then
        if slot.loading then return nil end
        if slot.cancelled or not current(slot.ticket) then
            self:_release(record, slot)
            return nil
        end
        local result = slot.result
        slot.result = nil
        self:_release(record, slot)
        return result
    end
    if self.count >= MAX_PENDING or self.clock() < (record.retryAt or 0) then return nil end
    slot = {ticket=record.generation, loading=true, current=current}
    self.slots[record] = slot
    self.count = self.count + 1
    self.spawn(function()
        local ok, result = pcall(self.load, record)
        slot.loading = false
        if ok then slot.result = result end
        if self.destroyed or slot.cancelled or not current(slot.ticket) then
            self:_release(record, slot)
        elseif not ok or not result then
            record.retryAt = self.clock() + RETRY_SECONDS
            self.report(record, result)
            self:_release(record, slot)
        end
    end)
    return nil
end

function Requests:Backoff(record)
    record.retryAt = self.clock() + RETRY_SECONDS
end

function Requests:Destroy()
    self.destroyed = true
    for record in pairs(self.slots) do self:Invalidate(record) end
end

return Requests
