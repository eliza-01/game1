-- Cadence only. Never owns target selection, movement, or combat state.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Options = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("GameOptions"))
local config = Options.AdaptiveAISettings()
local Policy = {Enabled = config.enabled}

local function idle(agent)
    return agent.active and agent.model.Parent and agent.model:GetAttribute("LifeState") == "Alive"
        and agent.state == "Idle" and not agent.target and not agent.attacking
end

function Policy.MonsterDelay(agent, now, base)
    if not idle(agent) or agent.returning or agent.retaliating or agent.homeRecall
        or agent.specialCast or agent.retreatPending or agent.attackPursuitActive
        or agent.model:GetAttribute("MonsterCombatActive") == true
        or agent.model:GetAttribute("MonsterSpawning") == true then return base end
    local nav = agent.recoveryNavigation
    if nav and (nav.plan or nav.climb or nav.blockedPursuit or nav.mode == "Retry" or nav.mode == "BlockedWait") then return base end
    if agent.model:GetAttribute("MonsterAggressive") == true then
        -- Never suspend proximity detection: the original scan deadline is the
        -- upper bound, even for far-away or wandering aggressive monsters.
        return math.max(base, math.min(0.3, agent.nextTargetScanAt - now))
    end
    return config.dormantSeconds
end

function Policy.NpcDelay(agent, _now, base)
    if not idle(agent) or agent.recovery:Pending() or agent.returnAfterAttack
        or agent.model:GetAttribute("InCombat") == true or not agent.root.Anchored then return base end
    -- A displaced NPC must still run its original home-leash check. Only
    -- anchored NPCs at the authored home pose qualify for dormant cadence.
    if (agent.root.Position - agent.home.Position).Magnitude > 0.01 then return base end
    return config.dormantSeconds
end

return table.freeze(Policy)
