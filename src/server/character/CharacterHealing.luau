--!strict
-- Shared server authority for HP recovery. Debug rates never apply outside Studio.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Healing = {}
local MAX_REGEN = 10000
local MAX_VAMPIRIC = 100

local function valid(value: any, maximum: number): boolean
    return type(value) == "number" and value >= 0 and value <= maximum
end

function Healing.ValidateTestRates(regen: any, vampiric: any): (boolean, string?)
    if not valid(regen, MAX_REGEN) then return false, "HP/sec must be 0–10000" end
    if not valid(vampiric, MAX_VAMPIRIC) then return false, "Vampiric % must be 0–100" end
    return true, nil
end

local function testOwner(character: Model): Player?
    if not RunService:IsStudio() or character:GetAttribute("GameplayTestKind") ~= "player" then return nil end
    local owner = Players:GetPlayerFromCharacter(character)
    if not owner or owner.Character ~= character or owner:GetAttribute("Game1GameplayTestActive") ~= true
        or character:GetAttribute("Game1GameplayTestOwner") ~= owner.UserId then return nil end
    return owner
end

function Healing.TestRate(character: Model, attribute: string): number
    if not testOwner(character) then return 0 end
    local maximum = if attribute == "GameplayTestRegen" then MAX_REGEN else MAX_VAMPIRIC
    local rate = character:GetAttribute(attribute)
    return if valid(rate, maximum) then rate :: number else 0
end

function Healing.Restore(character: Model, amount: number): number
    if not character.Parent or character:GetAttribute("LifeState") ~= "Alive"
        or character:GetAttribute("Damageable") ~= true or not (amount > 0 and amount < math.huge) then return 0 end
    local maxHP = math.max(0, tonumber(character:GetAttribute("MaxHP")) or 0)
    local hp = math.clamp(tonumber(character:GetAttribute("HP")) or 0, 0, maxHP)
    if hp <= 0 or hp >= maxHP then return 0 end
    local restored = math.min(amount, maxHP - hp)
    character:SetAttribute("HP", hp + restored)
    return restored
end

function Healing.OnDamage(attacker: Model?, target: Model, actualLoss: number)
    if not attacker or attacker == target or actualLoss <= 0 then return end
    local owner = testOwner(attacker)
    if not owner or target:GetAttribute("Game1GameplayTestOwner") ~= owner.UserId then return end
    local kind = target:GetAttribute("GameplayTestKind")
    if kind ~= "zone" and kind ~= "group" then return end
    local rate = Healing.TestRate(attacker, "GameplayTestVampiric")
    if rate > 0 then Healing.Restore(attacker, actualLoss * rate / 100) end
end
return table.freeze(Healing)
