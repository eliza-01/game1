local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local CombatShared = Shared:WaitForChild("combat")
local Config = require(CombatShared:WaitForChild("AttackConfig"))
local AttackTimelineConfig = require(CombatShared:WaitForChild("AttackTimelineConfig"))
local CharacterAttackWindow = require(CombatShared:WaitForChild("CharacterAttackWindow"))
local WeaponAttackVolume = require(CombatShared:WaitForChild("WeaponAttackVolume"))
local WeaponBounceConfig = require(CombatShared:WaitForChild("WeaponBounceConfig"))
local CharacterAnimationRegistry = require(CharacterShared:WaitForChild("CharacterAnimationRegistry"))
local AttackAimGeometry = require(CombatShared:WaitForChild("AttackAimGeometry"))
local BowAimGeometry = require(CombatShared:WaitForChild("BowAimGeometry"))
local BowProjectileConfig = require(CombatShared:WaitForChild("BowProjectileConfig"))
local BowProjectileService = require(script.Parent:WaitForChild("BowProjectileService"))
local WeaponEnvironmentCollision = require(script.Parent:WaitForChild("WeaponEnvironmentCollision"))
local AttackDamageResolver = require(script.Parent:WaitForChild("AttackDamageResolver"))
local AttackSessionStore = require(script.Parent:WaitForChild("AttackSessionStore"))
local HostilePursuitRegistry = require(script.Parent:WaitForChild("HostilePursuitRegistry"))
local WeaponBounceService = require(script.Parent:WaitForChild("WeaponBounceService"))

-- A decorative reaction must not prevent the authoritative combat module from starting.
local swayOk, swayModule = pcall(function()
    return require(script.Parent.Parent:WaitForChild("world"):WaitForChild("LandscapeSwayService"))
end)
local LandscapeSwayService = if swayOk then swayModule else nil

local AttackService = {}
local pendingBowReleases: { [Player]: any } = {}

local function rowsForEquippedAttack(character: Model): any
    local profileId = tostring(character:GetAttribute("AnimationProfileId") or character:GetAttribute("CharacterArchetype") or "")
    local profile = CharacterAnimationRegistry.profiles[profileId]
    if not profile then
        return nil
    end

    local weaponSet = tostring(character:GetAttribute("AnimationWeaponSet") or "")
    if weaponSet ~= "" and weaponSet ~= "base" and weaponSet ~= "unarmed" then
        local weapon = profile.weapons and profile.weapons[weaponSet]
        if weapon and weapon.attack then return weapon.attack end
        -- In particular, a bow may NEVER fire using the fallback hands clip.
        if weaponSet == "bow" then return nil end
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
    hitTargets: { [Model]: boolean }?,
    aimOrigin: Vector3?,
    aimDirection: Vector3?,
    attackRange: number
): number
    local hitCount, headshotTarget = AttackDamageResolver.Apply({
        player = player,
        character = character,
        root = root,
        serial = serial,
        boxCFrame = boxCFrame,
        boxSize = boxSize,
        sourceLabel = sourceLabel,
        hitTargets = hitTargets,
        aimOrigin = aimOrigin,
        aimDirection = aimDirection,
        attackRange = attackRange,
        headshotTarget = AttackSessionStore.HeadshotTarget(player),
    })
    AttackSessionStore.SetHeadshotTarget(player, headshotTarget)
    return hitCount
end

local triggerWeaponBounce

local function applyAnimatedWeaponSweep(
    player: Player,
    character: Model,
    root: BasePart,
    serial: number,
    clientAttackId: number,
    clipId: string,
    weapon: Model,
    boxSize: Vector3,
    previousBoxCFrame: CFrame?,
    currentBoxCFrame: CFrame,
    previousElapsed: number?,
    currentElapsed: number,
    previousAimOrigin: Vector3?,
    previousAimDirection: Vector3?,
    currentAimOrigin: Vector3?,
    currentAimDirection: Vector3?
): (number, boolean)
    local attackRange = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Config.Range, 1, Config.MaxAimDistance)
    local weaponBoneBoxLocalPosition = WeaponAttackVolume.ReadWeaponBoneBoxLocalPosition(weapon)
    local hitTargets = AttackSessionStore.HitTargets(player, character, serial, clientAttackId)
    if not hitTargets then
        return 0, false
    end

    local steps = 1
    if typeof(previousBoxCFrame) == "CFrame" then
        local linearDelta = (currentBoxCFrame.Position - previousBoxCFrame.Position).Magnitude
        local _, angularDelta = previousBoxCFrame:ToObjectSpace(currentBoxCFrame):ToAxisAngle()
        local linearSteps = math.ceil(linearDelta / math.max(0.05, Config.WeaponPoseSweepLinearStep))
        local angularSteps = math.ceil(math.abs(angularDelta) / math.max(math.rad(1), Config.WeaponPoseSweepAngularStep))
        steps = math.clamp(math.max(1, linearSteps, angularSteps), 1, Config.WeaponPoseSweepMaxSubsteps)
    end

    local previousVolume = nil
    if typeof(previousBoxCFrame) == "CFrame" then
        previousVolume = WeaponAttackVolume.Build(
            root.Position,
            previousBoxCFrame,
            boxSize,
            attackRange,
            weaponBoneBoxLocalPosition
        )
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
        local sampledAimDirection = AttackAimGeometry.InterpolateDirection(previousAimDirection, currentAimDirection, alpha)
        local sampledElapsed = if previousElapsed ~= nil
            then previousElapsed + (currentElapsed - previousElapsed) * alpha
            else currentElapsed
        local volume = WeaponAttackVolume.Build(root.Position, sampledBoxCFrame, boxSize, attackRange, weaponBoneBoxLocalPosition)
        if volume then
            -- Keep the authored HitStart -> HitEnd environment query unchanged.
            -- Combat/pursuit suppresses only the bounce RESPONSE to a real contact.
            local environmentContact = WeaponEnvironmentCollision.Query(previousVolume, volume)
            if LandscapeSwayService then LandscapeSwayService.Melee(volume, root.Position) end
            if environmentContact then
                local pursuerCount = HostilePursuitRegistry.Count(character)
                if character:GetAttribute("InCombat") == true or pursuerCount > 0 then
                    -- One informative line per affected attack, no Command Bar script.
                    if Config.DebugLogs and AttackSessionStore.FirstBounceSuppression(player) then
                        print(("[game1][weapon-bounce] suppressed player=%s combat=%s pursuers=%d")
                            :format(player.Name, tostring(character:GetAttribute("InCombat")), pursuerCount))
                    end
                else
                    local bounced = triggerWeaponBounce(
                        player,
                        character,
                        serial,
                        clientAttackId,
                        clipId,
                        sampledElapsed,
                        environmentContact
                    )
                    if bounced then
                        return hitCount, true
                    end
                end
            end

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
            previousVolume = volume
        end
    end
    return hitCount, false
end

local function clearAttackState(
    player: Player,
    character: Model,
    serial: number,
    clientAttackId: number,
    reportMiss: boolean
): boolean
    local finished = AttackSessionStore.Finish(player, character, serial, clientAttackId)
    if not finished then
        return false
    end

    if reportMiss
        and Config.DebugLogs
        and finished.environmentBlocked ~= true
        and next(finished.hitTargets) == nil
    then
        local attackRange = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Config.Range, 1, Config.MaxAimDistance)
        print(("[game1][attack] miss player=%s range=%.1f serial=%d source=animated_weapon_sweep")
            :format(player.Name, attackRange, serial))
    end

    if character.Parent and tonumber(character:GetAttribute("AttackSerial")) == serial then
        character:SetAttribute("AttackEndsAt", nil)
        character:SetAttribute("AttackDamageStartsAt", nil)
        character:SetAttribute("AttackDamageEndsAt", nil)
        character:SetAttribute("AttackClipId", nil)
        character:SetAttribute("AttackReleaseAt", nil)
    end
    return true
end

local function clearAttackStateLater(
    player: Player,
    character: Model,
    serial: number,
    clientAttackId: number,
    durationSeconds: number,
    reportMiss: boolean
)
    task.delay(durationSeconds, function()
        clearAttackState(player, character, serial, clientAttackId, reportMiss)
    end)
end

triggerWeaponBounce = function(
    player: Player,
    character: Model,
    serial: number,
    clientAttackId: number,
    clipId: string,
    elapsed: number,
    contact: any
): boolean
    if not AttackSessionStore.CanBounce(player, character, serial, clientAttackId) then
        return false
    end

    local reverseSeconds = math.max(0, elapsed) / math.max(0.1, WeaponBounceConfig.ReverseSpeedMultiplier)
    local recoverySeconds = math.max(
        WeaponBounceConfig.MinimumRecoverySeconds,
        reverseSeconds + WeaponBounceConfig.RecoverySeconds
    )
    local now = os.clock()
    if not AttackSessionStore.BlockForBounce(player, character, serial, clientAttackId, now + recoverySeconds) then
        return false
    end
    character:SetAttribute("AttackEndsAt", now + recoverySeconds)
    character:SetAttribute("AttackDamageEndsAt", now)
    character:SetAttribute("LastAttackBounced", true)

    WeaponBounceService.Publish(player, {
        clientAttackId = clientAttackId,
        clipId = clipId,
        position = contact.position,
        normal = contact.normal,
        assetId = tostring(contact.definition and contact.definition.slug or ""),
        reverseSpeedMultiplier = WeaponBounceConfig.ReverseSpeedMultiplier,
    })

    if Config.DebugLogs then
        print(("[game1][attack] bounce player=%s asset=%s part=%s elapsed=%.3f serial=%d")
            :format(
                player.Name,
                tostring(contact.definition and contact.definition.slug or "unknown"),
                tostring(contact.part and contact.part:GetFullName() or "unknown"),
                elapsed,
                serial
            ))
    end

    clearAttackStateLater(player, character, serial, clientAttackId, recoverySeconds, false)
    return true
end

-- Aim packets can only update an already accepted, unreleased bow attack.
-- The server owns the release clock, not a client marker or attack timestamp.
local function updateBowAim(player: Player, payload: any)
    if type(payload) ~= "table" then return end
    local pending = pendingBowReleases[player]
    if not pending or pending.clientAttackId ~= math.floor(tonumber(payload.clientAttackId) or 0) then return end
    local now = os.clock()
    if now > pending.releaseAt or now - pending.lastUpdate < BowProjectileConfig.AimUpdateInterval * 0.5 then return end
    if player.Character ~= pending.character then return end
    local session = AttackSessionStore.Get(player)
    if not session or session.serial ~= pending.serial or session.character ~= pending.character then return end
    local root = pending.character:FindFirstChild("RootCollider")
    if not root or not root:IsA("BasePart") then return end
    local origin, direction = BowAimGeometry.Validate(root, payload.aimOrigin, payload.aimDirection)
    if not origin or not direction then return end
    pending.aimOrigin = origin
    pending.aimDirection = direction
    pending.lastUpdate = now
end

local function beginBowRelease(player: Player, character: Model, root: BasePart,
    clientAttackId: number, serial: number, timing: any, payload: any): boolean
    local releaseEvent = timing.events and timing.events[BowProjectileConfig.ReleaseEvent]
    local releaseTime = releaseEvent and tonumber(releaseEvent.time)
    if not releaseTime or releaseTime < 0 or releaseTime > timing.duration then return false end
    local origin, direction = BowAimGeometry.Validate(root, payload.aimOrigin, payload.aimDirection)
    if not origin or not direction then return false end
    local pending = {
        character = character,
        serial = serial,
        clientAttackId = clientAttackId,
        aimOrigin = origin,
        aimDirection = direction,
        releaseAt = os.clock() + releaseTime,
        lastUpdate = 0,
    }
    pendingBowReleases[player] = pending
    task.delay(releaseTime, function()
        if pendingBowReleases[player] ~= pending then return end
        pendingBowReleases[player] = nil
        local session = AttackSessionStore.Get(player)
        if player.Character ~= character or not session or session.serial ~= serial
            or session.clientAttackId ~= clientAttackId then return end
        BowProjectileService.Release(player, character, pending.aimOrigin, pending.aimDirection)
    end)
    return true
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

    -- Server cadence is authoritative and does not depend on the submitted clip
    -- length or a per-clip animation scaling override.
    local timing = AttackTimelineConfig.ResolveCharacterRuntime(clipId, character:GetAttribute("AttackSpeed"))
    if not timing then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=missing_timeline clip=%s"):format(player.Name, clipId))
        end
        return
    end

    local isBow = string.lower(tostring(character:GetAttribute("EquippedWeaponType") or "")) == "bow"
    local releaseEvent = if isBow then timing.events and timing.events[BowProjectileConfig.ReleaseEvent] else nil
    local damageWindow = if isBow then nil else CharacterAttackWindow.Resolve(timing)
    if (isBow and not releaseEvent) or (not isBow and not damageWindow) then
        if Config.DebugLogs then
            print(("[game1][attack] reject player=%s reason=missing_character_damage_window clip=%s"):format(player.Name, clipId))
        end
        return
    end

    -- No bow is allowed to reuse melee attack windows or an unvalidated camera.
    if isBow then
        if tostring(character:GetAttribute("AnimationWeaponSet") or "") ~= "bow" then return end
        local origin, direction = BowAimGeometry.Validate(root, payload.aimOrigin, payload.aimDirection)
        if not origin or not direction then return end
    end

    local now = os.clock()
    if AttackSessionStore.IsCoolingDown(player, now) then
        return
    end

    local attackDuration = timing.duration
    local serial = (tonumber(character:GetAttribute("AttackSerial")) or 0) + 1
    AttackSessionStore.Begin(player, character, serial, clientAttackId, now + attackDuration, damageWindow)
    character:SetAttribute("AttackSerial", serial)
    character:SetAttribute("AttackClipId", clipId)
    character:SetAttribute("AttackStartedAt", now)
    character:SetAttribute("AttackEndsAt", now + attackDuration)
    character:SetAttribute("AttackDamageStartsAt", if damageWindow then now + damageWindow.startTime else nil)
    character:SetAttribute("AttackDamageEndsAt", if damageWindow then now + damageWindow.endTime else nil)
    character:SetAttribute("AttackReleaseAt", if releaseEvent then now + releaseEvent.time else nil)
    character:SetAttribute("LastAttackHitZone", nil)
    character:SetAttribute("LastAttackHeadshot", false)
    character:SetAttribute("LastAttackBounced", false)

    if isBow then
        if not beginBowRelease(player, character, root, clientAttackId, serial, timing, payload) then
            clearAttackState(player, character, serial, clientAttackId, false)
            return
        end
    end
    -- Bow Release creates one projectile; only melee uses the HitStart/HitEnd volume.
    clearAttackStateLater(player, character, serial, clientAttackId, attackDuration, not isBow)
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
    if character and string.lower(tostring(character:GetAttribute("EquippedWeaponType") or "")) == "bow" then
        return -- a bow cannot submit melee hitbox pose packets
    end
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
    local session = AttackSessionStore.Get(player)
    local damageWindow = session and session.damageWindow
    if not session
        or session.character ~= character
        or session.clientAttackId ~= clientAttackId
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

    local aimOrigin, aimDirection = AttackAimGeometry.Normalize(root.Position, payload.aimOrigin, payload.aimDirection)

    local sweepState = AttackSessionStore.EnsureSweep(session)

    -- Accepted poses sweep continuously only inside HitStart -> HitEnd. There is
    -- no buffered terminal Hit checkpoint anymore; each accepted pose belongs to
    -- the active authored window and is resolved immediately.
    local serial = session.serial
    local lastElapsed = tonumber(sweepState.lastElapsed)
    if serial and (lastElapsed == nil or elapsed + 1e-4 >= lastElapsed) then
        local previousBoxCFrame = if typeof(sweepState.lastBoxCFrame) == "CFrame" then sweepState.lastBoxCFrame else nil
        local previousAimOrigin = if typeof(sweepState.lastAimOrigin) == "Vector3" then sweepState.lastAimOrigin else nil
        local previousAimDirection = if typeof(sweepState.lastAimDirection) == "Vector3" then sweepState.lastAimDirection else nil
        local _, bounced = applyAnimatedWeaponSweep(
            player,
            character,
            root,
            serial,
            clientAttackId,
            tostring(character:GetAttribute("AttackClipId") or ""),
            weapon,
            boxSize,
            previousBoxCFrame,
            payload.boxCFrame,
            lastElapsed,
            elapsed,
            previousAimOrigin,
            previousAimDirection,
            aimOrigin,
            aimDirection
        )
        if not bounced then
            AttackSessionStore.CommitSweep(session, sweepState, elapsed, payload.boxCFrame, aimOrigin, aimDirection)
        end
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

    local aimEvent = remotes:FindFirstChild("BowAimUpdate") or Instance.new("RemoteEvent")
    aimEvent.Name = "BowAimUpdate"
    aimEvent.Parent = remotes
    aimEvent.OnServerEvent:Connect(updateBowAim)

    Players.PlayerRemoving:Connect(AttackSessionStore.Forget)
    Players.PlayerRemoving:Connect(function(player)
        pendingBowReleases[player] = nil
    end)
end

return table.freeze(AttackService)
