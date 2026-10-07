local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local CombatShared = Shared:WaitForChild("combat")
local AnimationShared = Shared:WaitForChild("animation")
local Config = require(CombatShared:WaitForChild("AttackConfig"))
local AttackTimelineConfig = require(CombatShared:WaitForChild("AttackTimelineConfig"))
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
local weaponPoseBuffers: { [Player]: any } = {}
local activeHitTargets: { [Player]: { [Model]: boolean } } = {}

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

local function applyDamageInVolume(
    player: Player,
    character: Model,
    root: BasePart,
    serial: number,
    boxCFrame: CFrame,
    boxSize: Vector3,
    sourceLabel: string,
    hitTargets: { [Model]: boolean }?
): number
    local hitCount = 0

    -- The visible debug target hitboxes and the authoritative damage query share
    -- this exact source. Virtual bone capsules/spheres are queried directly;
    -- root-fallback targets (training dummy) use their physical RootCollider.
    for _, target in ipairs(EntityHitboxService.QueryDamageablesInBox(character, boxCFrame, boxSize)) do
        local model = target.model
        local hit = target.hit or {}
        if model
            and model:IsA("Model")
            and model:GetAttribute("Damageable") == true
            and (not hitTargets or hitTargets[model] ~= true)
        then
            local hitPosition = if typeof(hit.hitPosition) == "Vector3" then hit.hitPosition else root.Position
            local hitDistance = (hitPosition - root.Position).Magnitude
            local rawDamage = tonumber(character:GetAttribute("Damage")) or 0
            local finalDamage, killed = DamageService.Apply(character, model, rawDamage)
            if hitTargets then
                hitTargets[model] = true
            end
            HitEffectService.Publish(character, model, model:GetAttribute("LastCritical") == true, hitPosition)
            hitCount += 1
            if Config.DebugLogs then
                print(("[game1][attack] hit player=%s target=%s zone=%s distance=%.2f damage=%d targethp=%s killed=%s serial=%d source=%s hitbox=%s")
                    :format(
                        player.Name,
                        model.Name,
                        tostring(hit.hitZone or "body"),
                        hitDistance,
                        finalDamage,
                        tostring(model:GetAttribute("HP")),
                        tostring(killed),
                        serial,
                        sourceLabel,
                        tostring(target.mode or "unknown")
                    ))
            end
        end
    end

    return hitCount
end

local function hasRegisteredHit(player: Player): boolean
    for _ in pairs(activeHitTargets[player] or {}) do
        return true
    end
    return false
end

local function applyAnimatedWeaponSweep(
    player: Player,
    character: Model,
    root: BasePart,
    serial: number,
    weapon: Model,
    boxSize: Vector3,
    previousBoxCFrame: CFrame?,
    currentBoxCFrame: CFrame
): number
    local attackRange = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Config.Range, 1, Config.MaxAimDistance)
    local gripBoxLocalPosition = WeaponAttackVolume.ReadGripBoxLocalPosition(weapon)
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
        local volume = WeaponAttackVolume.Build(root.Position, sampledBoxCFrame, boxSize, attackRange, gripBoxLocalPosition)
        if volume then
            hitCount += applyDamageInVolume(
                player,
                character,
                root,
                serial,
                volume.cframe,
                volume.size,
                "animated_weapon_sweep",
                hitTargets
            )
        end
    end
    return hitCount
end

local function fallbackAimVolume(root: BasePart, aim: Vector3, attackRange: number): (CFrame, Vector3)
    local flat = Vector3.new(aim.X - root.Position.X, 0, aim.Z - root.Position.Z)
    if flat.Magnitude < 0.001 then
        flat = root.CFrame.LookVector
    end
    local direction = flat.Unit
    local center = root.Position + direction * (attackRange * 0.5)
    return CFrame.lookAt(center, center + direction), Vector3.new(Config.BoxWidth, Config.BoxHeight, attackRange)
end

local function validatedAnimatedWeaponVolume(
    player: Player,
    character: Model,
    root: BasePart,
    clientAttackId: number,
    attackRange: number,
    hitElapsed: number
): (any?, string?)
    local weapon = character:FindFirstChild("EquippedWeapon")
    if not weapon or not weapon:IsA("Model") then
        return nil, "unarmed"
    end

    local _, boxSize = WeaponAttackVolume.ReadWeaponBox(weapon)
    if not boxSize then
        return nil, "missing_weapon_box"
    end

    local buffer = weaponPoseBuffers[player]
    if not buffer or buffer.character ~= character or buffer.clientAttackId ~= clientAttackId then
        return nil, "missing_weapon_pose"
    end

    hitElapsed = math.max(0, tonumber(hitElapsed) or 0)
    local sample = nil
    local bestError = math.huge
    for _, candidate in ipairs(buffer.samples or {}) do
        if typeof(candidate.boxCFrame) == "CFrame" then
            local errorSeconds = math.abs((tonumber(candidate.elapsed) or 0) - hitElapsed)
            if errorSeconds < bestError then
                bestError = errorSeconds
                sample = candidate
            end
        end
    end
    if not sample then
        return nil, "missing_weapon_pose"
    end
    if bestError > Config.WeaponPoseHitTimeTolerance then
        return nil, "weapon_pose_outside_hit_window"
    end
    if os.clock() - sample.receivedAt > Config.WeaponPoseMaxAgeSeconds then
        return nil, "stale_weapon_pose"
    end

    local maxCenterDistance = attackRange + boxSize.Magnitude + Config.WeaponPoseValidationSlack
    if (sample.boxCFrame.Position - root.Position).Magnitude > maxCenterDistance then
        return nil, "invalid_weapon_pose"
    end

    local gripBoxLocalPosition = WeaponAttackVolume.ReadGripBoxLocalPosition(weapon)
    local volume = WeaponAttackVolume.Build(root.Position, sample.boxCFrame, boxSize, attackRange, gripBoxLocalPosition)
    if not volume then
        return nil, "invalid_weapon_volume"
    end
    return volume, nil
end

local function resolveMeleeDamage(
    player: Player,
    character: Model,
    serial: number,
    clientAttackId: number,
    aim: Vector3,
    hitElapsed: number
)
    if activeSerial[player] ~= serial
        or activeClientAttackId[player] ~= clientAttackId
        or player.Character ~= character
        or not character.Parent
        or tostring(character:GetAttribute("LifeState") or "") ~= "Alive"
    then
        return
    end

    local root = character:FindFirstChild("RootCollider")
    if not root or not root:IsA("BasePart") then
        return
    end

    local attackRange = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Config.Range, 1, Config.MaxAimDistance)
    local volume, reason = validatedAnimatedWeaponVolume(player, character, root, clientAttackId, attackRange, hitElapsed)
    local hitCount = 0

    if volume then
        -- Equipped weapons use the animated weapon OBB itself as the basis for
        -- damage. Its longest axis is extended only up to AttackRadius, making
        -- the hit volume follow the actual attack animation instead of aim yaw.
        hitCount = applyDamageInVolume(
            player,
            character,
            root,
            serial,
            volume.cframe,
            volume.size,
            "animated_weapon_volume",
            activeHitTargets[player]
        )
    elseif reason == "unarmed" then
        -- Hands keep the legacy aim volume until an authored unarmed attack box
        -- exists. Equipped weapons never fall back to this approximation.
        local boxCFrame, boxSize = fallbackAimVolume(root, aim, attackRange)
        hitCount = applyDamageInVolume(
            player,
            character,
            root,
            serial,
            boxCFrame,
            boxSize,
            "unarmed_fallback",
            activeHitTargets[player]
        )
    elseif Config.DebugLogs and not hasRegisteredHit(player) then
        print(("[game1][attack] miss player=%s range=%.1f serial=%d reason=%s")
            :format(player.Name, attackRange, serial, tostring(reason)))
        return
    else
        return
    end

    if hitCount == 0 and not hasRegisteredHit(player) and Config.DebugLogs then
        print(("[game1][attack] miss player=%s range=%.1f serial=%d source=%s")
            :format(player.Name, attackRange, serial, volume and "animated_weapon_volume" or "unarmed_fallback"))
    end
end

local function scheduleTimelineResults(
    player: Player,
    character: Model,
    serial: number,
    clientAttackId: number,
    aim: Vector3,
    timing: any
)
    for eventName, event in pairs(timing.events or {}) do
        local resultType = tostring(event.result or "")
        local delaySeconds = math.max(0, tonumber(event.time) or 0)
        if resultType == AttackTimelineConfig.ResultTypes.MeleeDamage then
            task.delay(delaySeconds, function()
                resolveMeleeDamage(player, character, serial, clientAttackId, aim, delaySeconds)
            end)
        elseif Config.DebugLogs and resultType ~= "" then
            warn(("[game1][attack] no result handler event=%s result=%s"):format(tostring(eventName), resultType))
        end
    end
end

local function clearAttackStateLater(player: Player, character: Model, serial: number, clientAttackId: number, durationSeconds: number)
    task.delay(durationSeconds, function()
        if activeSerial[player] ~= serial or activeClientAttackId[player] ~= clientAttackId then
            return
        end
        activeUntil[player] = nil
        activeSerial[player] = nil
        activeClientAttackId[player] = nil
        activeHitTargets[player] = nil
        local buffer = weaponPoseBuffers[player]
        if buffer and buffer.clientAttackId == clientAttackId then
            weaponPoseBuffers[player] = nil
        end
        if character.Parent and tonumber(character:GetAttribute("AttackSerial")) == serial then
            character:SetAttribute("AttackEndsAt", nil)
            character:SetAttribute("AttackClipId", nil)
        end
    end)
end

local function attack(player: Player, payload: any)
    if type(payload) ~= "table" or typeof(payload.aim) ~= "Vector3" then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=invalid_payload"):format(player.Name))
        end
        return
    end

    local aim: Vector3 = payload.aim
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
    local timing = AttackTimelineConfig.ResolveRuntime(clipId, animationSpeedPercent, descriptor.duplicateFirstFrameAtEnd == true)
    if not timing then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=missing_timeline clip=%s"):format(player.Name, clipId))
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
    character:SetAttribute("AttackSerial", serial)
    character:SetAttribute("AttackClipId", clipId)
    character:SetAttribute("AttackStartedAt", now)
    character:SetAttribute("AttackEndsAt", now + attackDuration)

    -- Equipped weapon damage is primarily resolved continuously from accepted
    -- animated pose contacts. The authored Hit event remains a compatibility
    -- checkpoint (and still owns unarmed fallback damage) rather than the only
    -- instant at which an equipped weapon is allowed to connect.
    scheduleTimelineResults(player, character, serial, clientAttackId, aim, timing)
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

    local _, boxSize = WeaponAttackVolume.ReadWeaponBox(weapon)
    if not boxSize then
        return
    end
    local attackRange = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Config.Range, 1, Config.MaxAimDistance)
    local maxCenterDistance = attackRange + boxSize.Magnitude + Config.WeaponPoseValidationSlack
    if (payload.boxCFrame.Position - root.Position).Magnitude > maxCenterDistance then
        return
    end

    local elapsed = math.max(0, tonumber(payload.elapsed) or 0)
    local buffer = weaponPoseBuffers[player]
    if not buffer or buffer.character ~= character or buffer.clientAttackId ~= clientAttackId then
        buffer = {
            character = character,
            clientAttackId = clientAttackId,
            samples = {},
        }
        weaponPoseBuffers[player] = buffer
    end
    table.insert(buffer.samples, {
        elapsed = elapsed,
        boxCFrame = payload.boxCFrame,
        receivedAt = os.clock(),
    })
    while #buffer.samples > Config.WeaponPoseBufferSize do
        table.remove(buffer.samples, 1)
    end

    -- Weapon attacks are contact-driven, not single-frame timeline snapshots.
    -- Every accepted animated weapon pose participates in the attack sweep while
    -- this attack is active. Interpolate between samples so a fast blade cannot
    -- tunnel through a target between two 30 Hz pose packets. Each target is
    -- damaged at most once per attack, while different intersected targets can
    -- all be damaged by the same sweep.
    local serial = activeSerial[player]
    local attackEndsAt = activeUntil[player]
    local lastDamageElapsed = tonumber(buffer.lastDamageElapsed)
    if serial
        and activeClientAttackId[player] == clientAttackId
        and attackEndsAt ~= nil
        and os.clock() <= attackEndsAt
        and (lastDamageElapsed == nil or elapsed + 1e-4 >= lastDamageElapsed)
    then
        local previousBoxCFrame = if typeof(buffer.lastDamageBoxCFrame) == "CFrame" then buffer.lastDamageBoxCFrame else nil
        applyAnimatedWeaponSweep(
            player,
            character,
            root,
            serial,
            weapon,
            boxSize,
            previousBoxCFrame,
            payload.boxCFrame
        )
        buffer.lastDamageElapsed = elapsed
        buffer.lastDamageBoxCFrame = payload.boxCFrame
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
        weaponPoseBuffers[player] = nil
    end)
end

return table.freeze(AttackService)
