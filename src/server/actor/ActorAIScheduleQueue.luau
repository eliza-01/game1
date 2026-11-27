-- Deadline queue; no world, combat or movement dependencies. Injected clock
-- and dispatcher allow deterministic tests, including yielding decisions.
local Queue = {}
Queue.__index = Queue

local function earlier(a, b)
    return a.due < b.due or (a.due == b.due and a.order < b.order)
end

local function swap(heap, a, b)
    heap[a], heap[b] = heap[b], heap[a]
    heap[a].index, heap[b].index = a, b
end

local function up(heap, i)
    while i > 1 do
        local parent = math.floor(i / 2)
        if not earlier(heap[i], heap[parent]) then break end
        swap(heap, i, parent)
        i = parent
    end
end

local function down(heap, i)
    while i * 2 <= #heap do
        local child = i * 2
        if child + 1 <= #heap and earlier(heap[child + 1], heap[child]) then child = child + 1 end
        if not earlier(heap[child], heap[i]) then break end
        swap(heap, i, child)
        i = child
    end
end

local function unlink(heap, entry)
    local i = entry.index
    if not i then return end -- already running
    local last = table.remove(heap)
    entry.index = nil
    if last == entry then return end
    heap[i], last.index = last, i
    if i > 1 and earlier(last, heap[math.floor(i / 2)]) then up(heap, i) else down(heap, i) end
end

function Queue.new(clock, dispatch, report)
    return setmetatable({clock = clock, dispatch = dispatch, report = report, heap = {}, entries = {}, serial = 0}, Queue)
end

function Queue:_enqueue(entry, due)
    self.serial = self.serial + 1
    entry.due, entry.order = due, self.serial
    local heap = self.heap
    entry.index = #heap + 1
    heap[entry.index] = entry
    up(heap, entry.index)
end

function Queue:Register(key, interval, delay, step, onStop, phaseLocked)
    assert(interval > 0 and delay > 0, "positive AI cadence required")
    if self.entries[key] then return false end
    local entry = {key = key, interval = interval, step = step, onStop = onStop, phaseLocked = phaseLocked}
    self.entries[key] = entry
    self:_enqueue(entry, self.clock() + delay)
    return true
end

function Queue:Remove(key)
    local entry = self.entries[key]
    if not entry then return end
    self.entries[key] = nil
    unlink(self.heap, entry)
end

local function run(self, entry)
    if self.entries[entry.key] ~= entry then return end
    local ok, result = xpcall(entry.step, debug.traceback, entry.key, self.clock())
    if not ok then self.report(result) end
    -- A yielding step may have been removed/replaced by its lifecycle owner.
    if self.entries[entry.key] ~= entry then return end
    if (ok and result == false) or (not ok and entry.onStop) then
        self:Remove(entry.key)
        if entry.onStop then
            local stopped, err = xpcall(entry.onStop, debug.traceback, entry.key)
            if not stopped then self.report(err) end
        end
        return
    end
    -- Completion-based cadence matches the old monster wait loop. No catch-up
    -- bursts or concurrent periodic decisions after a slow/yielding step.
    local finishedAt = self.clock()
    local nextDue = finishedAt + entry.interval
    if entry.phaseLocked then
        -- NPC previously carried the fractional Heartbeat remainder forward.
        -- Keep its nominal phase without replaying missed decision ticks.
        nextDue = entry.due + entry.interval
        if nextDue <= finishedAt then
            nextDue = nextDue + (math.floor((finishedAt - nextDue) / entry.interval) + 1) * entry.interval
        end
    end
    self:_enqueue(entry, nextDue)
end

function Queue:Pump(now)
    local heap = self.heap
    while heap[1] and heap[1].due <= now do
        local entry = heap[1]
        unlink(heap, entry)
        self.dispatch(run, self, entry)
    end
end

return Queue
