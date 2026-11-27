-- One synchronous pending transition per placement. No new scheduler/worker.
-- Desired and Actual remain on the placement; a fallback can differ from Desired.
local Queue = {}
Queue.__index = Queue
local AGE_TICKS = 8 -- two seconds at the existing 0.25 s observation interval

function Queue.new(sortTransitions)
    return setmetatable({entries={}, ordered={}, tick=0, dirty=false, sort=sortTransitions}, Queue)
end

function Queue:Begin(position, force)
    self.tick = self.tick + 1
    if force or self.position ~= position then self.dirty = true end
    self.position = position
end

function Queue:Remove(record)
    if self.entries[record] then
        self.entries[record] = nil
        self.dirty = true
    end
end

function Queue:Set(record, variant, prototype)
    if not variant or variant == record.actual then self:Remove(record); return end
    local entry = self.entries[record]
    if entry and entry.desired == record.desired and entry.variant == variant
        and entry.prototype == prototype and entry.actual == record.actual then return end
    self.entries[record] = {record=record, desired=record.desired, actual=record.actual,
        variant=variant, prototype=prototype, queuedAt=self.tick, aged=false}
    self.dirty = true
end

function Queue:Ordered(distance)
    for _, entry in pairs(self.entries) do
        local aged = self.tick - entry.queuedAt >= AGE_TICKS
        if entry.aged ~= aged then entry.aged = aged; self.dirty = true end
    end
    if self.dirty then
        local ordered = {}
        for _, entry in pairs(self.entries) do
            distance(entry.record, self.position)
            ordered[#ordered+1] = entry
        end
        self.sort(ordered)
        self.ordered = ordered
        self.dirty = false
    end
    return self.ordered
end

function Queue:Attempted(entry)
    -- A missing composite proxy is retried, but must not monopolize an aged
    -- reservation or prevent other requests from receiving a turn.
    if self.entries[entry.record] ~= entry then return end
    if entry.aged then self.dirty = true end
    entry.queuedAt = self.tick
    entry.aged = false
end

return Queue
