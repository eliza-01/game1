-- Server-authoritative monster combat AI adapted from RobloxLineage.
-- Contract: Aggro -> Chase -> Attack. While an authored attack is still active,
-- a target that leaves weapon range is pursued directly without cancelling the
-- attack; the live target position is validated again on the Hit timeline event.
local Facing = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorFacingTracker"))
local TargetPolicy = require(script.Parent:WaitForChild("MonsterTargetPolicy"))
local CombatState = require(script.Parent:WaitForChild("MonsterCombatState"))
local Presentation = require(script.Parent:WaitForChild("MonsterCombatPresentation"))
local AttackExecutor = require(script.Parent:WaitForChild("MonsterAttackExecutor"))
local Navigation = require(script.Parent:WaitForChild("MonsterChaseNavigation"))
local Lifecycle = require(script.Parent:WaitForChild("MonsterAgentLifecycle"))

local MonsterAIService = {}
local started = false
local random = Random.new()

local THINK_INTERVAL = 0.10
local TARGET_SCAN_INTERVAL = 0.30
local rootOf = TargetPolicy.RootOf
local targetIsValid = TargetPolicy.IsValid
local horizontalDistance = TargetPolicy.HorizontalDistance
local aggressive = TargetPolicy.IsAggressive
local attackRadius = TargetPolicy.AttackRadius

local setState = CombatState.SetState

-- Movement and its per-agent path/blocked state are owned by MonsterChaseNavigation.
local stopNavigation = Navigation.StopNavigation
local runSpeedStuds = Navigation.RunSpeedStuds
local navigateTo = Navigation.NavigateTo

local AttackMovement = table.freeze({
    StopNavigation = stopNavigation,
    RunSpeedStuds = runSpeedStuds,
})

local function leaveCombat(agent: any)
    Facing.Stop(agent.model)
    CombatState.ClearTarget(agent)
    agent.attacking = false
    agent.attackSerial += 1
    AttackExecutor.ClearPursuit(agent)
    stopNavigation(agent)
    Presentation.Stop(agent)
    CombatState.FinishExit(agent)
end

local function updateTarget(agent: any, now: number)
    if agent.target and targetIsValid(agent.target) then return end
    if agent.target then leaveCombat(agent) end
    if not aggressive(agent) or now < agent.nextTargetScanAt then return end
    agent.nextTargetScanAt = now + TARGET_SCAN_INTERVAL
    local target = TargetPolicy.AcquireNearestTarget(agent)
    if target then CombatState.Enter(agent, target) end
end

local function runAgent(agent: any)
    task.wait(random:NextNumber(0, THINK_INTERVAL))
    while agent.active and agent.model.Parent do
        task.wait(THINK_INTERVAL)
        if not agent.active or not agent.model.Parent then break end
        if tostring(agent.model:GetAttribute("LifeState") or "") ~= "Alive" then
            leaveCombat(agent)
            break
        end
        -- The rig can be temporarily anchored below terrain during spawn reveal.
        if agent.model:GetAttribute("MonsterSpawning") == true then
            continue
        end
        if not aggressive(agent) then
            if agent.target or agent.model:GetAttribute("MonsterCombatActive") == true then leaveCombat(agent) end
            continue
        end
        local now = os.clock()
        updateTarget(agent, now)
        local target = agent.target
        local targetRoot = rootOf(target)
        local distance = if targetRoot then horizontalDistance(agent.root.Position, targetRoot.Position) else 0
        local action = CombatState.Decide(agent.attacking, targetRoot ~= nil, distance, attackRadius(agent))
        if action == "AttackActive" then
            -- Active-attack movement is owned by maintainAttackPursuit().
            -- The slower AI decision loop must not issue competing MoveTo calls.
            setState(agent, "Attack")
        elseif action == "BeginAttack" then
            stopNavigation(agent)
            AttackExecutor.FaceDirection(agent, targetRoot.Position - agent.root.Position)
            Presentation.PlayCombatIdle(agent)
            AttackExecutor.Begin(agent, target, AttackMovement, random)
        elseif action == "Chase" then
            setState(agent, "Chase")
            AttackExecutor.ClearPursuit(agent)
            Presentation.PlayRun(agent)
            navigateTo(agent, targetRoot.Position, runSpeedStuds(agent))
        elseif agent.model:GetAttribute("MonsterCombatActive") == true then
            leaveCombat(agent)
        end
    end
    Lifecycle.Release(agent)
end

function MonsterAIService.Start()
    if started then return end
    started = true
    Lifecycle.Start(runAgent, random)
    print("[game1][monster-ai] RobloxLineage aggro/chase/attack-pursuit runtime ready")
end

return table.freeze(MonsterAIService)
