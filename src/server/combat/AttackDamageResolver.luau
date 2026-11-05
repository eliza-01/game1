-- Authoritative reticle-ray + weapon-volume melee damage resolution. No session ownership:
-- caller owns hitTargets/headshotTarget and persists the returned headshot target.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local CombatShared = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("combat")
local Config = require(CombatShared:WaitForChild("AttackConfig"))
local AttackAimGeometry = require(CombatShared:WaitForChild("AttackAimGeometry"))
local DamageService = require(script.Parent:WaitForChild("DamageService"))
local HitEffectService = require(script.Parent:WaitForChild("HitEffectService"))
local EntityHitboxService = require(script.Parent:WaitForChild("EntityHitboxService"))

local AttackDamageResolver = {}

export type DamageQuery = {
    player: Player,
    character: Model,
    root: BasePart,
    serial: number,
    boxCFrame: CFrame,
    boxSize: Vector3,
    sourceLabel: string,
    hitTargets: { [Model]: boolean }?,
    aimOrigin: Vector3?,
    aimDirection: Vector3?,
    attackRange: number,
    headshotTarget: Model?,
}

function AttackDamageResolver.Apply(query: DamageQuery): (number, Model?)
    local player = query.player
    local character = query.character
    local root = query.root
    local serial = query.serial
    local boxCFrame = query.boxCFrame
    local boxSize = query.boxSize
    local sourceLabel = query.sourceLabel
    local hitTargets = query.hitTargets or {}
    local aimOrigin = query.aimOrigin
    local aimDirection = query.aimDirection
    local attackRange = query.attackRange
    local headshotTarget = query.headshotTarget
    local hitCount = 0
    local contacts = EntityHitboxService.QueryDamageablesInBox(character, boxCFrame, boxSize, hitTargets)

    -- The reticle ray contributes ONE nearest aimed target independently of blade
    -- contact, but only when its actual hit point is within AttackRadius. Weapon
    -- volume contacts remain unrestricted by that radius (authored blade length).
    local aimedRegion = nil
    local rayStart, rayDirection = AttackAimGeometry.HeadshotSegment(root.Position, aimOrigin, aimDirection, attackRange)
    if rayStart and rayDirection then
        local candidate = EntityHitboxService.RaycastAimRegions(character, rayStart, rayDirection, attackRange)
        if candidate and AttackAimGeometry.HitWithinAttackRadius(root.Position, candidate.hitPosition, attackRange) then
            aimedRegion = candidate
            -- Aim first: if the blade also overlaps this target, shared hitTargets
            -- suppresses a second damage event. Other blade contacts still land.
            table.insert(contacts, 1, {
                model = candidate.model,
                hit = {
                    hitPosition = candidate.hitPosition,
                    geometryRole = candidate.zone,
                },
                mode = "reticle_ray",
            })
        end
    end

    for _, target in ipairs(contacts) do
        local model = target.model
        local hit = target.hit or {}
        if model
            and model:IsA("Model")
            and model:GetAttribute("Damageable") == true
            and hitTargets[model] ~= true
        then
            local isHeadshot = headshotTarget == nil
                and aimedRegion ~= nil
                and aimedRegion.zone == "head"
                and aimedRegion.model == model
            local hitZone = if isHeadshot then "head" else "body"
            local hitPosition = if typeof(hit.hitPosition) == "Vector3" then hit.hitPosition else root.Position
            local hitDistance = (hitPosition - root.Position).Magnitude
            local damageMultiplier = if isHeadshot then Config.HeadshotDamageMultiplier else 1
            local rawDamage = (tonumber(character:GetAttribute("Damage")) or 0) * damageMultiplier
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
            hitTargets[model] = true
            HitEffectService.Publish(character, model, model:GetAttribute("LastCritical") == true, hitPosition)
            hitCount += 1
            if Config.DebugLogs then
                print(("[game1][attack] hit player=%s target=%s zone=%s distance=%.2f damage=%d targethp=%s killed=%s serial=%d source=%s hitbox=%s contact=%s")
                    :format(
                        player.Name,
                        model.Name,
                        hitZone,
                        hitDistance,
                        finalDamage,
                        tostring(model:GetAttribute("HP")),
                        tostring(killed),
                        serial,
                        sourceLabel,
                        tostring(target.mode or "unknown"),
                        tostring(hit.geometryRole or "unknown")
                    ))
            end
        end
    end

    return hitCount, headshotTarget
end

return table.freeze(AttackDamageResolver)
