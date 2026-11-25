-- Applies published stat/behavior policy to a fresh monster clone.
-- Does not create rigs, play clips or schedule population.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
local CharacterMovementConfig = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("character"):WaitForChild("CharacterMovementConfig"))
local Balance = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("balance"):WaitForChild("Balance"))
local Critical = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("balance"):WaitForChild("CriticalStats"))
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
    local balance = Balance.MonsterForModel(tostring(definition.slug or record.monsterSlug or ""))
    if record.testOwner then balance = Balance.Monster(record.testBalanceId) end
    local maxHP = if balance then balance.hp else math.max(1, finite(stats.MaxHP, 100))
    model:SetAttribute("MonsterBalanceId", if balance then balance.id else "")
    model:SetAttribute("RewardXP", if balance then balance.xp else 0)
    model:SetAttribute("RewardGold", if balance then balance.gold else 0)
    model:SetAttribute("Game1MonsterRuntime", true)
    model:SetAttribute("MonsterSlug", tostring(definition.slug or record.monsterSlug or ""))
    local level = if balance then balance.level else tonumber(stats.Level)
    if level and level > 0 and level < 100000 and level == math.floor(level) then
        model:SetAttribute("Level", level)
    end
    model:SetAttribute("SpawnId", tostring(record.spawnId or ""))
    local point = record.position or {}
    model:SetAttribute("MonsterSpawnCenter", Vector3.new(finite(point.x, 0), finite(point.y, 0), finite(point.z, 0)))
    model:SetAttribute("MonsterInstanceId", instanceId)
    model:SetAttribute("Damageable", true)
    model:SetAttribute("LifeState", "Alive")
    model:SetAttribute("InCombat", false)
    model:SetAttribute("CombatState", "Peace")
    model:SetAttribute("CombatUntilServerTime", 0)
    model:SetAttribute("MaxHP", maxHP)
    model:SetAttribute("HP", maxHP)
    model:SetAttribute("Damage", if balance then balance.damage else math.max(0, finite(stats.Damage, 10)))
    model:SetAttribute("AttackSpeed", if balance then balance.attackSpeed else math.max(1, finite(stats.AttackSpeed, 100)))
    model:SetAttribute("RunSpeed", math.max(0, finite(stats.RunSpeed, CharacterMovementConfig.DefaultRunSpeed)))
    local debugLocomotion = tostring(Workspace:GetAttribute("Game1MonsterDebugLocomotionMode") or "Walk")
    model:SetAttribute("MonsterLocomotionMode", string.lower(debugLocomotion) == "run" and "Run" or "Walk")
    model:SetAttribute("CritChance", Critical.Chance(if balance then balance.critChance else finite(stats.CritChance, 0)))
    model:SetAttribute("Defense", if balance then 0 else math.max(0, finite(stats.Defense, 0)))
    local aggressive = behavior.aggressive == true
    if record.testOwner then
        model:SetAttribute("Game1GameplayTestOwner", record.testOwner)
        model:SetAttribute("GameplayTestKind", record.testKind)
        aggressive = false -- group is armed atomically after every member is ready
    end
    local aggroRadius = math.max(0, finite(behavior.aggroRadiusStuds, 16))
    if record.testOwner then aggroRadius = 120 end
    local attackRadius = if balance then balance.attackRange else math.max(0, finite(behavior.attackRadiusStuds, 3))
    model:SetAttribute("MonsterCombatType", if balance then balance.type else "melee")
    if record.testApproachFrame and record.testApproachSize then
        model:SetAttribute("GameplayTestApproachFrame", record.testApproachFrame)
        model:SetAttribute("GameplayTestApproachSize", record.testApproachSize)
        aggressive = true
        aggroRadius = attackRadius
    end
    -- Leash belongs to this spawn record, never to the monster species.
    local homeRadius = math.clamp(finite(record.homeRadiusStuds, 150), 1, 10000)
    model:SetAttribute("MonsterAuthoredAggressive", aggressive)
    model:SetAttribute("MonsterAuthoredAggroRadius", aggroRadius)
    model:SetAttribute("MonsterAuthoredAttackRadius", attackRadius)
    model:SetAttribute("MonsterAggressive", aggressive)
    model:SetAttribute("MonsterAggroRadius", aggroRadius)
    model:SetAttribute("MonsterHomeRadiusStuds", homeRadius)
    model:SetAttribute("MonsterAttackRadius", attackRadius)
    model:SetAttribute("MonsterCombatActive", false)
    model:SetAttribute("MonsterAttackPursuitActive", false)
end

MonsterInitialAttributes.Apply = applyMonsterAttributes
return table.freeze(MonsterInitialAttributes)
