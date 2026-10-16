-- NPC intent-to-locomotion policy. No Animator or Humanoid dependencies.
-- Attack pursuit retains weapon-specific SPEED, not a different combat gait.
local CharacterMovementConfig = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterMovementConfig"))

local NpcMovementPolicy = {}
NpcMovementPolicy.RecoverySeconds = 2

function NpcMovementPolicy.ModeFor(phase: string): string
    return if phase == "Combat" then "Run" else "Walk"
end

function NpcMovementPolicy.SpeedFor(runSpeed: any, phase: string): number
    return CharacterMovementConfig.RobloxSpeed(nil, runSpeed, NpcMovementPolicy.ModeFor(phase))
end

return table.freeze(NpcMovementPolicy)
