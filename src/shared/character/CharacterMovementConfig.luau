local CharacterMovementConfig = {}

-- RunSpeed is a game-design stat, not a Roblox world velocity.
-- Canonical conversion: 10 RunSpeed units == 1 stud/second.
-- Walking always uses exactly half of the current RunSpeed stat.
CharacterMovementConfig.DefaultRunSpeed = 50
CharacterMovementConfig.WalkSpeedMultiplier = 0.5
CharacterMovementConfig.RunSpeedUnitsPerStud = 10

local function gameSpeed(currentRunSpeed: any, movementMode: any): number
    local runSpeed = math.max(0, tonumber(currentRunSpeed) or CharacterMovementConfig.DefaultRunSpeed)
    if tostring(movementMode) == "Walk" then
        return runSpeed * CharacterMovementConfig.WalkSpeedMultiplier
    end
    return runSpeed
end

function CharacterMovementConfig.Resolve(_archetype: any): any
    return {
        groundWalk = CharacterMovementConfig.RobloxSpeed(nil, CharacterMovementConfig.DefaultRunSpeed, "Walk"),
        groundRun = CharacterMovementConfig.RobloxSpeed(nil, CharacterMovementConfig.DefaultRunSpeed, "Run"),
    }
end

function CharacterMovementConfig.MovementMultiplier(_archetype: any, currentRunSpeed: any): number
    local value = math.max(0, tonumber(currentRunSpeed) or CharacterMovementConfig.DefaultRunSpeed)
    return value / CharacterMovementConfig.DefaultRunSpeed
end

-- Returns the game-design speed value for the requested locomotion mode.
function CharacterMovementConfig.ResolveSpeed(_archetype: any, currentRunSpeed: any, movementMode: any): number
    return gameSpeed(currentRunSpeed, movementMode)
end

-- Returns the actual Roblox world velocity in studs/second.
function CharacterMovementConfig.RobloxSpeed(_archetype: any, currentRunSpeed: any, movementMode: any): number
    return gameSpeed(currentRunSpeed, movementMode) / CharacterMovementConfig.RunSpeedUnitsPerStud
end


function CharacterMovementConfig.RobloxSpeedAtRunMultiplier(_archetype: any, currentRunSpeed: any, runSpeedMultiplier: any): number
    local runSpeed = math.max(0, tonumber(currentRunSpeed) or CharacterMovementConfig.DefaultRunSpeed)
    local multiplier = math.max(0, tonumber(runSpeedMultiplier) or 1)
    return (runSpeed * multiplier) / CharacterMovementConfig.RunSpeedUnitsPerStud
end

-- Converts an arbitrary attack movement speed back into the equivalent RunSpeed
-- value expected by a Run/Walk animation scaling rule. Example: attack movement
-- at 75% RunSpeed with Walk legs => 1.5x the normal Walk cadence because normal
-- Walk moves at 50% RunSpeed.
function CharacterMovementConfig.EquivalentRunSpeedForLocomotion(currentRunSpeed: any, runSpeedMultiplier: any, locomotionMode: any): number
    local runSpeed = math.max(0, tonumber(currentRunSpeed) or CharacterMovementConfig.DefaultRunSpeed)
    local multiplier = math.max(0, tonumber(runSpeedMultiplier) or 1)
    local modeMultiplier = if tostring(locomotionMode) == "Walk" then CharacterMovementConfig.WalkSpeedMultiplier else 1
    return (runSpeed * multiplier) / math.max(0.001, modeMultiplier)
end

function CharacterMovementConfig.StudsPerSecond(archetype: any, currentRunSpeed: any, movementMode: any): number
    return CharacterMovementConfig.RobloxSpeed(archetype, currentRunSpeed, movementMode)
end

function CharacterMovementConfig.RunSpeedFromStudsPerSecond(studsPerSecond: any): number
    return math.max(0, tonumber(studsPerSecond) or 0) * CharacterMovementConfig.RunSpeedUnitsPerStud
end

return table.freeze(CharacterMovementConfig)
