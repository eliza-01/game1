-- Pure presentation decisions; no GUI, listeners or gameplay writes.
local Policy = {}
function Policy.Monster(model, context, inRange)
    if model:GetAttribute("MonsterHomeRecalling") == true then return false, false, false end
    local focused = model == context.aimed or model == context.locked
    local attackingUs = model:GetAttribute("MonsterCombatActive") == true
        and model:GetAttribute("MonsterTargetUserId") == context.userId
    local engaged = context.showAll or focused or attackingUs
    local zone = model:GetAttribute("GameplayTestZone")
    local release = type(zone) == "number" and zone <= 6
    local owner = model:GetAttribute("Game1GameplayTestOwner")
    local sameZone = release and context.playerZone == zone and owner == context.userId
    local group = model:GetAttribute("GameplayTestKind") == "group" and owner == context.userId
    local icon = sameZone or (group and inRange)
    if group then return inRange, inRange and engaged and context.hpEnabled, icon end
    if release then return sameZone and inRange, sameZone and inRange and engaged and context.hpEnabled, icon end
    local visible = inRange and engaged and context.hpEnabled
    -- HealthBarView historically suppressed the title for non-portrait GP targets.
    local hasPortrait = model:GetAttribute("GameplayTestKind") == "group" or (tonumber(zone) ~= nil and tonumber(zone) <= 6)
    return visible and (hasPortrait or owner == nil), visible, false
end
function Policy.Npc(model, context, distanceSquared)
    local maxHP = tonumber(model:GetAttribute("MaxHP")) or 0
    local hp = tonumber(model:GetAttribute("HP")) or maxHP
    local hostile = model:GetAttribute("NpcTargetUserId") == context.userId
        and model:GetAttribute("NpcAIState") ~= "Idle"
    return distanceSquared <= context.nameSq, context.hpEnabled and distanceSquared <= context.hpSq
        and (hp < maxHP - 0.001 or hostile), false
end
return table.freeze(Policy)
