local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local AttackConfig = require(CombatShared:WaitForChild("AttackConfig"))
local CombatFeedbackService = require(script.Parent:WaitForChild("CombatFeedbackService"))
local CombatStateService = require(script.Parent:WaitForChild("CombatStateService"))

local DamageService = {}
local criticalRandom = Random.new()
local CRITICAL_DAMAGE_MULTIPLIER = 2

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
    local criticalChance = if attacker then math.clamp(tonumber(attacker:GetAttribute("CritChance")) or 0, 0, 100) else 0
    local critical = criticalChance > 0 and criticalRandom:NextNumber(0, 100) < criticalChance
    local damageBeforeDefense = normalizedRawDamage * (if critical then CRITICAL_DAMAGE_MULTIPLIER else 1)
    local finalDamage = math.max(0, math.floor(damageBeforeDefense - defense))
    local hp = math.max(0, tonumber(target:GetAttribute("HP")) or 0)
    local newHP = math.max(0, hp - finalDamage)

    target:SetAttribute("HP", newHP)
    target:SetAttribute("LastDamage", finalDamage)
    target:SetAttribute("LastCritical", critical)
    target:SetAttribute("LastAttackerUserId", attacker and attacker:GetAttribute("CharacterOwnerUserId") or 0)
    if attacker then
        attacker:SetAttribute("LastAttackCritical", critical)
    end

    if finalDamage > 0 then
        -- Combat state is a consequence of authoritative damage, not input intent.
        -- The same generic attributes work for player characters, monsters and NPC rigs.
        CombatStateService.ActivatePair(attacker, target)
    end

    local killed = newHP <= 0
    if killed then
        -- HP=0 is the exact death edge. Gameplay leaves Alive immediately; presentation
        -- services then play the complete authored death clip before entering DeathIdle.
        target:SetAttribute("Damageable", false)
        target:SetAttribute("LifeState", "Dying")
        target:SetAttribute("DeathStartedAt", os.clock())
    end

    CombatFeedbackService.PublishDamage(attacker, target, finalDamage, critical)

    if AttackConfig.DebugLogs then
        print(("[game1][DAMAGE] target=%s raw=%d crit=%s chance=%.1f defense=%d final=%d hp=%d->%d killed=%s"):format(
            target.Name,
            normalizedRawDamage,
            tostring(critical),
            criticalChance,
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
