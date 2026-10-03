local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local AttackConfig = require(CombatShared:WaitForChild("AttackConfig"))

local DamageService = {}

function DamageService.Apply(attacker: Model?, target: Model, rawDamage: number): (number, boolean)
    if target:GetAttribute("Damageable") ~= true or target:GetAttribute("LifeState") ~= "Alive" then
        if AttackConfig.DebugLogs then
            print(("[game1][DAMAGE] REJECT target=%s damageable=%s lifeState=%s"):format(
                target:GetFullName(),
                tostring(target:GetAttribute("Damageable")),
                tostring(target:GetAttribute("LifeState"))
            ))
        end
        return 0, false
    end

    local defense = math.max(0, tonumber(target:GetAttribute("Defense")) or 0)
    local normalizedRawDamage = math.max(0, tonumber(rawDamage) or 0)
    local finalDamage = math.max(0, math.floor(normalizedRawDamage - defense))
    local hp = math.max(0, tonumber(target:GetAttribute("HP")) or 0)
    local newHP = math.max(0, hp - finalDamage)

    target:SetAttribute("HP", newHP)
    target:SetAttribute("LastDamage", finalDamage)
    target:SetAttribute("LastAttackerUserId", attacker and attacker:GetAttribute("CharacterOwnerUserId") or 0)

    local killed = newHP <= 0
    if killed then
        target:SetAttribute("LifeState", "Dead")
    end

    if AttackConfig.DebugLogs then
        print(("[game1][DAMAGE] target=%s raw=%d defense=%d final=%d hp=%d->%d killed=%s"):format(
            target.Name,
            normalizedRawDamage,
            defense,
            finalDamage,
            hp,
            newHP,
            tostring(killed)
        ))
    end

    return finalDamage, killed
end

return DamageService
