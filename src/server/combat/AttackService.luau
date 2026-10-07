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
local activeDamageUntil: { [Player]: number } = {}
local activeDamageCutoffElapsed: { [Player]: number } = {}

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

local function meleeHitTime(timing: any): number?
    local hit = timing and timing.events and timing.events.Hit
    if type(hit) ~= "table" or tostring(hit.result or "") ~= AttackTimelineConfig.ResultTypes.MeleeDamage then
        return nil
    end
    local hitTime = tonumber(hit.time)
    if hitTime == nil then
        return nil
    end
    return math.clamp(hitTime, 0, math.max(0, tonumber(timing.duration) or 0))
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

    -- Target geometry is a precomputed set of tight bone-local boxes derived
    -- from the visual mesh once when the rig is loaded. Runtime melee does only
    -- OBB-vs-OBB tests; the head box has priority over all body boxes.
    for _, target in ipairs(EntityHitboxService.QueryDamageablesInBox(character, boxCFrame, boxSize, hitTargets)) do
        local model = target.model
        local hit = target.hit or {}
        if model
            and model:IsA("Model")
            and model:GetAttribute("Damageable") == true
            and (not hitTargets or hitTargets[model] ~= true)
        then
            local hitPosition = if typeof(hit.hitPosition) == "Vector3" then hit.hitPosition else root.Position
            local hitDistance = (hitPosition - root.Position).Magnitude
            local hitZone = tostring(hit.hitZone or "body")
            local damageMultiplier = if hitZone == "head" then Config.HeadshotDamageMultiplier else 1
            local rawDamage = (tonumber(character:GetAttribute("Damage")) or 0) * damageMultiplier
            local finalDamage, killed = DamageService.Apply(character, model, rawDamage)
            model:SetAttribute("LastHitZone", hitZone)
            model:SetAttribute("LastHeadshot", hitZone == "head")
            character:SetAttribute("LastAttackHitZone", hitZone)
            character:SetAttribute("LastAttackHeadshot", hitZone == "head")
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
                        hitZone,
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
                hitTargets
            )
        end
    end
    return hitCount
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
        return nil, "missing_equipped_weapon"
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

    local weaponBoneBoxLocalPosition = WeaponAttackVolume.ReadWeaponBoneBoxLocalPosition(weapon)
    local volume = WeaponAttackVolume.Build(root.Position, sample.boxCFrame, boxSize, attackRange, weaponBoneBoxLocalPosition)
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

    local cutoffElapsed = activeDamageCutoffElapsed[player]
    if cutoffElapsed == nil or hitElapsed > cutoffElapsed + 1e-4 then
        return
    end

    -- Hit is the terminal damage moment. Close the continuous contact window
    -- before resolving this exact timeline checkpoint so no later pose packet
    -- can deal damage, even if it arrives in the same server frame.
    activeDamageUntil[player] = nil

    local root = character:FindFirstChild("RootCollider")
    if not root or not root:IsA("BasePart") then
        return
    end

    local attackRange = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Config.Range, 1, Config.MaxAimDistance)
    local volume, reason = validatedAnimatedWeaponVolume(player, character, root, clientAttackId, attackRange, hitElapsed)
    if not volume then
        if Config.DebugLogs and not hasRegisteredHit(player) then
            print(("[game1][attack] miss player=%s range=%.1f serial=%d reason=%s")
                :format(player.Name, attackRange, serial, tostring(reason)))
        end
        return
    end

    -- Final Hit checkpoint uses the same bone-to-blade attacking OBB as the
    -- continuous pre-Hit sweep. It may register contact at Hit itself, but never
    -- reopens the damage window afterwards.
    local hitCount = applyDamageInVolume(
        player,
        character,
        root,
        serial,
        volume.cframe,
        volume.size,
        "animated_weapon_volume",
        activeHitTargets[player]
    )

    if hitCount == 0 and not hasRegisteredHit(player) and Config.DebugLogs then
        print(("[game1][attack] miss player=%s range=%.1f serial=%d source=animated_weapon_volume")
            :format(player.Name, attackRange, serial))
    end
end

local function scheduleTimelineResults(
    player: Player,
    character: Model,
    serial: number,
    clientAttackId: number,
    timing: any
)
    for eventName, event in pairs(timing.events or {}) do
        local resultType = tostring(event.result or "")
        local delaySeconds = math.max(0, tonumber(event.time) or 0)
        if eventName == "Hit" and resultType == AttackTimelineConfig.ResultTypes.MeleeDamage then
            task.delay(delaySeconds, function()
                resolveMeleeDamage(player, character, serial, clientAttackId, delaySeconds)
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
        activeDamageUntil[player] = nil
        activeDamageCutoffElapsed[player] = nil
        local buffer = weaponPoseBuffers[player]
        if buffer and buffer.clientAttackId == clientAttackId then
            weaponPoseBuffers[player] = nil
        end
        if character.Parent and tonumber(character:GetAttribute("AttackSerial")) == serial then
            character:SetAttribute("AttackEndsAt", nil)
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
    local timing = AttackTimelineConfig.ResolveRuntime(clipId, animationSpeedPercent, descriptor.duplicateFirstFrameAtEnd == true)
    if not timing then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=missing_timeline clip=%s"):format(player.Name, clipId))
        end
        return
    end

    local hitTime = meleeHitTime(timing)
    if hitTime == nil then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=missing_melee_hit_event clip=%s"):format(player.Name, clipId))
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
    activeDamageCutoffElapsed[player] = hitTime
    activeDamageUntil[player] = now + hitTime
    character:SetAttribute("AttackSerial", serial)
    character:SetAttribute("AttackClipId", clipId)
    character:SetAttribute("AttackStartedAt", now)
    character:SetAttribute("AttackEndsAt", now + attackDuration)
    character:SetAttribute("AttackDamageEndsAt", now + hitTime)

    -- Equipped weapon damage is contact-driven only from attack start through
    -- the authored Hit moment. Hit itself is the terminal checkpoint; the rest
    -- of the animation is presentation/cooldown only and cannot deal damage.
    scheduleTimelineResults(player, character, serial, clientAttackId, timing)
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
    local damageUntil = activeDamageUntil[player]
    local damageCutoffElapsed = activeDamageCutoffElapsed[player]
    if activeClientAttackId[player] ~= clientAttackId
        or activeSerial[player] == nil
        or damageUntil == nil
        or damageCutoffElapsed == nil
        or os.clock() > damageUntil
        or elapsed > damageCutoffElapsed + 1e-4
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

    -- Accepted poses sweep continuously only up to the authored Hit event.
    -- Interpolation prevents tunnelling between 30 Hz packets; one target is
    -- still damaged at most once per attack.
    local serial = activeSerial[player]
    local lastDamageElapsed = tonumber(buffer.lastDamageElapsed)
    if serial
        and activeClientAttackId[player] == clientAttackId
        and activeDamageUntil[player] ~= nil
        and os.clock() <= activeDamageUntil[player]
        and elapsed <= damageCutoffElapsed + 1e-4
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
        activeDamageUntil[player] = nil
        activeDamageCutoffElapsed[player] = nil
        weaponPoseBuffers[player] = nil
    end)
end

return table.freeze(AttackService)
