local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local Config = require(CharacterShared:WaitForChild("CharacterStatsConfig"))

local Service = {}
local BASE_PREFIX = "Base"
local modifierSources = setmetatable({}, { __mode = "k" })

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
            local debugOverride = tonumber(character:GetAttribute("MovementDebugRunSpeedOverride"))
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

function Service.Initialize(character: Model)
    local d = Config.Default
    modifierSources[character] = {}
    setBase(character, "Level", d.Level)
    setBase(character, "MaxHP", d.MaxHP)
    setBase(character, "Damage", d.Damage)
    setBase(character, "Defense", d.Defense)
    setBase(character, "AttackSpeed", d.AttackSpeed)
    setBase(character, "RunSpeed", d.RunSpeed)
    setBase(character, "CritChance", d.CritChance)
    character:SetAttribute("MoveSpeed", d.RunSpeed)
    character:SetAttribute("HP", d.MaxHP)
    character:SetAttribute("Damageable", true)
    character:SetAttribute("LifeState", "Alive")
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
