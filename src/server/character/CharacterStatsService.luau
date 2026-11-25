local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local Config = require(CharacterShared:WaitForChild("CharacterStatsConfig"))
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))

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
        if stat == "RunSpeed" then
            local debugOverride = tonumber(character:GetAttribute(RUN_SPEED_OVERRIDE_ATTRIBUTE))
            if debugOverride ~= nil then
                resolved = math.max(0, debugOverride)
            end
        end
        character:SetAttribute(stat, resolved)
    end

    local newMaxHP = tonumber(character:GetAttribute("MaxHP")) or Config.Default.MaxHP
    if newMaxHP ~= previousMaxHP then
        character:SetAttribute("HP", math.clamp(previousHP, 0, math.max(0, newMaxHP)))
    end
    character:SetAttribute("MoveSpeed", tonumber(character:GetAttribute("RunSpeed")) or Config.Default.RunSpeed)
end

function Service.Initialize(character: Model, startingStats: any?, progressionLevel: number?)
    local d = Config.Default
    local stats = if type(startingStats) == "table" then startingStats else {}
    local function value(stat: string): number
        return tonumber(stats[stat]) or tonumber(d[stat]) or 0
    end

    modifierSources[character] = {}
    local level = Balance.Level(progressionLevel or 1)
    setBase(character, "Level", level.level)
    setBase(character, "MaxHP", level.hp)
    setBase(character, "Damage", Balance.Rules.baseDamage)
    setBase(character, "Defense", 0)
    setBase(character, "AttackSpeed", Balance.Rules.baseAttackSpeed)
    setBase(character, "RunSpeed", value("RunSpeed"))
    setBase(character, "CritChance", Balance.Rules.critChance)
    character:SetAttribute("MoveSpeed", value("RunSpeed"))
    character:SetAttribute("HP", level.hp)
    character:SetAttribute("Damageable", true)
    character:SetAttribute("LifeState", "Alive")
end

function Service.SetProgressionLevel(character: Model, levelNumber: number)
    local level = Balance.Level(levelNumber)
    character:SetAttribute("BaseLevel", level.level)
    character:SetAttribute("BaseMaxHP", level.hp)
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
