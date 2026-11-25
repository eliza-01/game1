-- M358 · Server-authoritative arc contacts; a reticle ray can only UPGRADE
-- an already valid arc target to one headshot. Never adds out-of-arc damage.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local CombatShared = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("combat")
local Config = require(CombatShared:WaitForChild("AttackConfig"))
local AttackAimGeometry = require(CombatShared:WaitForChild("AttackAimGeometry"))
local DamageService = require(script.Parent:WaitForChild("DamageService"))
local HitEffectService = require(script.Parent:WaitForChild("HitEffectService"))
local EntityHitboxService = require(script.Parent:WaitForChild("EntityHitboxService"))
local MeleeTargetQuery = require(script.Parent:WaitForChild("MeleeTargetQuery"))

local AttackDamageResolver = {}

export type DamageQuery = {
    player: Player,
    character: Model,
    root: BasePart,
    serial: number,
    aimOrigin: Vector3?,
    aimDirection: Vector3?,
    attackRange: number,
    arcAngleDegrees: number,
    verticalPadding: number,
    facingDirection: Vector3?,
    baseDamage: number?,
}

function AttackDamageResolver.Apply(query: DamageQuery): (number, Model?, number)
    local character, root = query.character, query.root
    local targets = MeleeTargetQuery.Find(character, root, query.attackRange,
        query.arcAngleDegrees, query.verticalPadding, query.facingDirection)
    local aimedHead = nil
    -- A completely empty arc cannot produce a headshot. Do not run the
    -- global bone-raycast/occlusion checks when there is no eligible victim.
    if #targets > 0 then
        local rayStart, rayDirection = AttackAimGeometry.HeadshotSegment(root.Position,
            query.aimOrigin, query.aimDirection, query.attackRange)
        if rayStart and rayDirection then
            local aimed = EntityHitboxService.RaycastAimRegions(character, rayStart, rayDirection, query.attackRange)
            if aimed and aimed.zone == "head"
                and AttackAimGeometry.HitWithinAttackRadius(root.Position, aimed.hitPosition, query.attackRange)
                and MeleeTargetQuery.IsUnobstructed(character, aimed.model, root, aimed.hitPosition)
            then
                -- The target must also be in THIS server-evaluated arc sample.
                for _, contact in ipairs(targets) do
                    if contact.model == aimed.model then
                        aimedHead = aimed
                        break
                    end
                end
            end
        end
    end

    local hitCount, damagedTargets = 0, 0
    local headshotTarget = nil
    for _, contact in ipairs(targets) do
        local model = contact.model
        if model and model.Parent and model:GetAttribute("Damageable") == true
            then
            local isHeadshot = aimedHead ~= nil and aimedHead.model == model
            local hitPosition = if isHeadshot then aimedHead.hitPosition else contact.hit.hitPosition
            local hitZone = if isHeadshot then "head" else "body"
            local damageMultiplier = if isHeadshot then Config.HeadshotDamageMultiplier else 1
            local rawDamage = (query.baseDamage or tonumber(character:GetAttribute("Damage")) or 0) * damageMultiplier
            local finalDamage, killed = DamageService.Apply(character, model, rawDamage, isHeadshot)
            model:SetAttribute("LastHitZone", hitZone)
            model:SetAttribute("LastHeadshot", isHeadshot)
            if isHeadshot then
                headshotTarget = model
                character:SetAttribute("LastAttackHitZone", "head")
                character:SetAttribute("LastAttackHeadshot", true)
            elseif character:GetAttribute("LastAttackHitZone") == nil then
                character:SetAttribute("LastAttackHitZone", "body")
            end
            if finalDamage > 0 then
                damagedTargets += 1
                HitEffectService.Publish(character, model, model:GetAttribute("LastCritical") == true, hitPosition)
            end
            hitCount += 1
            if Config.DebugLogs then
                print(("[game1][melee-arc] hit player=%s target=%s zone=%s damage=%d killed=%s serial=%d reach=%.2f arc=%.1f")
                    :format(query.player.Name, model.Name, hitZone, finalDamage, tostring(killed),
                        query.serial, query.attackRange, query.arcAngleDegrees))
            end
        end
    end
    return hitCount, headshotTarget, damagedTargets
end

return table.freeze(AttackDamageResolver)
