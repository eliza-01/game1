local CharacterMovementConfig = {}
CharacterMovementConfig.DefaultRunSpeed = 16
CharacterMovementConfig.DefaultWalkSpeed = 9
function CharacterMovementConfig.Resolve(_archetype: any): any
    return { groundWalk = CharacterMovementConfig.DefaultWalkSpeed, groundRun = CharacterMovementConfig.DefaultRunSpeed }
end
function CharacterMovementConfig.MovementMultiplier(_archetype: any, _currentMoveSpeed: any): number return 1 end
function CharacterMovementConfig.ResolveSpeed(_archetype: any, _currentMoveSpeed: any, movementMode: any): number
    return if tostring(movementMode) == "Walk" then CharacterMovementConfig.DefaultWalkSpeed else CharacterMovementConfig.DefaultRunSpeed
end
function CharacterMovementConfig.RobloxSpeed(archetype: any, currentMoveSpeed: any, movementMode: any): number
    return CharacterMovementConfig.ResolveSpeed(archetype, currentMoveSpeed, movementMode)
end
return table.freeze(CharacterMovementConfig)
