local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local AnimationShared = Shared:WaitForChild("animation")
local CharacterShared = Shared:WaitForChild("character")
local DeathAnimationPolicy = require(CombatShared:WaitForChild("DeathAnimationPolicy"))
local AttackTimelineConfig = require(CombatShared:WaitForChild("AttackTimelineConfig"))
local WeaponBounceConfig = require(CombatShared:WaitForChild("WeaponBounceConfig"))
local AnimationSpeedScaling = require(AnimationShared:WaitForChild("AnimationSpeedScaling"))
local CharacterMovementConfig = require(CharacterShared:WaitForChild("CharacterMovementConfig"))
local GameOptions = require(Shared:WaitForChild("GameOptions"))

local AnimationResolver = require(script.Parent:WaitForChild("AnimationResolver"))
local AnimationTrackCache = require(script.Parent:WaitForChild("AnimationTrackCache"))
local AttackUpperBodyComposer = require(script.Parent:WaitForChild("AttackUpperBodyComposer"))

local CharacterAnimationController = {}

local localPlayer = Players.LocalPlayer
local started = false
local character: Model? = nil
local animator: Animator? = nil
local cache = nil
local currentLoop = nil
local currentLoopClipId = ""
-- Per-spawn airborne playback; movement owns the physical jump state.
local airborneSequence = -1
local jumpStartFinished = false
local jumpWarningSequence = -1
local jumpStartStoppedConnection: RBXScriptConnection? = nil
local currentAction = nil
local currentActionOnComplete = nil
local currentActionSlot = ""
local currentActionLockedUntil = 0
local currentActionComposed = false
local currentActionTimeline = nil
local currentActionClipId = ""
local currentActionToken = 0
local attackLowerBodyActive = false
local connections = {}
local lifeTransition = false
local lastLifeState = "Alive"
local deathTrack: AnimationTrack? = nil
local deathTerminalPoseHeld = false
local deathTerminalReported = false

local function disconnectJumpStart()
	if jumpStartStoppedConnection then
		jumpStartStoppedConnection:Disconnect()
		jumpStartStoppedConnection = nil
	end
end

local function disconnectAll()
	for _, connection in ipairs(connections) do
		connection:Disconnect()
	end
	table.clear(connections)
end

local function clearCharacter()
	disconnectJumpStart()
	airborneSequence = -1
	jumpStartFinished = false
	jumpWarningSequence = -1
	disconnectAll()
	if cache then
		cache:Destroy()
	end
	cache = nil
	character = nil
	animator = nil
	currentLoop = nil
	currentLoopClipId = ""
	currentAction = nil
	currentActionOnComplete = nil
	currentActionSlot = ""
	currentActionLockedUntil = 0
	currentActionComposed = false
	currentActionTimeline = nil
	currentActionClipId = ""
	currentActionToken += 1
	attackLowerBodyActive = false
	AttackUpperBodyComposer.End()
	lifeTransition = false
	lastLifeState = "Alive"
	deathTrack = nil
	deathTerminalPoseHeld = false
	deathTerminalReported = false
end

local function findAnimator(model: Model): Animator?
	local visual = model:FindFirstChild("Visual")
	if not visual then
		return nil
	end
	local host = visual:FindFirstChildWhichIsA("AnimationController", true)
	if not host then
		return nil
	end
	local found = host:FindFirstChildOfClass("Animator")
	return if found and found:IsA("Animator") then found else nil
end

local function animationPlaybackPercent(channel: string, animationId: any?): number
	if not character then
		return 100
	end
	local normalizedChannel = string.lower(tostring(channel or ""))
	if normalizedChannel == "death" or normalizedChannel == "revive" then
		local _, custom = AnimationSpeedScaling.RuleForAnimation(character, normalizedChannel, animationId)
		if not custom then return GameOptions.CharacterLifePlaybackPercent(normalizedChannel) end
	end
	if attackLowerBodyActive and (normalizedChannel == "run" or normalizedChannel == "walk") then
		local runSpeed = tonumber(character:GetAttribute("RunSpeed")) or CharacterMovementConfig.DefaultRunSpeed
		local multiplier = tonumber(character:GetAttribute("AttackMovementRunSpeedMultiplier")) or 1
		local equivalentRunSpeed = CharacterMovementConfig.EquivalentRunSpeedForLocomotion(
			runSpeed,
			multiplier,
			normalizedChannel == "walk" and "Walk" or "Run"
		)
		return AnimationSpeedScaling.ResolveForAnimation(character, normalizedChannel, animationId, equivalentRunSpeed)
	end
	local percent = AnimationSpeedScaling.ResolveForAnimation(character, normalizedChannel, animationId)
	if not attackLowerBodyActive and normalizedChannel == "run" then
		percent *= CharacterMovementConfig.TestTrackRunMultiplier(character, "Run")
	end
	return percent
end

local function animationPlaybackScale(channel: string, animationId: any?): number
	return animationPlaybackPercent(channel, animationId) / 100
end

local function publishPlaybackPercent(channel: string)
	if character then
		character:SetAttribute("AnimationPlaybackSpeedPercent", animationPlaybackPercent(channel))
	end
end

local function movementSlot(): string
	if not character then
		return "idle"
	end
	if attackLowerBodyActive then
		-- RobloxLineage composition: upper body comes from the attack source rig,
		-- while the visible lower body remains live locomotion. Stopping during the
		-- attack returns the legs to combat_idle without interrupting the upper hit.
		local state = string.lower(tostring(character:GetAttribute("MovementState") or "idle"))
		if state == "idle" then
			return "combat_idle"
		end
		-- A walk modifier/backpedal still drives the feet at Walk speed even
		-- when the equipped melee weapon normally permits Run during a swing.
		if state == "walk" then return "walk" end
		local configuredMode = string.lower(tostring(character:GetAttribute("AttackMovementLocomotionMode") or "run"))
		return if configuredMode == "walk" then "walk" else "run"
	end
	local state = string.lower(tostring(character:GetAttribute("MovementState") or "idle"))
	if state == "idle" and character:GetAttribute("InCombat") == true then
		return "combat_idle"
	end
	if state == "walk" then
		return "walk"
	elseif state == "run" then
		return "run"
	end
	return "idle"
end

local function stopCurrentLoop(fadeTime: number?)
	disconnectJumpStart()
	if currentLoop and currentLoop.IsPlaying then
		currentLoop:Stop(fadeTime or 0)
	end
end

local refreshLoop

local function stopCurrentAction(fadeTime: number?)
	if character and currentActionSlot == "attack" then
		character:SetAttribute("AnimationAttackUpperBodyComposed", false)
		character:SetAttribute("AnimationAttackLowerBodySlot", nil)
		character:SetAttribute("AnimationAttackBridgeBone", nil)
		character:SetAttribute("AnimationActionEndsAt", nil)
	end
	if currentActionComposed then
		AttackUpperBodyComposer.End()
	elseif currentAction and currentAction.IsPlaying then
		currentAction:Stop(fadeTime or 0)
	end
	currentActionOnComplete = nil
	currentActionComposed = false
	currentActionTimeline = nil
	currentActionClipId = ""
	currentActionToken += 1
	attackLowerBodyActive = false
end

local function finishAttackPresentation(boundCharacter: Model, token: number)
	if character ~= boundCharacter or currentActionToken ~= token or currentActionSlot ~= "attack" then
		return
	end
	currentActionLockedUntil = 0
	currentActionSlot = ""
	if currentActionComposed then
		AttackUpperBodyComposer.End()
	elseif currentAction and currentAction.IsPlaying then
		currentAction:Stop(0.04)
	end
	currentActionComposed = false
	currentActionTimeline = nil
	currentActionClipId = ""
	attackLowerBodyActive = false
	currentAction = nil
	boundCharacter:SetAttribute("AnimationActionEndsAt", nil)
	boundCharacter:SetAttribute("AnimationAttackUpperBodyComposed", false)
	boundCharacter:SetAttribute("AnimationAttackLowerBodySlot", nil)
	boundCharacter:SetAttribute("AnimationAttackBridgeBone", nil)
	refreshLoop()
end

local function applyBackwardPlayback(track: AnimationTrack, slot: string)
	if not character then
		return
	end
	local backward = tostring(character:GetAttribute("AnimationMovementDirection") or "Forward") == "Backward"
	local playbackScale = animationPlaybackScale(slot, track.Animation and track.Animation.AnimationId)
	if not backward or (slot ~= "walk" and slot ~= "run") then
		track:AdjustSpeed(playbackScale)
		return
	end
	task.spawn(function()
		local deadline = os.clock() + 1
		while track.IsPlaying and track.Length <= 0 and os.clock() < deadline do
			RunService.Heartbeat:Wait()
		end
		if track.IsPlaying and track.Length > 0 then
			track.TimePosition = math.max(0, track.Length - 0.001)
			track:AdjustSpeed(-playbackScale)
		end
	end)
end

refreshLoop = function()
	if not character or not cache or lifeTransition then
		return
	end
	local slot = movementSlot()
	local inJump = character:GetAttribute("AnimationAirborne") == true
	local sequence = tonumber(character:GetAttribute("AnimationJumpSequence")) or 0
	if inJump then
		if airborneSequence ~= sequence then
			-- A new accepted impulse restarts jump_start, even when the same
			-- AnimationTrack is cached from an earlier jump.
			airborneSequence = sequence
			jumpStartFinished = false
			stopCurrentLoop(0.04)
			currentLoop = nil
			currentLoopClipId = ""
		end
		slot = if jumpStartFinished then "jump_loop" else "jump_start"
	else
		if airborneSequence ~= -1 then
			disconnectJumpStart()
			airborneSequence = -1
			jumpStartFinished = false
		end
	end
	local descriptor = AnimationResolver.ResolveLocomotion(character, slot)
	if inJump and not descriptor and slot == "jump_start" then
		-- A published loop can still play if jump_start is not authored yet.
		if jumpWarningSequence ~= sequence then
			warn("[game1][animation][jump] jump_start missing from published character profile")
			jumpWarningSequence = sequence
		end
		jumpStartFinished = true
		slot = "jump_loop"
		descriptor = AnimationResolver.ResolveLocomotion(character, slot)
	end
	if inJump and not descriptor then
		if jumpWarningSequence ~= sequence then
			warn("[game1][animation][jump] jump_loop missing from published character profile")
			jumpWarningSequence = sequence
		end
		-- Preserve pre-existing locomotion as a compatibility fallback.
		slot = movementSlot()
		descriptor = AnimationResolver.ResolveLocomotion(character, slot)
	end
	if attackLowerBodyActive then
		character:SetAttribute("AnimationAttackLowerBodySlot", slot)
	end
	if not descriptor then
		stopCurrentLoop(0.12)
		currentLoop = nil
		currentLoopClipId = ""
		character:SetAttribute("AnimationResolvedSlot", slot)
		character:SetAttribute("AnimationResolvedClip", "")
		return
	end

	local clipId = tostring(descriptor.clipId or "")
	local playbackScale = animationPlaybackScale(slot, descriptor.animationId)
	if not attackLowerBodyActive then
		publishPlaybackPercent(slot)
	end
	if currentLoop and currentLoopClipId == clipId then
		applyBackwardPlayback(currentLoop, slot)
		return
	end

	local nextTrack = cache:Get(descriptor)
	if not nextTrack then
		if inJump and slot == "jump_start" then
			jumpStartFinished = true
			refreshLoop()
		end
		return
	end
	local isJumpSlot = slot == "jump_start" or slot == "jump_loop"
	stopCurrentLoop(if isJumpSlot then 0.05 else 0.15)
	currentLoop = nextTrack
	currentLoopClipId = clipId
	nextTrack.Looped = descriptor.looped == true
	if isJumpSlot then
		nextTrack:Play(0.05, 1, playbackScale)
	else
		-- Preserve the existing locomotion blend for walk/run/idle.
		nextTrack:Play(0.15, 1, playbackScale)
	end
	applyBackwardPlayback(nextTrack, slot)
	character:SetAttribute("AnimationResolvedSlot", slot)
	character:SetAttribute("AnimationResolvedClip", clipId)

	if inJump and slot == "jump_start" then
		local boundCharacter = character
		local boundSequence = sequence
		local boundTrack = nextTrack
		jumpStartStoppedConnection = boundTrack.Stopped:Connect(function()
			if character ~= boundCharacter or airborneSequence ~= boundSequence
				or boundCharacter:GetAttribute("AnimationAirborne") ~= true
				or currentLoop ~= boundTrack then
				return
			end
			disconnectJumpStart()
			jumpStartFinished = true
			refreshLoop()
		end)
	end
end
local function notifyDeathTerminalReached(boundCharacter: Model)
	if deathTerminalReported or character ~= boundCharacter or not boundCharacter.Parent then
		return
	end
	deathTerminalReported = true
	local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes")
	local event = remotes and remotes:FindFirstChild("DeathTerminalReached")
	if event and event:IsA("RemoteEvent") then
		event:FireServer()
	end
end

local function notifyReviveAnimationFinished(boundCharacter: Model)
	if character ~= boundCharacter or tostring(boundCharacter:GetAttribute("LifeState") or "") ~= "Reviving" then
		return
	end
	local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes")
	local remote = remotes and remotes:FindFirstChild("ReviveAnimationFinished")
	if remote and remote:IsA("RemoteEvent") then
		remote:FireServer()
	end
end

local function playDeath()
	if not character or not cache then
		return
	end
	local boundCharacter = character
	local descriptor = AnimationResolver.Resolve(boundCharacter, "base", nil, "death")
	local track = descriptor and cache:Get(descriptor) or nil

	stopCurrentLoop(0)
	currentLoop = nil
	currentLoopClipId = ""
	stopCurrentAction(0)
	currentAction = track
	currentActionSlot = "death"
	currentActionLockedUntil = 0
	boundCharacter:SetAttribute("AnimationActionEndsAt", nil)
	deathTrack = track
	deathTerminalPoseHeld = false
	deathTerminalReported = false
	boundCharacter:SetAttribute("AnimationActionSlot", "death")
	boundCharacter:SetAttribute("AnimationActionClip", descriptor and tostring(descriptor.clipId or "") or "")
	boundCharacter:SetAttribute("DeathAnimationStartedAt", os.clock())
	boundCharacter:SetAttribute("DeathTerminalPoseHeld", false)

	if not track then
		warn("[game1][animation] required death animation track is missing; character remains Dying")
		return
	end

	publishPlaybackPercent("death")
	DeathAnimationPolicy.Start(track, animationPlaybackScale("death", track.Animation and track.Animation.AnimationId))
end

local function maintainDeathTerminalPose(deltaTimeSim: number)
	local boundCharacter = character
	local track = deathTrack
	if not boundCharacter
		or not track
		or deathTerminalPoseHeld
		or tostring(boundCharacter:GetAttribute("LifeState") or "Alive") ~= "Dying"
	then
		return
	end

	local reached, terminalTime = DeathAnimationPolicy.LatchVisibleTerminalPose(track, deltaTimeSim)
	if not reached then
		return
	end

	deathTerminalPoseHeld = true
	boundCharacter:SetAttribute("DeathAnimationLength", track.Length)
	boundCharacter:SetAttribute("DeathAnimationTerminalTime", terminalTime)
	boundCharacter:SetAttribute("AnimationResolvedSlot", "death_idle")
	boundCharacter:SetAttribute("DeathTerminalPoseHeld", true)
	boundCharacter:SetAttribute("DeathTerminalPoseHeldAt", os.clock())
	notifyDeathTerminalReached(boundCharacter)
end

local function playBaseLifeAction(slot: string, onStopped)
	if not character or not cache then
		if onStopped then onStopped() end
		return
	end
	local descriptor = AnimationResolver.Resolve(character, "base", nil, slot)
	if not descriptor then
		if onStopped then onStopped() end
		return
	end
	local track = cache:Get(descriptor)
	if not track then
		if onStopped then onStopped() end
		return
	end
	stopCurrentLoop(0.08)
	currentLoop = nil
	currentLoopClipId = ""
	stopCurrentAction(0.04)
	currentAction = track
	currentActionSlot = slot
	currentActionLockedUntil = 0
	publishPlaybackPercent(slot)
	local playbackScale = animationPlaybackScale(slot, descriptor.animationId)
	character:SetAttribute("AnimationActionSlot", slot)
	character:SetAttribute("AnimationActionClip", tostring(descriptor.clipId or ""))
	track.Looped = false
	track:Play(0.06, 1, playbackScale)
	track.Stopped:Once(function()
		if currentAction == track then
			currentAction = nil
			currentActionSlot = ""
			currentActionLockedUntil = 0
		end
		if onStopped then onStopped() end
	end)
end

local function handleLifeState()
	if not character then
		return
	end
	local current = tostring(character:GetAttribute("LifeState") or "Alive")
	local previous = lastLifeState
	lastLifeState = current
	if current == "Dying" and previous ~= "Dying" then
		lifeTransition = true
		playDeath()
	elseif current == "DeathIdle" then
		-- Keep the frozen terminal frame of Death. There is deliberately no
		-- separate death_wait animation in game1.
		lifeTransition = true
	elseif current == "Reviving" and previous ~= "Reviving" then
		deathTrack = nil
		deathTerminalPoseHeld = false
		deathTerminalReported = false
		lifeTransition = true
		stopCurrentAction(0)
		currentAction = nil
		currentActionSlot = ""
		currentActionLockedUntil = 0
		character:SetAttribute("AnimationActionEndsAt", nil)
		local reviveCharacter = character
		playBaseLifeAction("revive", function()
			if reviveCharacter then
				notifyReviveAnimationFinished(reviveCharacter)
			end
		end)
	elseif current == "Alive" and previous == "Reviving" then
		lifeTransition = false
		refreshLoop()
	elseif current == "Alive" and previous ~= "Alive" then
		-- Same-character resurrection remains supported for dev/test lifecycles.
		lifeTransition = true
		playBaseLifeAction("revive", function()
			if not character then return end
			lifeTransition = false
			refreshLoop()
		end)
	else
		refreshLoop()
	end
end

local function maintainDeathPose(deltaTimeSim: number)
	maintainDeathTerminalPose(deltaTimeSim)
end

local function bindCharacter(newCharacter: Model)
	clearCharacter()
	character = newCharacter
	animator = findAnimator(newCharacter)
    -- A missing Animator disables only presentation. Combat metadata remains
    -- available so local input can still initiate server-authoritative actions.
    if animator then
        cache = AnimationTrackCache.new(animator)
        local boundCache = cache
        local descriptors = AnimationResolver.ListForCharacter(newCharacter)
        task.spawn(function()
            local result = boundCache:Prewarm(descriptors, 4)
            if character ~= newCharacter or cache ~= boundCache then return end
            print(("[game1][animation] prewarm %d/%d ready in %.3fs")
                :format(result.ready, result.total, result.elapsed))
        end)
    else
        warn("[game1][animation] Animator missing; visual unavailable, gameplay continues")
    end
    lastLifeState = tostring(newCharacter:GetAttribute("LifeState") or "Alive")
	local refreshAttributes = { "MovementState", "InCombat", "AnimationMovementDirection", "AnimationWeaponSet", "RunSpeed", "AttackSpeed", "AttackMovementLocomotionMode", "AttackMovementRunSpeedMultiplier", "AnimationAirborne", "AnimationJumpSequence", "GameplayTestOnTrack" }
	for _, channel in ipairs({ "run", "walk" }) do
		table.insert(refreshAttributes, AnimationSpeedScaling.DebugUnitsPerPercentAttribute(channel))
	end
	for _, attribute in ipairs(refreshAttributes) do
		table.insert(connections, newCharacter:GetAttributeChangedSignal(attribute):Connect(refreshLoop))
	end
	table.insert(connections, newCharacter:GetAttributeChangedSignal("LifeState"):Connect(handleLifeState))
	if lastLifeState == "Reviving" then
		-- A return-to-town character is born directly in Reviving, so there is no
		-- attribute edge for the client to observe. Synthesize the transition once.
		lastLifeState = "Alive"
		handleLifeState()
	else
		refreshLoop()
	end
	print("[game1][animation] character animation profile bound")
end

-- This function ACCEPTS an attack immediately from authored metadata.  Loading
-- the animation can take many frames or fail; it has no veto over gameplay.
function CharacterAnimationController.PlayAction(slot: string)
    if not character or lifeTransition then return nil end
    local now = os.clock()
    if currentActionSlot == "attack" and now < currentActionLockedUntil then return nil end
    local descriptor = AnimationResolver.ResolveAction(character, slot)
    if not descriptor then return nil end
    local clipId = tostring(descriptor.clipId or "")

    if slot ~= "attack" then
        if not cache then return nil end
        local track = cache:Get(descriptor)
        if not track then return nil end
        stopCurrentAction(0.06)
        local speed = animationPlaybackScale(slot, descriptor.animationId)
        track.Looped = false
        track:Play(0.06, 1, speed)
        currentAction = track
        currentActionSlot = slot
        currentActionLockedUntil = 0
        currentActionClipId = clipId
        character:SetAttribute("AnimationActionSlot", slot)
        character:SetAttribute("AnimationActionClip", clipId)
        publishPlaybackPercent(slot)
        return { track = track, clipId = clipId, playbackSpeed = speed }
    end

    local timeline = AttackTimelineConfig.ResolveCharacterRuntime(clipId, character:GetAttribute("AttackSpeed"))
    if not timeline then
        warn(("[game1][animation] attack clip has no timeline: %s"):format(clipId))
        return nil
    end
    local actionStartedAt = os.clock()
    local runtimeDuration = timeline.duration
    stopCurrentAction(0.06)
    currentActionToken += 1
    local token = currentActionToken
    local boundCharacter = character
    local boundCache = cache
    local playbackSpeed = timeline.playbackSpeed

    currentAction = nil  -- the track is purely optional presentation
    currentActionComposed = false
    currentActionSlot = "attack"
    currentActionClipId = clipId
    currentActionTimeline = timeline
    currentActionLockedUntil = actionStartedAt + runtimeDuration
    attackLowerBodyActive = true
    boundCharacter:SetAttribute("AnimationActionSlot", "attack")
    boundCharacter:SetAttribute("AnimationActionClip", clipId)
    boundCharacter:SetAttribute("AnimationActionEndsAt", currentActionLockedUntil)
    boundCharacter:SetAttribute("AnimationAttackBounced", false)
    boundCharacter:SetAttribute("AnimationAttackUpperBodyComposed", false)
    boundCharacter:SetAttribute("AnimationAttackLowerBodySlot", movementSlot())
    boundCharacter:SetAttribute("AnimationPlaybackSpeedPercent", timeline.animationSpeedPercent)
    boundCharacter:SetAttribute("AnimationAttackCompositionError", nil)
    refreshLoop()

    -- The presentation pipeline is asynchronous; delays below remain based on
    -- actionStartedAt, NOT on when LoadAnimation/upper-body composition finishes.
    task.spawn(function()
        local track, reason, loadedSpeed = AttackUpperBodyComposer.Begin(
            boundCharacter, descriptor, playbackSpeed, function()
                return character == boundCharacter and cache == boundCache
                    and currentActionToken == token and currentActionSlot == "attack"
                    and not lifeTransition and os.clock() < actionStartedAt + runtimeDuration
            end, timeline.playbackDuration
        )
        if currentActionToken ~= token or character ~= boundCharacter then
            -- Begin's validity guard owns stale resource cleanup.
            return
        end
        if not track then
            boundCharacter:SetAttribute("AnimationAttackCompositionError", tostring(reason))
            warn(("[game1][animation] attack %s visual unavailable; gameplay continues: %s")
                :format(clipId, tostring(reason)))
            return
        end
        currentAction = track
        currentActionComposed = true
        -- Visual speed is corrected for the actual loaded animation length,
        -- while the timeline and server HitEnd are NEVER recalculated.
        timeline.playbackSpeed = loadedSpeed or playbackSpeed
        timeline.animationSpeedPercent = timeline.playbackSpeed * 100
        boundCharacter:SetAttribute("AnimationPlaybackSpeedPercent", timeline.animationSpeedPercent)
        boundCharacter:SetAttribute("AnimationAttackUpperBodyComposed", true)
        boundCharacter:SetAttribute("AnimationAttackBridgeBone", AttackUpperBodyComposer.GetBridgeName())
        local elapsed = math.max(0, os.clock() - actionStartedAt)
        if elapsed > 0 then
            pcall(function()
                track.TimePosition = math.min(track.Length - 1 / 120, elapsed * timeline.playbackSpeed)
            end)
        end
    end)

    local exitBlend = AttackUpperBodyComposer.GetExitBlendSeconds()
    if runtimeDuration > exitBlend + 0.01 then
        task.delay(runtimeDuration - exitBlend, function()
            if character == boundCharacter and currentActionToken == token
                and currentActionComposed then
                AttackUpperBodyComposer.BeginExitBlend()
            end
        end)
    end
    task.delay(runtimeDuration, function()
        finishAttackPresentation(boundCharacter, token)
    end)

    return {
        track = nil, -- may load later; never a precondition for an attack
        clipId = clipId,
        playbackSpeed = playbackSpeed,
        animationSpeedPercent = timeline.animationSpeedPercent,
        durationSeconds = runtimeDuration,
        endsAt = currentActionLockedUntil,
        timeline = timeline,
        upperBodyComposed = false,
        lowerBodySlot = movementSlot(),
    }
end

function CharacterAnimationController.BounceCurrentAttack(clipId: string, reverseSpeedMultiplier: number?): (boolean, number)
	if not character
		or currentActionSlot ~= "attack"
		or currentActionClipId ~= tostring(clipId or "")
	then
		return false, 0
	end

	local track = currentAction :: AnimationTrack?
	local timeline = currentActionTimeline
	local playbackSpeed = math.max(0.01, tonumber(timeline and timeline.playbackSpeed) or 1)
	local multiplier = math.max(0.1, tonumber(reverseSpeedMultiplier) or 2)
	local reverseSpeed = playbackSpeed * multiplier
	local sourceTime = if track then math.max(0, tonumber(track.TimePosition) or 0) else 0
	local rewindSeconds = if track then sourceTime / reverseSpeed
		else math.max(0.05, WeaponBounceConfig.MinimumRecoverySeconds)
	local exitBlend = if currentActionComposed then AttackUpperBodyComposer.GetExitBlendSeconds() else 0

	currentActionToken += 1
	local bounceToken = currentActionToken
	currentActionLockedUntil = os.clock() + rewindSeconds + exitBlend
	character:SetAttribute("AnimationActionEndsAt", currentActionLockedUntil)
	character:SetAttribute("AnimationAttackBounced", true)


	if currentActionComposed then
		AttackUpperBodyComposer.SetPlaybackSpeed(-reverseSpeed)
	elseif track then
		if not track.IsPlaying then
			track:Play(0, 1, 0)
			pcall(function()
				track.TimePosition = sourceTime
			end)
		end
		track:AdjustSpeed(-reverseSpeed)
	end

	local boundCharacter = character
	local boundTrack = track
	task.delay(rewindSeconds, function()
		if character ~= boundCharacter or currentActionToken ~= bounceToken then
			return
		end
		if boundTrack then
			pcall(function() boundTrack.TimePosition = 0 end)
		end
		if currentActionComposed then
			AttackUpperBodyComposer.SetPlaybackSpeed(0)
			AttackUpperBodyComposer.BeginExitBlend()
			if exitBlend > 0 then
				task.delay(exitBlend, function()
					finishAttackPresentation(boundCharacter, bounceToken)
				end)
			else
				finishAttackPresentation(boundCharacter, bounceToken)
			end
		else
			if boundTrack then boundTrack:AdjustSpeed(0) end
			finishAttackPresentation(boundCharacter, bounceToken)
		end
	end)

	return true, rewindSeconds + exitBlend
end

function CharacterAnimationController.SetWeaponSet(weaponSet: string?)
	if character then
		character:SetAttribute("AnimationWeaponSet", string.lower(tostring(weaponSet or "")))
	end
end

function CharacterAnimationController.Refresh()
	refreshLoop()
end

function CharacterAnimationController.Start()
	if started then
		return
	end
	started = true
	AttackUpperBodyComposer.Start()
	localPlayer.CharacterAdded:Connect(bindCharacter)
	localPlayer.CharacterRemoving:Connect(function(removing)
		if removing == character then
			clearCharacter()
		end
	end)
	if localPlayer.Character then
		task.spawn(bindCharacter, localPlayer.Character)
	end
	RunService.PreAnimation:Connect(maintainDeathPose)
end

return CharacterAnimationController
