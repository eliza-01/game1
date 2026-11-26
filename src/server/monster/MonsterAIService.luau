-- Server-authoritative monster combat AI adapted from RobloxLineage.
-- Contract: Aggro -> Chase -> Attack. While an authored attack is still active,
-- a target that leaves weapon range is pursued directly without cancelling the
-- attack; the live target position is validated again on the Hit timeline event.
local Facing = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorFacingTracker"))
local TargetPolicy = require(script.Parent:WaitForChild("MonsterTargetPolicy"))
local CombatState = require(script.Parent:WaitForChild("MonsterCombatState"))
local Presentation = require(script.Parent:WaitForChild("MonsterCombatPresentation"))
local AttackExecutor = require(script.Parent:WaitForChild("MonsterAttackExecutor"))
local Skills = require(script.Parent:WaitForChild("MonsterSkills"))
local Special = require(script.Parent:WaitForChild("MonsterSkillCast"))
local Navigation = require(script.Parent:WaitForChild("MonsterChaseNavigation"))
local Lifecycle = require(script.Parent:WaitForChild("MonsterAgentLifecycle"))
local DamageSignals = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("ActorDamageSignals"))
local DeathChase = require(script.Parent:WaitForChild("MonsterDeathChasePolicy"))
local HomeLeash = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorHomeLeash"))
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local GameOptions = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("GameOptions"))

local Retreat = require(script.Parent:WaitForChild("MonsterRangedRetreat"))
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
    Special.Cancel(agent)
    Retreat.Clear(agent)
    Facing.Stop(agent.model)
    CombatState.ClearTarget(agent)
    agent.retaliating = false
    agent.returning = false
    agent.lastDamageAt = 0
    agent.attacking = false
    agent.attackSerial += 1
    AttackExecutor.ClearPursuit(agent)
    stopNavigation(agent)
    Presentation.Stop(agent)
    CombatState.FinishExit(agent)
end

local function beginReturn(agent: any)
    if agent.returning then return end
    Special.Cancel(agent)
    Retreat.Clear(agent)
    -- Invalidate pending attack hit events BEFORE clearing the target.
    agent.attacking = false
    agent.attackSerial += 1
    AttackExecutor.ClearPursuit(agent)
    stopNavigation(agent)
    Facing.Stop(agent.model)
    CombatState.ClearTarget(agent)
    agent.model:SetAttribute("MonsterTargetName", "")
    agent.model:SetAttribute("MonsterTargetUserId", 0)
    agent.retaliating = false
    agent.returning = true
    -- Stay combat-active until home so wandering cannot fight navigation.
    agent.model:SetAttribute("MonsterCombatActive", true)
    setState(agent, "Return")
    Presentation.PlayRun(agent)
end

local function updateReturn(agent: any)
    local home = agent.home
    if horizontalDistance(agent.root.Position, home) <= 2 then
        leaveCombat(agent)
        return
    end
    setState(agent, "Return")
    navigateTo(agent, home, runSpeedStuds(agent))
end

local function outsideHome(agent: any, position: Vector3): boolean
    return HomeLeash.Outside(agent.spawnCenter, position, agent.homeRadius)
end

local function updateTarget(agent: any, now: number)
    if agent.target and targetIsValid(agent.target) and TargetPolicy.AllowsTarget(agent, agent.target) then return end
    if agent.target then beginReturn(agent); return end
    if not aggressive(agent) or now < agent.nextTargetScanAt then return end
    agent.nextTargetScanAt = now + TARGET_SCAN_INTERVAL
    local target = TargetPolicy.AcquireNearestTarget(agent)
    if target then CombatState.Enter(agent, target) end
end

-- Server-authoritative retaliation edge, independent of the periodic proximity
-- scan. This is an aggro transition; the authored Hit event still owns damage.
local function onDamaged(attacker: Model?, monster: Model, attempted: number, applied: number, killed: boolean)
    if attempted <= 0 or killed or not attacker or not Players:GetPlayerFromCharacter(attacker) then return end
    if not TargetPolicy.IsValid(attacker) or monster:GetAttribute("LifeState") ~= "Alive" then return end
    local agent = Lifecycle.Find(monster)
    if not agent or not agent.active or not TargetPolicy.AllowsTarget(agent, attacker) then return end
    if agent.target ~= attacker or agent.returning then
        Retreat.Clear(agent)
        CombatState.Enter(agent, attacker)
        agent.lastDamageAt = os.clock() -- New encounter starts an inactivity clock.
    elseif applied > 0 then
        agent.lastDamageAt = os.clock()
    end
    agent.returning = false
    agent.retaliating = true
    if applied > 0 then Skills.MarkAttacked(agent.model) end
    if agent.model:GetAttribute("MonsterSpawning") == true or agent.attacking or Retreat.Waiting(agent) then return end
    local targetRoot = rootOf(attacker)
    if not targetRoot then return end
    if horizontalDistance(agent.root.Position, targetRoot.Position) <= attackRadius(agent) then
        stopNavigation(agent)
        Presentation.PlayCombatIdle(agent)
        AttackExecutor.Begin(agent, attacker, AttackMovement, random)
    else
        setState(agent, "Chase")
        AttackExecutor.ClearPursuit(agent)
        Presentation.PlayRun(agent)
        navigateTo(agent, targetRoot.Position, runSpeedStuds(agent))
    end
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
        if not aggressive(agent) and not agent.retaliating and not agent.returning then
            if agent.target or agent.model:GetAttribute("MonsterCombatActive") == true then leaveCombat(agent) end
            continue
        end
        local now = os.clock()
        if agent.returning then
            updateReturn(agent)
            continue
        end
        updateTarget(agent, now)
        -- updateTarget can start Return when the player dies or respawns.
        -- Do not fall through to NoTarget/leaveCombat and strand the monster.
        if agent.returning then
            updateReturn(agent)
            continue
        end
        local target = agent.target
        if target then
            if agent.lastDamageAt <= 0 then agent.lastDamageAt = now end
            local targetRoot = rootOf(target)
            if not DeathChase.IsBound(agent.model) and (outsideHome(agent, agent.root.Position)
                or (targetRoot and outsideHome(agent, targetRoot.Position))
                or HomeLeash.NoDamageTimeout(agent.lastDamageAt, now, GameOptions.HostileNoDamageReturnSeconds())) then
                beginReturn(agent)
                updateReturn(agent)
                continue
            end
        end
        local targetRoot = rootOf(target)
        local distance = if targetRoot then horizontalDistance(agent.root.Position, targetRoot.Position) else 0
        if not agent.attacking and targetRoot and Retreat.Step(agent, targetRoot, now) then
            setState(agent, "Retreat")
            continue
        end
        if target and not agent.attacking and Special.TryBegin(agent,target) then continue end
        local action = CombatState.Decide(agent.attacking, targetRoot ~= nil, distance, attackRadius(agent))
        if action == "AttackActive" then
            -- Active-attack movement is owned by maintainAttackPursuit().
            -- The slower AI decision loop must not issue competing MoveTo calls.
            setState(agent, "Attack")
        elseif action == "BeginAttack" then
            stopNavigation(agent)
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

-- Confirmed damage in either direction refreshes combat activity.
-- Taking damage during Return immediately re-engages via onDamaged above.
local function onDamageDealt(attacker: Model?, target: Model, _attempted: number, applied: number)
    if not attacker or applied <= 0 or not Players:GetPlayerFromCharacter(target) then return end
    local agent = Lifecycle.Find(attacker)
    if agent and agent.active and agent.target == target then
        agent.lastDamageAt = os.clock()
    end
end

function MonsterAIService.Start()
    if started then return end
    started = true
    DamageSignals.Event:Connect(onDamaged)
    DamageSignals.Event:Connect(onDamageDealt)
    Lifecycle.Start(runAgent, random)
    print("[game1][monster-ai] RobloxLineage aggro/chase/attack-pursuit runtime ready")
end

return table.freeze(MonsterAIService)
