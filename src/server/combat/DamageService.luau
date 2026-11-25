local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local AttackConfig = require(CombatShared:WaitForChild("AttackConfig"))
local CombatFeedbackService = require(script.Parent:WaitForChild("CombatFeedbackService"))
local CombatStateService = require(script.Parent:WaitForChild("CombatStateService"))
local ActorDamageSignals = require(script.Parent:WaitForChild("ActorDamageSignals"))

local Isolation = require(script.Parent.Parent:WaitForChild("dev"):WaitForChild("GameplayTestIsolation"))
local Healing = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CharacterHealing"))
local DamageService = {}
local criticalRandom = Random.new()
local Balance = require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local CRITICAL_DAMAGE_MULTIPLIER = Balance.Rules.critMultiplier
local Critical = require(Shared:WaitForChild("balance"):WaitForChild("CriticalStats"))

function DamageService.Apply(attacker: Model?, target: Model, rawDamage: number, headshot: boolean?, periodic: boolean?): (number, boolean)
    if not Isolation.Allows(attacker, target) then return 0, false end
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

    local defense = if periodic then 0 else math.max(0, tonumber(target:GetAttribute("Defense")) or 0)
    local normalizedRawDamage = math.max(0, tonumber(rawDamage) or 0)
    local criticalChance = if attacker then Critical.Chance(tonumber(attacker:GetAttribute("CritChance")) or 0) else 0
    local critical = not periodic and criticalChance > 0 and criticalRandom:NextNumber(0, 100) < criticalChance
    local criticalMultiplier = if attacker then Critical.Multiplier(attacker:GetAttribute("CritMultiplier")) else CRITICAL_DAMAGE_MULTIPLIER
    local damageBeforeDefense = normalizedRawDamage * (if critical then criticalMultiplier else 1)
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

    -- Only HP actually removed (not overkill) contributes to lifesteal.
    if not periodic then Healing.OnDamage(attacker, target, hp - newHP) end
    ActorDamageSignals.Publish(attacker, target, normalizedRawDamage, finalDamage, killed)
    CombatFeedbackService.PublishDamage(attacker, target, finalDamage, critical, headshot == true)

    if AttackConfig.DebugLogs then
        print(("[game1][DAMAGE] target=%s raw=%d crit=%s chance=%.1f defense=%d final=%d hp=%.1f->%.1f killed=%s"):format(
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
