local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local Config = require(CharacterShared:WaitForChild("CharacterStatsConfig"))
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))

local Critical = require(Shared:WaitForChild("balance"):WaitForChild("CriticalStats"))

local Service = {}
local BASE_PREFIX = "Base"
local modifierSources = setmetatable({}, { __mode = "k" })
local RUN_SPEED_OVERRIDE_ATTRIBUTE = "MovementDebugRunSpeedOverride"

local function baseName(stat: string): string
    return BASE_PREFIX .. stat
end

local function setBase(character: Model, stat: string, value: number)
    character:SetAttribute(baseName(stat), value)
    character:SetAttribute(stat, value)
end

local function recompute(character: Model)
    local previousMaxHP = tonumber(character:GetAttribute("MaxHP")) or Config.Default.MaxHP
    local previousHP = tonumber(character:GetAttribute("HP")) or previousMaxHP
    local sources = modifierSources[character] or {}

    for stat, defaultValue in pairs(Config.Default) do
        local base = tonumber(character:GetAttribute(baseName(stat)))
        if base == nil then
            base = tonumber(defaultValue) or 0
            character:SetAttribute(baseName(stat), base)
        end
        local delta = 0
        for _, modifiers in pairs(sources) do
            delta += tonumber(modifiers[stat]) or 0
        end
        local resolved = base + delta
        -- Percent modifiers are resolved after flat gear modifiers so buffs
        -- follow weapon swaps and progression without snapshotting old stats.
        if stat == "Damage" or stat == "MaxHP" then
            local percent = 0
            for _, modifiers in pairs(sources) do
                percent += tonumber(modifiers[stat .. "Percent"]) or 0
            end
            local buff = sources["skill-buffs"] or {}
            local buffPercent = tonumber(buff[stat .. "Percent"]) or 0
            local beforeBuff = resolved * (1 + (percent - buffPercent) / 100)
            resolved *= 1 + percent / 100
            if stat == "MaxHP" and percent ~= 0 then resolved = math.floor(resolved + 0.5) end
            if stat == "MaxHP" and percent ~= buffPercent then beforeBuff = math.floor(beforeBuff + 0.5) end
            character:SetAttribute(if stat == "Damage" then "BuffGain_might" else "BuffGain_earth", if buffPercent > 0 then resolved - beforeBuff else nil)
        end
        if stat == "AttackSpeed" then
            local percent=0
            for _, modifiers in pairs(sources) do percent += tonumber(modifiers.AttackSpeedPercent) or 0 end
            resolved *= 1+percent/100
        end
        if stat == "CritChance" then
            local percent, flat = 0, 0
            for _, modifiers in pairs(sources) do
                percent += tonumber(modifiers.CritChancePercent) or 0
                flat += tonumber(modifiers.CritChanceFlat) or 0
            end
            resolved = Critical.Chance(resolved, percent, flat)
        elseif stat == "CritMultiplier" then
            resolved = Critical.Multiplier(resolved)
        elseif stat == "RunSpeed" then
            local debugOverride = tonumber(character:GetAttribute(RUN_SPEED_OVERRIDE_ATTRIBUTE))
            if debugOverride ~= nil then
                resolved = math.max(0, debugOverride + (tonumber((sources["skill-buffs"] or {}).RunSpeed) or 0))
            end
        end
        if stat == "RunSpeed" then
            local gain = tonumber((sources["skill-buffs"] or {}).RunSpeed) or 0
            character:SetAttribute("BuffGain_wind", if gain > 0 then gain else nil)
        end
        character:SetAttribute(stat, resolved)
    end

    local newMaxHP = tonumber(character:GetAttribute("MaxHP")) or Config.Default.MaxHP
    if newMaxHP ~= previousMaxHP then
        character:SetAttribute("HP", math.clamp(previousHP, 0, math.max(0, newMaxHP)))
    end
    character:SetAttribute("MoveSpeed", tonumber(character:GetAttribute("RunSpeed")) or Config.Default.RunSpeed)
end

function Service.Initialize(character: Model, _startingStats: any?, progressionLevel: number?)

    modifierSources[character] = {}
    local level = Balance.Level(progressionLevel or 1)
    setBase(character, "Level", level.level)
    setBase(character, "MaxHP", level.hp)
    setBase(character, "Damage", Balance.BaseDamageAt(level.level))
    setBase(character, "Defense", 0)
    setBase(character, "AttackSpeed", Balance.Rules.baseAttackSpeed)
    setBase(character, "RunSpeed", Balance.Rules.baseRunSpeed)
    setBase(character, "CritChance", Balance.Rules.critChance)
    character:SetAttribute("CritChance", Critical.Chance(Balance.Rules.critChance))
    setBase(character, "CritMultiplier", Balance.Rules.critMultiplier)
    character:SetAttribute("MoveSpeed", Balance.Rules.baseRunSpeed)
    character:SetAttribute("HP", level.hp)
    character:SetAttribute("Damageable", true)
    character:SetAttribute("LifeState", "Alive")
end

function Service.SetProgressionLevel(character: Model, levelNumber: number)
    local level = Balance.Level(levelNumber)
    character:SetAttribute("BaseLevel", level.level)
    character:SetAttribute("BaseMaxHP", level.hp)
    character:SetAttribute("BaseDamage", Balance.BaseDamageAt(level.level))
    recompute(character)
end

function Service.SetModifierSource(character: Model, sourceId: string, modifiers: any)
    local sources = modifierSources[character]
    if not sources then
        sources = {}
        modifierSources[character] = sources
    end
    sources[sourceId] = if type(modifiers) == "table" then modifiers else {}
    recompute(character)
end

function Service.ClearModifierSource(character: Model, sourceId: string)
    local sources = modifierSources[character]
    if sources then
        sources[sourceId] = nil
    end
    recompute(character)
end

function Service.ApplyModifiers(character: Model, modifiers: any)
    Service.SetModifierSource(character, "weapon", modifiers)
end

return Service
