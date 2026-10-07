local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local CombatShared = Shared:WaitForChild("combat")
local AnimationShared = Shared:WaitForChild("animation")
local Config = require(CombatShared:WaitForChild("AttackConfig"))
local AttackTimelineConfig = require(CombatShared:WaitForChild("AttackTimelineConfig"))
local CharacterAttackWindow = require(CombatShared:WaitForChild("CharacterAttackWindow"))
local WeaponAttackVolume = require(CombatShared:WaitForChild("WeaponAttackVolume"))
local AnimationSpeedScaling = require(AnimationShared:WaitForChild("AnimationSpeedScaling"))
local CharacterAnimationRegistry = require(CharacterShared:WaitForChild("CharacterAnimationRegistry"))
local DamageService = require(script.Parent:WaitForChild("DamageService"))
local HitEffectService = require(script.Parent:WaitForChild("HitEffectService"))
local EntityHitboxService = require(script.Parent:WaitForChild("EntityHitboxService"))

local AttackService = {}
local activeUntil: { [Player]: number } = {}
local activeSerial: { [Player]: number } = {}
local activeClientAttackId: { [Player]: number } = {}
local weaponSweepStates: { [Player]: any } = {}
local activeHitTargets: { [Player]: { [Model]: boolean } } = {}
local activeDamageWindows: { [Player]: any } = {}
local activeHeadshotTarget: { [Player]: Model } = {}

local function rowsForEquippedAttack(character: Model): any
    local profileId = tostring(character:GetAttribute("AnimationProfileId") or character:GetAttribute("CharacterArchetype") or "")
    local profile = CharacterAnimationRegistry.profiles[profileId]
    if not profile then
        return nil
    end

    local weaponSet = tostring(character:GetAttribute("AnimationWeaponSet") or "")
    if weaponSet ~= "" and weaponSet ~= "base" and weaponSet ~= "unarmed" then
        local weapon = profile.weapons and profile.weapons[weaponSet]
        if weapon and weapon.attack then
            return weapon.attack
        end
    end
    return profile.base and profile.base.attack or nil
end

local function allowedAttackDescriptor(character: Model, clipId: string): any?
    if clipId == "" then
        return nil
    end
    for _, descriptor in ipairs(rowsForEquippedAttack(character) or {}) do
        if tostring(descriptor.clipId or "") == clipId then
            return descriptor
        end
    end
    return nil
end

local function finiteNumber(value: number): boolean
    return value == value and value > -math.huge and value < math.huge
end

local function finiteVector(value: Vector3): boolean
    return finiteNumber(value.X) and finiteNumber(value.Y) and finiteNumber(value.Z)
end

local function normalizeAimSample(rootPosition: Vector3, aimOrigin: any, aimDirection: any): (Vector3?, Vector3?)
    if typeof(aimOrigin) ~= "Vector3"
        or typeof(aimDirection) ~= "Vector3"
        or not finiteVector(aimOrigin)
        or not finiteVector(aimDirection)
        or (aimOrigin - rootPosition).Magnitude > Config.HeadshotAimOriginMaxDistance
    then
        return nil, nil
    end

    local magnitude = aimDirection.Magnitude
    if magnitude <= 1e-6 then
        return nil, nil
    end
    return aimOrigin, aimDirection / magnitude
end

local function buildHeadshotAimSegment(
    rootPosition: Vector3,
    aimOrigin: any,
    aimDirection: any,
    attackRange: number
): (Vector3?, Vector3?)
    local origin, direction = normalizeAimSample(rootPosition, aimOrigin, aimDirection)
    if not origin or not direction then
        return nil, nil
    end

    -- Camera distance must not consume melee range. Keep the exact center-screen
    -- line, but rebase its finite segment to the point on that line closest to
    -- the attacker. The segment then extends exactly AttackRadius forward.
    local closestAlongRay = math.max(0, (rootPosition - origin):Dot(direction))
    return origin + direction * closestAlongRay, direction
end

local function interpolateAimDirection(previous: Vector3?, current: Vector3?, alpha: number): Vector3?
    if typeof(current) ~= "Vector3" then
        return nil
    end
    if typeof(previous) ~= "Vector3" then
        return current
    end
    local blended = previous:Lerp(current, alpha)
    if blended.Magnitude <= 1e-6 then
        return current
    end
    return blended.Unit
end

local function applyDamageInVolume(
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
    attackRange: number
): number
    local hitCount = 0
    local contacts = EntityHitboxService.QueryDamageablesInBox(character, boxCFrame, boxSize, hitTargets)

    -- Weapon contact and headshot classification are deliberately independent.
    -- The blade OBB decides which targets take melee damage. A finite reticle ray
    -- only decides whether ONE of those contacts is upgraded to a headshot.
    local aimedRegion = nil
    if #contacts > 0 and activeHeadshotTarget[player] == nil then
        local rayStart, rayDirection = buildHeadshotAimSegment(root.Position, aimOrigin, aimDirection, attackRange)
        if rayStart and rayDirection then
            aimedRegion = EntityHitboxService.RaycastAimRegions(character, rayStart, rayDirection, attackRange)
        end
    end

    for _, target in ipairs(contacts) do
        local model = target.model
        local hit = target.hit or {}
        if model
            and model:IsA("Model")
            and model:GetAttribute("Damageable") == true
            and (not hitTargets or hitTargets[model] ~= true)
        then
            local isHeadshot = activeHeadshotTarget[player] == nil
                and aimedRegion ~= nil
                and aimedRegion.zone == "head"
                and aimedRegion.model == model
            local hitZone = if isHeadshot then "head" else "body"
            local hitPosition = if typeof(hit.hitPosition) == "Vector3" then hit.hitPosition else root.Position
            local hitDistance = (hitPosition - root.Position).Magnitude
            local damageMultiplier = if isHeadshot then Config.HeadshotDamageMultiplier else 1
            local rawDamage = (tonumber(character:GetAttribute("Damage")) or 0) * damageMultiplier
            local finalDamage, killed = DamageService.Apply(character, model, rawDamage)

            model:SetAttribute("LastHitZone", hitZone)
            model:SetAttribute("LastHeadshot", isHeadshot)
            if isHeadshot then
                activeHeadshotTarget[player] = model
                character:SetAttribute("LastAttackHitZone", "head")
                character:SetAttribute("LastAttackHeadshot", true)
            elseif character:GetAttribute("LastAttackHitZone") == nil then
                character:SetAttribute("LastAttackHitZone", "body")
            end
            if hitTargets then
                hitTargets[model] = true
            end
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

    return hitCount
end

local function applyAnimatedWeaponSweep(
    player: Player,
    character: Model,
    root: BasePart,
    serial: number,
    weapon: Model,
    boxSize: Vector3,
    previousBoxCFrame: CFrame?,
    currentBoxCFrame: CFrame,
    previousAimOrigin: Vector3?,
    previousAimDirection: Vector3?,
    currentAimOrigin: Vector3?,
    currentAimDirection: Vector3?
): number
    local attackRange = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Config.Range, 1, Config.MaxAimDistance)
    local weaponBoneBoxLocalPosition = WeaponAttackVolume.ReadWeaponBoneBoxLocalPosition(weapon)
    local hitTargets = activeHitTargets[player]
    if not hitTargets then
        hitTargets = {}
        activeHitTargets[player] = hitTargets
    end

    local steps = 1
    if typeof(previousBoxCFrame) == "CFrame" then
        local linearDelta = (currentBoxCFrame.Position - previousBoxCFrame.Position).Magnitude
        local _, angularDelta = previousBoxCFrame:ToObjectSpace(currentBoxCFrame):ToAxisAngle()
        local linearSteps = math.ceil(linearDelta / math.max(0.05, Config.WeaponPoseSweepLinearStep))
        local angularSteps = math.ceil(math.abs(angularDelta) / math.max(math.rad(1), Config.WeaponPoseSweepAngularStep))
        steps = math.clamp(math.max(1, linearSteps, angularSteps), 1, Config.WeaponPoseSweepMaxSubsteps)
    end

    local hitCount = 0
    for step = 1, steps do
        local alpha = step / steps
        local sampledBoxCFrame = if typeof(previousBoxCFrame) == "CFrame"
            then previousBoxCFrame:Lerp(currentBoxCFrame, alpha)
            else currentBoxCFrame
        local sampledAimOrigin = if typeof(previousAimOrigin) == "Vector3" and typeof(currentAimOrigin) == "Vector3"
            then previousAimOrigin:Lerp(currentAimOrigin, alpha)
            else currentAimOrigin
        local sampledAimDirection = interpolateAimDirection(previousAimDirection, currentAimDirection, alpha)
        local volume = WeaponAttackVolume.Build(root.Position, sampledBoxCFrame, boxSize, attackRange, weaponBoneBoxLocalPosition)
        if volume then
            hitCount += applyDamageInVolume(
                player,
                character,
                root,
                serial,
                volume.cframe,
                volume.size,
                "animated_weapon_sweep",
                hitTargets,
                sampledAimOrigin,
                sampledAimDirection,
                attackRange
            )
        end
    end
    return hitCount
end

local function clearAttackStateLater(player: Player, character: Model, serial: number, clientAttackId: number, durationSeconds: number)
    task.delay(durationSeconds, function()
        if activeSerial[player] ~= serial or activeClientAttackId[player] ~= clientAttackId then
            return
        end
        if Config.DebugLogs and next(activeHitTargets[player] or {}) == nil then
            local attackRange = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Config.Range, 1, Config.MaxAimDistance)
            print(("[game1][attack] miss player=%s range=%.1f serial=%d source=animated_weapon_sweep")
                :format(player.Name, attackRange, serial))
        end
        activeUntil[player] = nil
        activeSerial[player] = nil
        activeClientAttackId[player] = nil
        activeHitTargets[player] = nil
        activeDamageWindows[player] = nil
        activeHeadshotTarget[player] = nil
        local sweepState = weaponSweepStates[player]
        if sweepState and sweepState.clientAttackId == clientAttackId then
            weaponSweepStates[player] = nil
        end
        if character.Parent and tonumber(character:GetAttribute("AttackSerial")) == serial then
            character:SetAttribute("AttackEndsAt", nil)
            character:SetAttribute("AttackDamageStartsAt", nil)
            character:SetAttribute("AttackDamageEndsAt", nil)
            character:SetAttribute("AttackClipId", nil)
        end
    end)
end

local function attack(player: Player, payload: any)
    if type(payload) ~= "table" then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=invalid_payload"):format(player.Name))
        end
        return
    end

    local clipId = tostring(payload.clipId or "")
    local clientAttackId = math.floor(tonumber(payload.clientAttackId) or 0)
    if clientAttackId <= 0 then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=missing_client_attack_id"):format(player.Name))
        end
        return
    end

    local character = player.Character
    local root = character and character:FindFirstChild("RootCollider")
    if not (character and root and root:IsA("BasePart")) or character:GetAttribute("LifeState") ~= "Alive" then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=character_not_ready"):format(player.Name))
        end
        return
    end

    local descriptor = allowedAttackDescriptor(character, clipId)
    if not descriptor then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=invalid_clip clip=%s"):format(player.Name, clipId))
        end
        return
    end

    local animationSpeedPercent = AnimationSpeedScaling.ResolveForModel(character, "attack")
    local timing = AttackTimelineConfig.ResolveRuntime(clipId, animationSpeedPercent)
    if not timing then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=missing_timeline clip=%s"):format(player.Name, clipId))
        end
        return
    end

    local damageWindow = CharacterAttackWindow.Resolve(timing)
    if not damageWindow then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=missing_character_damage_window clip=%s"):format(player.Name, clipId))
        end
        return
    end

    local now = os.clock()
    if now < (activeUntil[player] or 0) then
        return
    end

    local attackDuration = timing.duration
    local serial = (tonumber(character:GetAttribute("AttackSerial")) or 0) + 1
    activeSerial[player] = serial
    activeClientAttackId[player] = clientAttackId
    activeUntil[player] = now + attackDuration
    activeHitTargets[player] = {}
    activeHeadshotTarget[player] = nil
    activeDamageWindows[player] = damageWindow
    weaponSweepStates[player] = nil
    character:SetAttribute("AttackSerial", serial)
    character:SetAttribute("AttackClipId", clipId)
    character:SetAttribute("AttackStartedAt", now)
    character:SetAttribute("AttackEndsAt", now + attackDuration)
    character:SetAttribute("AttackDamageStartsAt", now + damageWindow.startTime)
    character:SetAttribute("AttackDamageEndsAt", now + damageWindow.endTime)
    character:SetAttribute("LastAttackHitZone", nil)
    character:SetAttribute("LastAttackHeadshot", false)

    -- Character weapon damage exists only inside the authored HitStart -> HitEnd
    -- interval. Hit is no longer a character damage event; monsters keep their
    -- separate single-Hit timing policy in MonsterAIService.
    clearAttackStateLater(player, character, serial, clientAttackId, attackDuration)
end

local function recordWeaponPose(player: Player, payload: any)
    if type(payload) ~= "table" or typeof(payload.boxCFrame) ~= "CFrame" then
        return
    end
    local clientAttackId = math.floor(tonumber(payload.clientAttackId) or 0)
    if clientAttackId <= 0 then
        return
    end

    local character = player.Character
    local root = character and character:FindFirstChild("RootCollider")
    local weapon = character and character:FindFirstChild("EquippedWeapon")
    if not character
        or not root
        or not root:IsA("BasePart")
        or not weapon
        or not weapon:IsA("Model")
        or tostring(character:GetAttribute("LifeState") or "") ~= "Alive"
    then
        return
    end

    local elapsed = math.max(0, tonumber(payload.elapsed) or 0)
    local damageWindow = activeDamageWindows[player]
    if activeClientAttackId[player] ~= clientAttackId
        or activeSerial[player] == nil
        or damageWindow == nil
        or elapsed + 1e-4 < damageWindow.startTime
        or elapsed > damageWindow.endTime + 1e-4
    then
        return
    end

    local _, boxSize = WeaponAttackVolume.ReadWeaponBox(weapon)
    if not boxSize then
        return
    end
    local attackRange = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Config.Range, 1, Config.MaxAimDistance)
    local maxCenterDistance = attackRange + boxSize.Magnitude + Config.WeaponPoseValidationSlack
    if (payload.boxCFrame.Position - root.Position).Magnitude > maxCenterDistance then
        return
    end

    local aimOrigin, aimDirection = normalizeAimSample(root.Position, payload.aimOrigin, payload.aimDirection)

    local sweepState = weaponSweepStates[player]
    if not sweepState or sweepState.character ~= character or sweepState.clientAttackId ~= clientAttackId then
        sweepState = {
            character = character,
            clientAttackId = clientAttackId,
        }
        weaponSweepStates[player] = sweepState
    end

    -- Accepted poses sweep continuously only inside HitStart -> HitEnd. There is
    -- no buffered terminal Hit checkpoint anymore; each accepted pose belongs to
    -- the active authored window and is resolved immediately.
    local serial = activeSerial[player]
    local lastElapsed = tonumber(sweepState.lastElapsed)
    if serial and (lastElapsed == nil or elapsed + 1e-4 >= lastElapsed) then
        local previousBoxCFrame = if typeof(sweepState.lastBoxCFrame) == "CFrame" then sweepState.lastBoxCFrame else nil
        local previousAimOrigin = if typeof(sweepState.lastAimOrigin) == "Vector3" then sweepState.lastAimOrigin else nil
        local previousAimDirection = if typeof(sweepState.lastAimDirection) == "Vector3" then sweepState.lastAimDirection else nil
        applyAnimatedWeaponSweep(
            player,
            character,
            root,
            serial,
            weapon,
            boxSize,
            previousBoxCFrame,
            payload.boxCFrame,
            previousAimOrigin,
            previousAimDirection,
            aimOrigin,
            aimDirection
        )
        sweepState.lastElapsed = elapsed
        sweepState.lastBoxCFrame = payload.boxCFrame
        sweepState.lastAimOrigin = aimOrigin
        sweepState.lastAimDirection = aimDirection
    end
end

function AttackService.Start()
    local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes") or Instance.new("Folder")
    remotes.Name = "Game1Remotes"
    remotes.Parent = ReplicatedStorage

    local event = remotes:FindFirstChild("AttackIntent") or Instance.new("RemoteEvent")
    event.Name = "AttackIntent"
    event.Parent = remotes
    event.OnServerEvent:Connect(attack)

    local poseEvent = remotes:FindFirstChild("AttackWeaponPose") or Instance.new("RemoteEvent")
    poseEvent.Name = "AttackWeaponPose"
    poseEvent.Parent = remotes
    poseEvent.OnServerEvent:Connect(recordWeaponPose)

    Players.PlayerRemoving:Connect(function(player)
        activeUntil[player] = nil
        activeSerial[player] = nil
        activeClientAttackId[player] = nil
        activeHitTargets[player] = nil
        activeDamageWindows[player] = nil
        activeHeadshotTarget[player] = nil
        weaponSweepStates[player] = nil
    end)
end

return table.freeze(AttackService)
