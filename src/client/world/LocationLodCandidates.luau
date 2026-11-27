-- Resolve only spatial candidates and previous live/desired records. A record
-- omitted in an earlier sample was necessarily UNLOADED under the old policy.
local Candidates = {}
Candidates.__index = Candidates

function Candidates.new(index)
    return setmetatable({index=index, retained={}, sampled=false}, Candidates)
end

function Candidates:Collect(position, force)
    if not force and self.position == position and self.localRecords then return self.localRecords end
    local records = self.index:Query(position)
    local seen = {}
    for _, record in ipairs(records) do seen[record] = true end
    self.indexed = seen
    for record in pairs(self.retained) do
        if not seen[record] then records[#records+1] = record end
    end
    if self.sampled then
        for _, record in ipairs(records) do
            if record.desired == nil then record.desired = "UNLOADED" end
        end
    end
    self.sampled = true
    self.position, self.localRecords = position, records
    return records
end

function Candidates:Retain(records)
    local retained = {}
    local count = 0
    for _, record in ipairs(records) do
        if record.desired ~= "UNLOADED" or record.actual ~= "UNLOADED" or record.part then
            retained[record] = true
        end
        -- A cached stationary sample must not keep the previous teleport
        -- region forever after its last pending unload has completed.
        if self.indexed[record] or retained[record] then
            count = count + 1
            records[count] = record
        end
    end
    for i = #records, count + 1, -1 do records[i] = nil end
    self.retained = retained
end

-- Unloads remain independent. Nearest band and missing geometry precede
-- quality upgrades; aging is confined to a band and load class.
function Candidates.SortTransitions(transitions)
    if #transitions < 2 then return end
    table.sort(transitions, function(a, b)
        local ar, br = a.record, b.record
        local aUnload = ar.desired == "UNLOADED" and ar.actual ~= "UNLOADED"
        local bUnload = br.desired == "UNLOADED" and br.actual ~= "UNLOADED"
        if aUnload ~= bUnload then return aUnload end
        local ab, bb = ar.loadBand or 0, br.loadBand or 0
        if ab ~= bb then return ab < bb end
        local ac, bc = ar.actual == "UNLOADED", br.actual == "UNLOADED"
        if ac ~= bc then return ac end
        if a.aged ~= b.aged then return a.aged == true end
        if a.aged and a.queuedAt ~= b.queuedAt then return a.queuedAt < b.queuedAt end
        local ad, bd = ar.loadDistance or ar.distance, br.loadDistance or br.distance
        if ad == bd then return ar.order < br.order end
        return ad < bd
    end)
end

return Candidates
