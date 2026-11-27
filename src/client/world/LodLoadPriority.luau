-- Near-to-far admission for the existing shared Runtime queue. No worker,
-- asset fetch or LOD decision here. Distances are to authored visual bounds.
local Priority = {}
Priority.__index = Priority
Priority.BandStuds = 32
Priority.WaitSeconds = 4

function Priority.new(clock)
    return setmetatable({clock=clock, waiting={}, expired={}}, Priority)
end

function Priority.Distance(record, position, surfaceDistance)
    if record.house then return surfaceDistance(position, record.worldFrame, record.worldSize) end
    local distance = math.huge
    for _, bounds in ipairs(record.fullBounds) do
        distance = math.min(distance, surfaceDistance(position, bounds.CFrame, bounds.Size))
    end
    return distance
end

function Priority:Sample(record, position, surfaceDistance)
    if record.loadPosition ~= position then
        record.loadDistance = Priority.Distance(record, position, surfaceDistance)
        record.loadBand = math.floor(record.loadDistance / Priority.BandStuds)
        record.loadPosition = position
    end
    return record.loadDistance
end

function Priority:Observe(records, position, surfaceDistance, reset)
    if reset then self.waiting, self.expired = {}, {} end
    local now = self.clock()
    local frontier = nil
    local progress = false
    for record in pairs(self.waiting) do
        if record.actual ~= "UNLOADED" and record.desired ~= "UNLOADED" and record.loadBand == self.frontier then
            progress = true
            break
        end
    end
    local cold = {}
    local waiting, expired = {}, {}
    for _, record in ipairs(records) do
        if record.desired ~= "UNLOADED" and record.actual == "UNLOADED" then
            self:Sample(record, position, surfaceDistance)
            local since = record.loadBand == self.frontier and self.waiting[record] or nil
            -- Slow but progressing bands keep their priority; only a stall
            -- lets the following band through.
            if progress and record.loadBand == self.frontier and since then since = now end
            if self.expired[record] or (since and now - since >= Priority.WaitSeconds) then
                expired[record] = true
            else
                cold[#cold+1] = record
                if since then waiting[record] = since end
                frontier = math.min(frontier or record.loadBand, record.loadBand)
            end
        end
    end
    -- Start each deadline only when that record reaches the nearest open band.
    -- Unavailable roots/templates do not hold the rest of the map forever.
    for _, record in ipairs(cold) do
        if record.loadBand == frontier then
            waiting[record] = waiting[record] or now
        else
            waiting[record] = nil
        end
    end
    self.waiting, self.expired, self.frontier = waiting, expired, frontier
end

function Priority:Allows(record)
    return self.frontier == nil or record.loadBand == nil or record.loadBand <= self.frontier
end

return Priority
