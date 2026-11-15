local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CharacterShared = Shared:WaitForChild("character")
local CombatShared = Shared:WaitForChild("combat")
local Config = require(CombatShared:WaitForChild("AttackConfig"))
local AttackTimelineConfig = require(CombatShared:WaitForChild("AttackTimelineConfig"))
local CharacterAttackHitEnd = require(CombatShared:WaitForChild("CharacterAttackHitEnd"))
local WeaponBounceConfig = require(CombatShared:WaitForChild("WeaponBounceConfig"))
local CharacterAnimationRegistry = require(CharacterShared:WaitForChild("CharacterAnimationRegistry"))
local AttackAimGeometry = require(CombatShared:WaitForChild("AttackAimGeometry"))
local BowAimGeometry = require(CombatShared:WaitForChild("BowAimGeometry"))
local BowProjectileConfig = require(CombatShared:WaitForChild("BowProjectileConfig"))
local BowHitscanService = require(script.Parent:WaitForChild("BowHitscanService"))
local MeleeEnvironmentContact = require(script.Parent:WaitForChild("MeleeEnvironmentContact"))
-- Sway is an optional presentation reaction; it cannot block authoritative hits.
local swayOk, swayModule = pcall(function()
    return require(script.Parent.Parent:WaitForChild("world"):WaitForChild("LandscapeSwayService"))
end)
local LandscapeSwayService = if swayOk then swayModule else nil
local AttackDamageResolver = require(script.Parent:WaitForChild("AttackDamageResolver"))
local CombatFeedbackService = require(script.Parent:WaitForChild("CombatFeedbackService"))
local AttackFeedbackTargeting = require(script.Parent:WaitForChild("AttackFeedbackTargeting"))
local AttackSessionStore = require(script.Parent:WaitForChild("AttackSessionStore"))
local HostilePursuitRegistry = require(script.Parent:WaitForChild("HostilePursuitRegistry"))
local WeaponBounceService = require(script.Parent:WaitForChild("WeaponBounceService"))


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

-- Exactly one server-clock HitEnd checkpoint. No active hit window.
-- Client-authored CFrame/Size of a weapon is never accepted or consulted.
local triggerWeaponBounce

local function applyMeleeArc(player: Player, character: Model, root: BasePart,
    serial: number, clientAttackId: number, clipId: string, elapsed: number): boolean
    local session = AttackSessionStore.Get(player)
    if not session or session.serial ~= serial or session.character ~= character
        or session.clientAttackId ~= clientAttackId or session.environmentBlocked
        or player.Character ~= character or character:GetAttribute("LifeState") ~= "Alive" then return false end
    if string.lower(tostring(character:GetAttribute("EquippedWeaponType") or "")) == "bow" then return false end
    local reach = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Config.Range, 1, Config.MaxAimDistance)
    local arcAngle = math.clamp(tonumber(character:GetAttribute("MeleeArcAngle")) or Config.MeleeDefaultArcAngle, 1, 360)
    local padding = Config.MeleeVerticalPadding

    if LandscapeSwayService then LandscapeSwayService.MeleeArc(root, reach, arcAngle) end
    -- Environment queries are meaningful only when Bounce is eligible.
    -- In combat, never spend up to five rays looking for contact to suppress.
    if character:GetAttribute("InCombat") ~= true and HostilePursuitRegistry.Count(character) == 0 then
        local contact = MeleeEnvironmentContact.Query(root, reach, arcAngle)
        if contact and triggerWeaponBounce(player, character, serial, clientAttackId, clipId, elapsed, contact) then
            return true
        end
    end

    local _, _, damaged = AttackDamageResolver.Apply({
        player=player, character=character, root=root, serial=serial,
        aimOrigin=session.lastAimOrigin,
        aimDirection=session.lastAimDirection, attackRange=reach,
        arcAngleDegrees=arcAngle, verticalPadding=padding,
    })
    if damaged > 0 then AttackSessionStore.MarkDamage(player, character, serial) end
    return false
end

local function scheduleMeleeArc(player: Player, character: Model, root: BasePart,
    serial: number, clientAttackId: number, clipId: string, hitEndEvent: any)
    local started = os.clock()
    task.delay(hitEndEvent.time, function()
        local session = AttackSessionStore.Get(player)
        if not session or session.serial ~= serial or session.clientAttackId ~= clientAttackId
            or session.character ~= character or player.Character ~= character
            or not character.Parent or session.environmentBlocked
            or character:GetAttribute("LifeState") ~= "Alive" then return end
        local currentRoot = character:FindFirstChild("RootCollider")
        if not currentRoot or not currentRoot:IsA("BasePart") then return end
        if not AttackSessionStore.MarkMeleeResolved(player, character, serial, clientAttackId) then return end
        -- Exactly one snapshot at HitEnd, even with no loaded animation track.
        local bounced = applyMeleeArc(player, character, currentRoot, serial, clientAttackId, clipId,
            math.max(0, os.clock() - started))
        if not bounced then
            local completed = AttackSessionStore.Get(player)
            if completed and completed.serial == serial and not completed.damageDealt then
                local range = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Config.Range,
                    1, Config.MaxAimDistance)
                local aimedState = AttackFeedbackTargeting.Evaluate(character, currentRoot,
                    completed.lastAimOrigin, completed.lastAimDirection, range, false)
                CombatFeedbackService.PublishAttackOutcome(character, aimedState, false)
                if Config.DebugLogs then
                    print(("[game1][attack] zero_damage player=%s serial=%d source=melee_arc HitEnd")
                        :format(player.Name, serial))
                end
            end
        end
    end)
end

local function clearAttackState(
    player: Player,
    character: Model,
    serial: number,
    clientAttackId: number
): boolean
    local active = AttackSessionStore.Get(player)
    -- Bounce can extend recovery beyond the original animation duration.
    -- An older completion timer must never shorten that server cooldown.
    if active and active.character == character and active.serial == serial
        and active.clientAttackId == clientAttackId and os.clock() + 0.002 < active.untilTime then
        task.delay(active.untilTime - os.clock(), function()
            clearAttackState(player, character, serial, clientAttackId)
        end)
        return false
    end
    local finished = AttackSessionStore.Finish(player, character, serial, clientAttackId)
    if not finished then
        return false
    end

    if character.Parent and tonumber(character:GetAttribute("AttackSerial")) == serial then
        character:SetAttribute("AttackEndsAt", nil)
        character:SetAttribute("AttackHitEndAt", nil)
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
    durationSeconds: number
)
    task.delay(durationSeconds, function()
        clearAttackState(player, character, serial, clientAttackId)
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
    character:SetAttribute("AttackHitEndAt", nil)
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

    clearAttackStateLater(player, character, serial, clientAttackId, recoverySeconds)
    return true
end

-- The client emits ONE capture ~100ms before Release. Separate reliable
-- remotes and network jitter can deliver it after the server's Release clock.
-- Never replace a missed late capture with an unrelated attack-start camera ray:
-- that produced visually identical shots with different flight directions.
local function finishBowRelease(player: Player, pending: any): boolean
    if pendingBowReleases[player] ~= pending then return false end
    pendingBowReleases[player] = nil -- consume once, including rejected shots
    local character = pending.character
    if not pending.snapshot or not character.Parent
        or player.Character ~= character
        or character:GetAttribute("LifeState") ~= "Alive"
        or character:GetAttribute("AttackSerial") ~= pending.serial
        or string.lower(tostring(character:GetAttribute("EquippedWeaponType") or "")) ~= "bow" then
        return false
    end
    if RunService:IsStudio() and Config.DebugLogs then
        print(("[game1][bow] release player=%s id=%d capture=%s delay_ms=%.0f")
            :format(player.Name, pending.clientAttackId,
                if pending.captureReceivedAt > pending.releaseAt then "late" else "on_time",
                math.max(0, (pending.captureReceivedAt - pending.releaseAt) * 1000)))
    end
    local released, damageDealt = BowHitscanService.Release(player, character, pending.snapshot)
    if released and damageDealt <= 0 then
        local root = character:FindFirstChild("RootCollider")
        if root and root:IsA("BasePart") then
            local range = math.clamp(tonumber(character:GetAttribute("AttackRadius")) or Config.Range,
                1, Config.MaxAimDistance)
            local aimedState = AttackFeedbackTargeting.Evaluate(character, root,
                pending.aimOrigin, pending.aimDirection, range, true)
            CombatFeedbackService.PublishAttackOutcome(character, aimedState, true)
        end
    end
    return released
end

local function updateBowAim(player: Player, payload: any)
    if type(payload) ~= "table" then return end
    local pending = pendingBowReleases[player]
    if not pending or pending.clientAttackId ~= math.floor(tonumber(payload.clientAttackId) or 0) then return end
    local now = os.clock()
    if pending.snapshot or now > pending.releaseAt + BowProjectileConfig.CaptureGraceSeconds then return end
    -- Accept one late packet inside a bounded grace window. Earlier packets
    -- must still come from the final portion of the authored attack timeline.
    if now < pending.releaseAt - BowProjectileConfig.CaptureWindowSeconds then return end
    if player.Character ~= pending.character
        or pending.character:GetAttribute("LifeState") ~= "Alive"
        or pending.character:GetAttribute("AttackSerial") ~= pending.serial then return end
    if not pending.releaseReached then
        local session = AttackSessionStore.Get(player)
        if not session or session.serial ~= pending.serial or session.character ~= pending.character then return end
    end
    local root = pending.character:FindFirstChild("RootCollider")
    if not root or not root:IsA("BasePart") then return end
    local origin, direction = BowAimGeometry.Validate(root, payload.aimOrigin, payload.aimDirection)
    if not origin or not direction then return end
    pending.snapshot = BowHitscanService.Capture(pending.character, origin, direction, payload.launchOrigin)
    if not pending.snapshot then return end
    pending.captureReceivedAt = now
    pending.aimOrigin = origin
    pending.aimDirection = direction
    if pending.releaseReached then
        finishBowRelease(player, pending)
    end
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
        releaseAt = os.clock() + releaseTime,
        releaseReached = false,
        snapshot = nil,
        captureReceivedAt = nil,
        aimOrigin = nil,
        aimDirection = nil,
    }
    pendingBowReleases[player] = pending
    task.delay(releaseTime, function()
        if pendingBowReleases[player] ~= pending then return end
        pending.releaseReached = true
        if pending.snapshot then
            finishBowRelease(player, pending)
            return
        end
        -- Do not turn network timing variance into an inaccurate projectile.
        -- A missing snapshot is an explicit failed shot, not a stale fallback.
        task.delay(BowProjectileConfig.CaptureGraceSeconds, function()
            if pendingBowReleases[player] ~= pending then return end
            pendingBowReleases[player] = nil
            if RunService:IsStudio() and Config.DebugLogs then
                warn(("[game1][bow] capture_timeout player=%s id=%d grace_ms=%.0f; no projectile (no stale aim)")
                    :format(player.Name, clientAttackId, BowProjectileConfig.CaptureGraceSeconds * 1000))
            end
        end)
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
    local hitEndEvent = if isBow then nil else CharacterAttackHitEnd.Resolve(timing)
    if (isBow and not releaseEvent) or (not isBow and not hitEndEvent) then
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
    AttackSessionStore.Begin(player, character, serial, clientAttackId, now + attackDuration)
    if not isBow then
        local origin, direction = AttackAimGeometry.Normalize(root.Position, payload.aimOrigin, payload.aimDirection)
        AttackSessionStore.SetAim(player, character, serial, clientAttackId, origin, direction)
    end
    character:SetAttribute("AttackSerial", serial)
    character:SetAttribute("AttackClipId", clipId)
    character:SetAttribute("AttackStartedAt", now)
    character:SetAttribute("AttackEndsAt", now + attackDuration)
    character:SetAttribute("AttackHitEndAt", if hitEndEvent then now + hitEndEvent.time else nil)
    character:SetAttribute("AttackReleaseAt", if releaseEvent then now + releaseEvent.time else nil)
    character:SetAttribute("LastAttackHitZone", nil)
    character:SetAttribute("LastAttackHeadshot", false)
    character:SetAttribute("LastAttackBounced", false)

    if isBow then
        if not beginBowRelease(player, character, root, clientAttackId, serial, timing, payload) then
            clearAttackState(player, character, serial, clientAttackId)
            return
        end
    end
    -- Bow's release path is separate; melee resolves once at server-timed HitEnd.
    if not isBow then
        scheduleMeleeArc(player, character, root, serial, clientAttackId, clipId, hitEndEvent)
    end
    clearAttackStateLater(player, character, serial, clientAttackId, attackDuration)
end

-- This event carries AIM ONLY for a headshot upgrade. Geometry and
-- damage timing are never sourced from client packets (M358).
local function updateMeleeAim(player: Player, payload: any)
    if type(payload) ~= "table" then return end
    local clientAttackId = math.floor(tonumber(payload.clientAttackId) or 0)
    local character = player.Character
    if not character or tostring(character:GetAttribute("EquippedWeaponType") or "") == "bow" then return end
    local root = character:FindFirstChild("RootCollider")
    local session = AttackSessionStore.Get(player)
    if not root or not root:IsA("BasePart") or not session
        or session.character ~= character or session.clientAttackId ~= clientAttackId
        or session.environmentBlocked or session.hitResolved
        or character:GetAttribute("LifeState") ~= "Alive" then return end
    local now = os.clock()
    if now > session.untilTime or now < session.untilTime - Config.MaxMeleeAimWindowSeconds then return end
    local origin, direction = AttackAimGeometry.Normalize(root.Position, payload.aimOrigin, payload.aimDirection)
    if origin and direction then
        AttackSessionStore.SetAim(player, character, session.serial, clientAttackId, origin, direction)
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

    local aimMeleeEvent = remotes:FindFirstChild("MeleeAimUpdate") or Instance.new("RemoteEvent")
    aimMeleeEvent.Name = "MeleeAimUpdate"
    aimMeleeEvent.Parent = remotes
    aimMeleeEvent.OnServerEvent:Connect(updateMeleeAim)

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
