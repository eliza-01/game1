-- Authoritative monster combat state/target lifecycle and decision policy.
-- Navigation, animation and damage stay with MonsterAIService and are not performed here.
local Players = game:GetService("Players")
local HostilePursuitRegistry = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("HostilePursuitRegistry"))

local MonsterCombatState = {}
export type Decision = "NoTarget" | "AttackActive" | "BeginAttack" | "Chase"

local function setState(agent: any, state: string)
    if agent.state == state then return end
    agent.state = state
    agent.model:SetAttribute("MonsterAIState", state)
end

local function enterCombat(agent: any, target: Model)
    agent.target = target
    HostilePursuitRegistry.SetTarget(agent.model, target)
    agent.model:SetAttribute("MonsterCombatActive", true)
    agent.model:SetAttribute("MonsterTargetName", target.Name)
    local player = Players:GetPlayerFromCharacter(target)
    agent.model:SetAttribute("MonsterTargetUserId", player and player.UserId or 0)
    setState(agent, "Aggro")
end

function MonsterCombatState.SetState(agent: any, state: string)
    setState(agent, state)
end

function MonsterCombatState.Enter(agent: any, target: Model)
    enterCombat(agent, target)
end

function MonsterCombatState.ClearTarget(agent: any)
    agent.target = nil
    HostilePursuitRegistry.Clear(agent.model)
end

function MonsterCombatState.FinishExit(agent: any)
    agent.model:SetAttribute("MonsterTargetName", "")
    agent.model:SetAttribute("MonsterTargetUserId", 0)
    agent.model:SetAttribute("MonsterCombatActive", false)
    agent.model:SetAttribute("MonsterAttackPhase", "")
    setState(agent, "Idle")
end

function MonsterCombatState.ClearPursuit(agent: any)
    HostilePursuitRegistry.Clear(agent.model)
end

function MonsterCombatState.Decide(attacking: boolean, hasTarget: boolean, distance: number, attackRadius: number): Decision
    if not hasTarget then return "NoTarget" end
    if attacking then return "AttackActive" end
    if distance <= attackRadius then return "BeginAttack" end
    return "Chase"
end

return table.freeze(MonsterCombatState)
