-- Action fingers are not joystick/pinch fingers. One owns drag at a time.
-- Engine-free state; position values need only subtraction and Magnitude.
local Touches = {}
function Touches.New()
    local entries = {}
    local dragOwner = nil
    local state = {}
    function state.Begin(input, kind, position, onTap)
        if entries[input] then return false end
        entries[input] = {kind = kind, position = position, travel = 0, onTap = onTap}
        return true
    end
    function state.Has(input) return entries[input] ~= nil end
    function state.Held(kind)
        for _, entry in pairs(entries) do if entry.kind == kind then return true end end
        return false
    end
    function state.Move(input, position)
        local entry = entries[input]
        if not entry then return nil end
        local delta = position - entry.position
        entry.position = position
        entry.travel = entry.travel + delta.Magnitude
        if delta.Magnitude > 0 and dragOwner == nil then dragOwner = input end
        if dragOwner == input then return delta end
        return nil
    end
    function state.Finish(input)
        local entry = entries[input]
        if not entry then return nil, false, nil end
        entries[input] = nil
        if dragOwner == input then dragOwner = nil end
        return entry.kind, entry.travel <= 8, entry.onTap
    end
    function state.Clear()
        table.clear(entries)
        dragOwner = nil
    end
    return state
end
return table.freeze(Touches)
