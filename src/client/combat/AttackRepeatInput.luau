-- Input intent only. The attack timeline and server still own attack acceptance.
local Repeat = {}
function Repeat.New()
    local sources = {}
    local automatic = false
    local nextAttempt = 0
    local state = {}
    function state.SetHeld(source, held)
        sources[source] = held and true or nil
        if held then nextAttempt = 0 end
    end
    function state.SetAutomatic(enabled)
        automatic = enabled
        if enabled then nextAttempt = 0 end
    end
    function state.Clear()
        table.clear(sources)
        automatic = false
        nextAttempt = 0
    end
    function state.IsActive() return automatic or next(sources) ~= nil end
    function state.NoteAttempt(now) nextAttempt = now + 0.1 end
    function state.ShouldAttempt(now, busy)
        if busy or not state.IsActive() or now < nextAttempt then return false end
        -- Retry only outside the active timeline; cap rejected local attempts.
        state.NoteAttempt(now)
        return true
    end
    return state
end
return table.freeze(Repeat)
