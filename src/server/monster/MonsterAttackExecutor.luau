-- Server-authoritative execution of authored monster attacks.
-- Owns Hit/finish timeline callbacks and active-attack pursuit (not general navigation).
-- Attack serial and target checks reject stale callbacks after death/target change.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local AttackTimelineConfig = require(Shared:WaitForChild("combat"):WaitForChild("AttackTimelineConfig"))
local AnimationSpeedScaling = require(Shared:WaitForChild("animation"):WaitForChild("AnimationSpeedScaling"))
local DamageService = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("DamageService"))
local CombatFeedbackService = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("CombatFeedbackService"))
local HitEffectService = require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("HitEffectService"))
local Facing = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorFacingTracker"))
local AttackPursuit = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorAttackPursuit"))
local TargetPolicy = require(script.Parent:WaitForChild("MonsterTargetPolicy"))
local CombatState = require(script.Parent:WaitForChild("MonsterCombatState"))
local Presentation = require(script.Parent:WaitForChild("MonsterCombatPresentation"))

local Retreat = require(script.Parent:WaitForChild("MonsterRangedRetreat"))
local Special = require(script.Parent:WaitForChild("MonsterSkillCast"))
local MonsterAttackExecutor = {}
local ATTACK_PURSUIT_SPEED_MULTIPLIER = 1.65
MonsterAttackExecutor.PursuitSpeedMultiplier = ATTACK_PURSUIT_SPEED_MULTIPLIER

local function finite(value: any, fallback: number): number
    local n = tonumber(value)
    if n == nil or n ~= n or n == math.huge or n == -math.huge then return fallback end
    return n
end

local rootOf = TargetPolicy.RootOf
local targetIsValid = TargetPolicy.IsValid
local attackRadius = TargetPolicy.AttackRadius
local aggressive = TargetPolicy.IsAggressive
local setState = CombatState.SetState

local function clearAttackPursuit(agent: any)
    agent.attackPursuit:Stop()
    if agent.attackPursuitActive then
        agent.attackPursuitActive = false
        agent.model:SetAttribute("MonsterAttackPursuitActive", false)
    end
end


local function pursueDirectlyDuringAttack(agent: any, targetRoot: BasePart, movement: any): boolean
    local maximumSpeed = movement.RunSpeedStuds(agent) * ATTACK_PURSUIT_SPEED_MULTIPLIER
    local pursuing, desiredSpeed = agent.attackPursuit:Step(targetRoot, attackRadius(agent), maximumSpeed)
    if not pursuing then
        clearAttackPursuit(agent)
        return false
    end
    if not agent.attackPursuitActive then
        agent.attackPursuitActive = true
        agent.model:SetAttribute("MonsterAttackPursuitActive", true)
    end
    local baseRunSpeed = math.max(0.001, movement.RunSpeedStuds(agent))
    Presentation.PublishAttackPursuitPlaybackSpeed(agent, desiredSpeed / baseRunSpeed)
    return true
end

local function maintainAttackPursuit(agent: any, target: Model, serial: number, movement: any)
    task.spawn(function()
        while agent.active
            and agent.attacking
            and agent.attackSerial == serial
            and agent.target == target
            and tostring(agent.model:GetAttribute("LifeState") or "") == "Alive" do
            local liveRoot = rootOf(target)
            if not targetIsValid(target) or not liveRoot then
                clearAttackPursuit(agent)
                return
            end
            pursueDirectlyDuringAttack(agent, liveRoot, movement)
            -- Facing is updated continuously by the shared tracker even at rest.
            RunService.Heartbeat:Wait()
        end
    end)
end

function MonsterAttackExecutor.Begin(agent: any, target: Model, movement: any, random: Random)
    if agent.attacking or os.clock() < agent.nextAttackAt then return end
    if Special.TryBegin(agent,target) then return end
    local row = Presentation.WeightedRow(agent.attackRows, random)
    if not row then return end
    local percent = AnimationSpeedScaling.ResolveForAnimation(agent.model, "attack", row.animationId)
    -- A bound monster must consume its Database AS even when the authored
    -- clip has no AttackSpeed scaling rule (the current Gremlin attack).
    local rule = AnimationSpeedScaling.RuleForAnimation(agent.model, "attack", row.animationId)
    if tostring(agent.model:GetAttribute("MonsterBalanceId") or "") ~= ""
        and (not rule or rule.stat ~= "AttackSpeed") then
        percent = math.clamp(percent * finite(agent.model:GetAttribute("AttackSpeed"), 100) / 100, 1, 400)
    end
    percent = math.clamp(percent * finite(agent.model:GetAttribute("SkillAttackSpeedMultiplier"), 1), 1, 400)
    local timing = AttackTimelineConfig.ResolveRuntime(row.clipId, percent)
    if not timing then return end

    local cycleDuration = timing.duration
    if Retreat.IsRanged(agent.model) then
        -- Reserve a portion of the existing cycle, not a new cooldown.
        local fittedPercent = Retreat.FitPercent(timing, percent)
        timing = AttackTimelineConfig.ResolveRuntime(row.clipId, fittedPercent)
        percent = fittedPercent
    end
    agent.attacking = true
    Facing.Track(agent.model, agent.root, agent.humanoid, target, rootOf, true)
    agent.attackSerial += 1
    local serial = agent.attackSerial
    local duration = math.max(0.05, finite(timing.duration, 0.05))
    local now = os.clock()
    agent.attackEndsAt = now + duration
    agent.nextAttackAt = agent.attackEndsAt
    if Retreat.IsRanged(agent.model) then
        agent.nextAttackAt = now + math.max(duration, cycleDuration)
        agent.retreatPending = agent.nextAttackAt > agent.attackEndsAt + 0.1
    end
    setState(agent, "Attack")
    movement.StopNavigation(agent)
    Presentation.PlayAttack(agent, row, percent)
    agent.model:SetAttribute("MonsterAttackPhase", "Windup")
    if not Retreat.IsRanged(agent.model) then maintainAttackPursuit(agent, target, serial, movement) end

    local hit = timing.events and timing.events.Hit
    local hitTime = math.max(0, finite(hit and hit.time, duration * 0.5))
    task.delay(hitTime, function()
        if not agent.active or agent.attackSerial ~= serial or agent.target ~= target or tostring(agent.model:GetAttribute("LifeState") or "") ~= "Alive" then return end
        if TargetPolicy.AttackStillConnects(agent, target) then
            local damage, killed = DamageService.Apply(agent.model, target, finite(agent.model:GetAttribute("Damage"), 0) * finite(agent.model:GetAttribute("SkillDamageMultiplier"), 1))
            HitEffectService.Publish(agent.model, target, target:GetAttribute("LastCritical") == true, rootOf(target) and rootOf(target).Position or nil)
            agent.model:SetAttribute("LastMonsterAttackDamage", damage)
            agent.model:SetAttribute("MonsterAttackPhase", if damage > 0 then "Hit" else "Miss")
            if damage <= 0 then CombatFeedbackService.PublishMissOverPlayer(target) end
            if killed then clearAttackPursuit(agent) end
        else
            agent.model:SetAttribute("LastMonsterAttackDamage", 0)
            agent.model:SetAttribute("MonsterAttackPhase", "Miss")
            CombatFeedbackService.PublishMissOverPlayer(target)
        end
    end)

    task.delay(duration, function()
        if not agent.active or agent.attackSerial ~= serial then return end
        agent.attacking = false
        agent.attackEndsAt = 0
        Facing.Stop(agent.model)
        clearAttackPursuit(agent)
        Presentation.StopAttack(agent)
        if agent.target == target and targetIsValid(target) and aggressive(agent) then
            agent.model:SetAttribute("MonsterAttackPhase", "Cooldown")
            Presentation.PlayCombatIdle(agent)
        end
    end)
end


function MonsterAttackExecutor.NewPursuit(root: BasePart, humanoid: Humanoid)
    return AttackPursuit.new(root, humanoid)
end

MonsterAttackExecutor.ClearPursuit = clearAttackPursuit
return table.freeze(MonsterAttackExecutor)
