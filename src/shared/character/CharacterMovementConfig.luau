local CharacterMovementConfig = {}

-- RunSpeed is a world-space movement speed in studs/second for every moving
-- entity. Walking is always exactly half of that stat. Keep the compatibility
-- method names because both ControllerManager characters and Humanoid monsters
-- consume this shared contract.
CharacterMovementConfig.DefaultRunSpeed = 50
CharacterMovementConfig.WalkSpeedMultiplier = 0.5

function CharacterMovementConfig.Resolve(_archetype: any): any
    return {
        groundWalk = CharacterMovementConfig.DefaultRunSpeed * CharacterMovementConfig.WalkSpeedMultiplier,
        groundRun = CharacterMovementConfig.DefaultRunSpeed,
    }
end

function CharacterMovementConfig.MovementMultiplier(_archetype: any, currentRunSpeed: any): number
    local value = math.max(0, tonumber(currentRunSpeed) or CharacterMovementConfig.DefaultRunSpeed)
    return value / CharacterMovementConfig.DefaultRunSpeed
end

function CharacterMovementConfig.ResolveSpeed(_archetype: any, currentRunSpeed: any, movementMode: any): number
    local runSpeed = math.max(0, tonumber(currentRunSpeed) or CharacterMovementConfig.DefaultRunSpeed)
    if tostring(movementMode) == "Walk" then
        return runSpeed * CharacterMovementConfig.WalkSpeedMultiplier
    end
    return runSpeed
end

function CharacterMovementConfig.RobloxSpeed(archetype: any, currentRunSpeed: any, movementMode: any): number
    return CharacterMovementConfig.ResolveSpeed(archetype, currentRunSpeed, movementMode)
end

return table.freeze(CharacterMovementConfig)
