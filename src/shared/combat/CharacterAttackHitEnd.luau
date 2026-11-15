-- Character melee: HitEnd is the ONLY gameplay collision checkpoint.
-- The authored normalized position is converted to server attack time by
-- AttackTimelineConfig. HitStart is not consulted for damage.
local CharacterAttackHitEnd = {}

function CharacterAttackHitEnd.Resolve(timing: any): any?
    local hitEnd = timing and timing.events and timing.events.HitEnd
    local duration = tonumber(timing and timing.duration)
    local time = tonumber(hitEnd and hitEnd.time)
    if not duration or duration <= 0 or not time
        or time < 0 or time > duration then
        return nil
    end
    return table.freeze({ time = time })
end

return table.freeze(CharacterAttackHitEnd)
