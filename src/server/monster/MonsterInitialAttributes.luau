-- Applies published stat/behavior policy to a fresh monster clone.
-- Does not create rigs, play clips or schedule population.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
local CharacterMovementConfig = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("character"):WaitForChild("CharacterMovementConfig"))
local MonsterInitialAttributes = {}
local function finite(value: any, fallback: number): number
    local number = tonumber(value)
    if number == nil or number ~= number or number == math.huge or number == -math.huge then
        return fallback
    end
    return number
end

local function applyMonsterAttributes(model: Model, definition: any, record: any, instanceId: string)
    local stats = definition.stats or {}
    local behavior = definition.behavior or {}
    local maxHP = math.max(1, finite(stats.MaxHP, 100))
    model:SetAttribute("Game1MonsterRuntime", true)
    model:SetAttribute("MonsterSlug", tostring(definition.slug or record.monsterSlug or ""))
    model:SetAttribute("SpawnId", tostring(record.spawnId or ""))
    model:SetAttribute("MonsterInstanceId", instanceId)
    model:SetAttribute("Damageable", true)
    model:SetAttribute("LifeState", "Alive")
    model:SetAttribute("InCombat", false)
    model:SetAttribute("CombatState", "Peace")
    model:SetAttribute("CombatUntilServerTime", 0)
    model:SetAttribute("MaxHP", maxHP)
    model:SetAttribute("HP", maxHP)
    model:SetAttribute("Damage", math.max(0, finite(stats.Damage, 10)))
    model:SetAttribute("AttackSpeed", math.max(1, finite(stats.AttackSpeed, 100)))
    model:SetAttribute("RunSpeed", math.max(0, finite(stats.RunSpeed, CharacterMovementConfig.DefaultRunSpeed)))
    local debugLocomotion = tostring(Workspace:GetAttribute("Game1MonsterDebugLocomotionMode") or "Walk")
    model:SetAttribute("MonsterLocomotionMode", string.lower(debugLocomotion) == "run" and "Run" or "Walk")
    model:SetAttribute("CritChance", math.clamp(finite(stats.CritChance, 0), 0, 100))
    model:SetAttribute("Defense", math.max(0, finite(stats.Defense, 0)))
    local aggressive = behavior.aggressive == true
    local aggroRadius = math.max(0, finite(behavior.aggroRadiusStuds, 16))
    local attackRadius = math.max(0, finite(behavior.attackRadiusStuds, 3))
    model:SetAttribute("MonsterAuthoredAggressive", aggressive)
    model:SetAttribute("MonsterAuthoredAggroRadius", aggroRadius)
    model:SetAttribute("MonsterAuthoredAttackRadius", attackRadius)
    model:SetAttribute("MonsterAggressive", aggressive)
    model:SetAttribute("MonsterAggroRadius", aggroRadius)
    model:SetAttribute("MonsterAttackRadius", attackRadius)
    model:SetAttribute("MonsterCombatActive", false)
    model:SetAttribute("MonsterAttackPursuitActive", false)
end

MonsterInitialAttributes.Apply = applyMonsterAttributes
return table.freeze(MonsterInitialAttributes)
