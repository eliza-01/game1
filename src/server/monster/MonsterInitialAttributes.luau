-- Applies published stat/behavior policy to a fresh monster clone.
-- Does not create rigs, play clips or schedule population.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
local CharacterMovementConfig = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("character"):WaitForChild("CharacterMovementConfig"))
local Balance = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("balance"):WaitForChild("Balance"))
local Critical = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("balance"):WaitForChild("CriticalStats"))
local DeathChase = require(script.Parent:WaitForChild("MonsterDeathChasePolicy"))
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
    if record.balanceId then balance = assert(Balance.Monster(record.balanceId), "Invalid authored monster balance ID") end
    if record.testOwner then balance = Balance.Monster(record.testBalanceId) end
    local maxHP = if balance then balance.hp else math.max(1, finite(stats.MaxHP, 100))
    model:SetAttribute("MonsterSkillCaster", if balance and balance.skills and record.testOwner then true else nil)
    model:SetAttribute("MonsterBalanceId", if balance then balance.id else "")
    model:SetAttribute("MonsterNameEn", if balance and not balance.skills then balance.nameEn else nil)
    model:SetAttribute("MonsterNameRu", if balance and not balance.skills then balance.nameRu else nil)
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
    model:SetAttribute("BaseMaxHP", maxHP)
    model:SetAttribute("MaxHP", maxHP)
    model:SetAttribute("HP", maxHP)
    model:SetAttribute("Damage", if balance then balance.damage else math.max(0, finite(stats.Damage, 10)))
    model:SetAttribute("AttackSpeed", if balance then balance.attackSpeed else math.max(1, finite(stats.AttackSpeed, 100)))
    model:SetAttribute("RunSpeed", if balance then balance.runSpeed else math.max(0, finite(stats.RunSpeed, CharacterMovementConfig.DefaultRunSpeed)))
    model:SetAttribute("BaseRunSpeed", model:GetAttribute("RunSpeed"))
    model:SetAttribute("MonsterLocomotionMode", "Walk")
    model:SetAttribute("CritChance", Critical.Chance(if balance then balance.critChance else finite(stats.CritChance, 0)))
    model:SetAttribute("Defense", if balance then 0 else math.max(0, finite(stats.Defense, 0)))
    local aggressive = if balance then balance.aggressive == true else behavior.aggressive == true
    local aggroRadius = math.clamp(finite(if balance then balance.aggroRadiusStuds else behavior.aggroRadiusStuds, 16), 0, 10000)
    -- A concrete spawn overrides its bound Database row. False and zero are valid overrides.
    if type(record.aggressive) == "boolean" then aggressive = record.aggressive end
    if record.aggroRadiusStuds ~= nil then aggroRadius = math.clamp(finite(record.aggroRadiusStuds, aggroRadius), 0, 10000) end
    if record.testOwner then
        model:SetAttribute("Game1GameplayTestOwner", record.testOwner)
        model:SetAttribute("GameplayTestKind", record.testKind)
        model:SetAttribute("GameplayTestZone", record.testZone)
        if record.testKind ~= "zone" then
            -- Guided groups are armed atomically after readiness, independent of world aggro.
            aggressive = false
            aggroRadius = 120
        elseif record.testZone == 8 then
            -- Dedicated Skilled calibration annex, not a release-zone encounter.
            aggressive = true
            aggroRadius = 30
        end
    end
    if record.testOwner and record.testKind == "zone" and (record.testZone or 99) <= 6 and balance then
        local overrides = require(script.Parent.Parent:WaitForChild("dev"):WaitForChild("GameplayAggroOverrides"))
        local change = overrides.Get(balance.nameEn)
        if change then aggressive = change.aggressive; aggroRadius = change.radius end
    end
    local attackRadius = if balance then balance.attackRange else math.max(0, finite(behavior.attackRadiusStuds, 3))
    model:SetAttribute("MonsterCombatType", if balance then balance.type else "melee")
    -- Leash belongs to this spawn record, never to the monster species.
    local homeRadius = math.clamp(finite(record.homeRadiusStuds, 150), 1, 10000)
    model:SetAttribute("MonsterAuthoredAggressive", aggressive)
    model:SetAttribute("MonsterAuthoredAggroRadius", aggroRadius)
    model:SetAttribute("MonsterAuthoredAttackRadius", attackRadius)
    model:SetAttribute("MonsterAggressive", aggressive)
    model:SetAttribute("MonsterAggroRadius", aggroRadius)
    model:SetAttribute("MonsterHomeRadiusStuds", homeRadius)
    local deathChase = if type(record.deathChase) == "boolean" then record.deathChase else balance ~= nil and balance.deathChase == true
    DeathChase.Configure(model, record, deathChase)
    model:SetAttribute("MonsterAttackRadius", attackRadius)
    model:SetAttribute("MonsterCombatActive", false)
    model:SetAttribute("MonsterAttackPursuitActive", false)
end

MonsterInitialAttributes.Apply = applyMonsterAttributes
return table.freeze(MonsterInitialAttributes)
