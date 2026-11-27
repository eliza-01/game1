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

-- Original unload-first and nearest-first priority. The old sort did not
-- specify ties; immutable manifest ordinal makes equal distances deterministic.
function Candidates.SortTransitions(transitions)
    if #transitions < 2 then return end
    table.sort(transitions, function(a, b)
        local ar, br = a.record, b.record
        local aUnload = ar.desired == "UNLOADED" and ar.actual ~= "UNLOADED"
        local bUnload = br.desired == "UNLOADED" and br.actual ~= "UNLOADED"
        if aUnload ~= bUnload then return aUnload end
        if a.aged ~= b.aged then return a.aged == true end
        if a.aged and a.queuedAt ~= b.queuedAt then return a.queuedAt < b.queuedAt end
        if ar.distance == br.distance then return ar.order < br.order end
        return ar.distance < br.distance
    end)
end

return Candidates
