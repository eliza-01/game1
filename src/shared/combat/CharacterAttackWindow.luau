-- Character-only melee damage-window policy.
--
-- A character weapon may deal damage continuously from authored HitStart
-- through authored HitEnd. Monster attacks intentionally do not use this
-- module; their current gameplay still resolves one authored Hit checkpoint.
local CharacterAttackWindow = {}

function CharacterAttackWindow.Resolve(timing: any): any?
    local events = timing and timing.events
    local hitStart = events and events.HitStart
    local hitEnd = events and events.HitEnd
    if type(hitStart) ~= "table" or type(hitEnd) ~= "table" then
        return nil
    end

    local duration = math.max(0, tonumber(timing.duration) or 0)
    local startTime = tonumber(hitStart.time)
    local endTime = tonumber(hitEnd.time)
    if startTime == nil or endTime == nil then
        return nil
    end

    startTime = math.clamp(startTime, 0, duration)
    endTime = math.clamp(endTime, 0, duration)
    if startTime > endTime then
        return nil
    end

    return table.freeze({
        startTime = startTime,
        endTime = endTime,
    })
end

return table.freeze(CharacterAttackWindow)
