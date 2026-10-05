local CharacterMovementConfig = {}

-- gameplay movement stat. 50 preserves the current game1 baseline movement feel.
CharacterMovementConfig.DefaultRunStat = 50
CharacterMovementConfig.DefaultRobloxRunSpeed = 16
CharacterMovementConfig.DefaultRobloxWalkSpeed = 9

function CharacterMovementConfig.Resolve(_archetype: any): any
    return {
        groundWalk = CharacterMovementConfig.DefaultRobloxWalkSpeed,
        groundRun = CharacterMovementConfig.DefaultRobloxRunSpeed,
    }
end

function CharacterMovementConfig.MovementMultiplier(_archetype: any, currentRunSpeed: any): number
    local value = math.max(0, tonumber(currentRunSpeed) or CharacterMovementConfig.DefaultRunStat)
    return value / CharacterMovementConfig.DefaultRunStat
end

function CharacterMovementConfig.ResolveSpeed(archetype: any, currentRunSpeed: any, movementMode: any): number
    local base = if tostring(movementMode) == "Walk"
        then CharacterMovementConfig.DefaultRobloxWalkSpeed
        else CharacterMovementConfig.DefaultRobloxRunSpeed
    return base * CharacterMovementConfig.MovementMultiplier(archetype, currentRunSpeed)
end

function CharacterMovementConfig.RobloxSpeed(archetype: any, currentRunSpeed: any, movementMode: any): number
    return CharacterMovementConfig.ResolveSpeed(archetype, currentRunSpeed, movementMode)
end

return table.freeze(CharacterMovementConfig)
