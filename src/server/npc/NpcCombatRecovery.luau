-- Per-NPC combat-disengage gate. Owned and ticked by NpcCombatAIService.
-- No tasks, remotes or event connections: death/unbind and re-aggro cancel it.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Policy = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("npc"):WaitForChild("NpcMovementPolicy"))

local NpcCombatRecovery = {}
NpcCombatRecovery.__index = NpcCombatRecovery

function NpcCombatRecovery.new()
    return setmetatable({ deadline = nil }, NpcCombatRecovery)
end

function NpcCombatRecovery:Begin(now: number): number
    self.deadline = now + Policy.RecoverySeconds
    return self.deadline
end

function NpcCombatRecovery:Pending(): boolean
    return self.deadline ~= nil
end

function NpcCombatRecovery:Ready(now: number): boolean
    return self.deadline ~= nil and now >= self.deadline
end

function NpcCombatRecovery:Cancel()
    self.deadline = nil
end

return table.freeze(NpcCombatRecovery)
