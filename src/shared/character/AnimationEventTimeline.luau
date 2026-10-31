--!strict
-- Pure cursor. Call with the track's TimePosition and DidLoop count, never wall time.
local Timeline = {}
Timeline.__index = Timeline

function Timeline.new(document: any)
    return setmetatable({document = document, position = -1e-8, cycle = 0, started = false}, Timeline)
end

function Timeline:Reset()
    self.position = -1e-8
    self.cycle = 0
    self.started = false
end

function Timeline:Advance(position: number, cycle: number, seek: boolean?): ({any}, boolean)
    local duration = self.document.duration or ((self.document.frame_end-self.document.frame_start)/self.document.fps)
    position = math.clamp(position, 0, duration)
    local previous, oldCycle = self.position, self.cycle
    local discontinuity = seek == true or cycle < oldCycle or (cycle == oldCycle and position < previous-1e-6)
    self.position, self.cycle = position, cycle
    self.started = true
    local fired = {}
    if discontinuity then
        -- Seek reconstructs persistent state only. It never replays missed blinks.
        for _, event in self.document.events do
            if event.time <= position and event.name ~= "blink" then table.insert(fired, event) end
        end
        return fired, true
    end
    -- Bound work after a hitch: skip obsolete full cycles, deliver at most tail + current.
    if cycle > oldCycle then
        for _, event in self.document.events do
            if event.time > previous then table.insert(fired, event) end
        end
        previous = -1e-8
    end
    for _, event in self.document.events do
        if event.time > previous and event.time <= position then table.insert(fired, event) end
    end
    return fired, false
end

return table.freeze(Timeline)
