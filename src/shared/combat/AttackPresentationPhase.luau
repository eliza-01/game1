-- Server-clock presentation state. No damage, hit detection or movement authority.
local Phase = { Attribute = "Game1AttackPresentation" }

function Phase.Resolve(state, now)
    local duration = state.duration
    if state.bounceAt then
        local reverse = state.reverseSpeed
        local position = math.max(0, state.bouncePhase - math.max(0, now - state.bounceAt) * reverse / duration)
        return position, (position > 0 and -reverse or 0), state.endAt
    end
    return math.clamp((now - state.startAt) / duration, 0, 1), 1, state.endAt
end

return table.freeze(Phase)
