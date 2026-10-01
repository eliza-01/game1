local DamageService = {}
function DamageService.Apply(attacker: Model?, target: Model, rawDamage: number): (number, boolean)
    if target:GetAttribute("Damageable") ~= true or target:GetAttribute("LifeState") ~= "Alive" then return 0, false end
    local defense = math.max(0, tonumber(target:GetAttribute("Defense")) or 0)
    local finalDamage = math.max(0, math.floor((tonumber(rawDamage) or 0) - defense))
    local hp = math.max(0, tonumber(target:GetAttribute("HP")) or 0)
    local newHP = math.max(0, hp - finalDamage)
    target:SetAttribute("HP", newHP)
    target:SetAttribute("LastDamage", finalDamage)
    target:SetAttribute("LastAttackerUserId", attacker and attacker:GetAttribute("CharacterOwnerUserId") or 0)
    if newHP <= 0 then target:SetAttribute("LifeState", "Dead") end
    return finalDamage, newHP <= 0
end
return DamageService
