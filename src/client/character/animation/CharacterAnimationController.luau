local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local AnimationShared = Shared:WaitForChild("animation")
local CharacterShared = Shared:WaitForChild("character")
local DeathAnimationPolicy = require(CombatShared:WaitForChild("DeathAnimationPolicy"))
local AttackTimelineConfig = require(CombatShared:WaitForChild("AttackTimelineConfig"))
local AnimationSpeedScaling = require(AnimationShared:WaitForChild("AnimationSpeedScaling"))
local AnimationFirstFrameSeam = require(AnimationShared:WaitForChild("AnimationFirstFrameSeam"))
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
local currentLoopSeam = nil
local currentLoopClipId = ""
local currentAction = nil
local currentActionSeam = nil
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

local function disconnectAll()
	for _, connection in ipairs(connections) do
		connection:Disconnect()
	end
	table.clear(connections)
end

local function clearCharacter()
	disconnectAll()
	if cache then
		cache:Destroy()
	end
	cache = nil
	character = nil
	animator = nil
	currentLoop = nil
	currentLoopSeam = nil
	currentLoopClipId = ""
	currentAction = nil
	currentActionSeam = nil
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

local function animationPlaybackPercent(channel: string): number
	if not character then
		return 100
	end
	local normalizedChannel = string.lower(tostring(channel or ""))
	if normalizedChannel == "death" or normalizedChannel == "revive" then
		return GameOptions.CharacterLifePlaybackPercent(normalizedChannel)
	end
	if attackLowerBodyActive and (normalizedChannel == "run" or normalizedChannel == "walk") then
		local runSpeed = tonumber(character:GetAttribute("RunSpeed")) or CharacterMovementConfig.DefaultRunSpeed
		local multiplier = tonumber(character:GetAttribute("AttackMovementRunSpeedMultiplier")) or 1
		local equivalentRunSpeed = CharacterMovementConfig.EquivalentRunSpeedForLocomotion(
			runSpeed,
			multiplier,
			normalizedChannel == "walk" and "Walk" or "Run"
		)
		return AnimationSpeedScaling.ResolveForModelWithStatValue(character, normalizedChannel, equivalentRunSpeed)
	end
	return AnimationSpeedScaling.ResolveForModel(character, normalizedChannel)
end

local function animationPlaybackScale(channel: string): number
	return animationPlaybackPercent(channel) / 100
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
	if currentLoopSeam then
		currentLoopSeam:Stop(fadeTime or 0)
	elseif currentLoop and currentLoop.IsPlaying then
		currentLoop:Stop(fadeTime or 0)
	end
	currentLoopSeam = nil
end

local refreshLoop

local function stopCurrentAction(fadeTime: number?)
	if currentActionComposed then
		AttackUpperBodyComposer.End()
	elseif currentActionSeam then
		currentActionSeam:Stop(fadeTime or 0)
	elseif currentAction and currentAction.IsPlaying then
		currentAction:Stop(fadeTime or 0)
	end
	currentActionSeam = nil
	currentActionOnComplete = nil
	currentActionComposed = false
	currentActionTimeline = nil
	currentActionClipId = ""
	currentActionToken += 1
	attackLowerBodyActive = false
end

local function finishAttackPresentation(boundCharacter: Model, boundTrack: AnimationTrack, token: number)
	if character ~= boundCharacter or currentAction ~= boundTrack or currentActionToken ~= token then
		return
	end
	currentActionLockedUntil = 0
	currentActionSlot = ""
	if currentActionComposed then
		AttackUpperBodyComposer.End()
	elseif currentActionSeam then
		currentActionSeam:Stop(0.04)
		currentActionSeam = nil
	elseif boundTrack.IsPlaying then
		boundTrack:Stop(0.04)
	end
	currentActionComposed = false
	currentActionTimeline = nil
	currentActionClipId = ""
	attackLowerBodyActive = false
	currentAction = nil
	boundCharacter:SetAttribute("AnimationActionEndsAt", nil)
	boundCharacter:SetAttribute("AnimationAttackUpperBodyComposed", false)
	boundCharacter:SetAttribute("AnimationAttackLowerBodySlot", nil)
	refreshLoop()
end

local function createSeam(descriptor, track: AnimationTrack, looped: boolean)
	if not cache or descriptor.duplicateFirstFrameAtEnd ~= true then
		return nil
	end
	local companion = cache:GetSeamCompanion(descriptor)
	if not companion then
		return nil
	end
	return AnimationFirstFrameSeam.new(track, companion, looped)
end

local function movementUsesForwardSeam(descriptor, slot: string): boolean
	if descriptor.duplicateFirstFrameAtEnd ~= true then
		return false
	end
	local backward = character and tostring(character:GetAttribute("AnimationMovementDirection") or "Forward") == "Backward"
	return not (backward and (slot == "walk" or slot == "run"))
end

local function applyBackwardPlayback(track: AnimationTrack, slot: string)
	if not character then
		return
	end
	local backward = tostring(character:GetAttribute("AnimationMovementDirection") or "Forward") == "Backward"
	local playbackScale = animationPlaybackScale(slot)
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
	if attackLowerBodyActive then
		character:SetAttribute("AnimationAttackLowerBodySlot", slot)
	end
	local descriptor = AnimationResolver.ResolveLocomotion(character, slot)
	if not descriptor then
		stopCurrentLoop(0.12)
		currentLoop = nil
		currentLoopClipId = ""
		character:SetAttribute("AnimationResolvedSlot", slot)
		character:SetAttribute("AnimationResolvedClip", "")
		return
	end

	local clipId = tostring(descriptor.clipId or "")
	local playbackScale = animationPlaybackScale(slot)
	local wantsSeam = movementUsesForwardSeam(descriptor, slot)
	publishPlaybackPercent(slot)

	if currentLoop and currentLoopClipId == clipId then
		if wantsSeam and currentLoopSeam then
			currentLoopSeam:AdjustSpeed(playbackScale)
			return
		elseif not wantsSeam and not currentLoopSeam then
			applyBackwardPlayback(currentLoop, slot)
			return
		end
		-- Direction/runtime seam mode changed for the same clip; restart that
		-- presentation path so a frozen companion can never leak across modes.
		stopCurrentLoop(0.08)
	end

	local nextTrack = cache:Get(descriptor)
	if not nextTrack then
		return
	end
	stopCurrentLoop(0.15)
	currentLoop = nextTrack
	currentLoopClipId = clipId
	if wantsSeam then
		currentLoopSeam = createSeam(descriptor, nextTrack, true)
	end
	if currentLoopSeam then
		currentLoopSeam:Play(0.15, playbackScale)
	else
		nextTrack.Looped = descriptor.looped == true
		nextTrack:Play(0.15, 1, playbackScale)
		applyBackwardPlayback(nextTrack, slot)
	end
	character:SetAttribute("AnimationResolvedSlot", slot)
	character:SetAttribute("AnimationResolvedClip", clipId)
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
	DeathAnimationPolicy.Start(track, animationPlaybackScale("death"))
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
	local playbackScale = animationPlaybackScale(slot)
	currentActionSeam = createSeam(descriptor, track, false)
	character:SetAttribute("AnimationActionSlot", slot)
	character:SetAttribute("AnimationActionClip", tostring(descriptor.clipId or ""))
	if currentActionSeam then
		currentActionOnComplete = onStopped
		currentActionSeam:Play(0.06, playbackScale)
		return
	end
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

local function maintainRuntimeAnimationTails(deltaTimeSim: number)
	if currentLoopSeam then
		currentLoopSeam:Step(deltaTimeSim)
	end
	if currentActionSeam then
		local completed = currentActionSeam:Step(deltaTimeSim)
		if completed and currentActionSlot ~= "attack" and currentActionSlot ~= "death" then
			local callback = currentActionOnComplete
			currentActionOnComplete = nil
			currentActionSeam:Stop(0.04)
			currentActionSeam = nil
			currentAction = nil
			currentActionSlot = ""
			currentActionLockedUntil = 0
			if callback then callback() end
		end
	end
	maintainDeathTerminalPose(deltaTimeSim)
end

local function bindCharacter(newCharacter: Model)
	clearCharacter()
	character = newCharacter
	animator = findAnimator(newCharacter)
	if not animator then
		warn("[game1][animation] Animator is missing from Visual")
		return
	end
	cache = AnimationTrackCache.new(animator)
	lastLifeState = tostring(newCharacter:GetAttribute("LifeState") or "Alive")
	local boundCache = cache
	local descriptors = AnimationResolver.ListForCharacter(newCharacter)
	task.spawn(function()
		local result = boundCache:Prewarm(descriptors, 4)
		if character ~= newCharacter or cache ~= boundCache then
			return
		end
		print(("[game1][animation] prewarm %d/%d ready in %.3fs"):format(result.ready, result.total, result.elapsed))
	end)
	local refreshAttributes = { "MovementState", "InCombat", "AnimationMovementDirection", "AnimationWeaponSet", "RunSpeed", "AttackSpeed", "AttackMovementLocomotionMode", "AttackMovementRunSpeedMultiplier" }
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

function CharacterAnimationController.PlayAction(slot: string)
	if not character or not cache or lifeTransition then
		return nil
	end

	local now = os.clock()
	if currentActionSlot == "attack" and now < currentActionLockedUntil then
		-- An attack owns its complete animation interval. Input/cooldown code may not
		-- interrupt it before the configured clip timeline reaches its end.
		return nil
	end

	local descriptor = AnimationResolver.ResolveAction(character, slot)
	if not descriptor then
		return nil
	end
	local fallbackTrack = cache:Get(descriptor)
	if not fallbackTrack then
		return nil
	end

	local clipId = tostring(descriptor.clipId or "")
	local animationSpeedPercent = animationPlaybackPercent(slot)
	local playbackSpeed = animationSpeedPercent / 100
	local timeline = nil
	local runtimeDuration = 0
	if slot == "attack" then
		timeline = AttackTimelineConfig.ResolveRuntime(clipId, animationSpeedPercent)
		if not timeline then
			warn(("[game1][animation] attack clip has no timeline: %s"):format(clipId))
			return nil
		end
		playbackSpeed = timeline.playbackSpeed
		runtimeDuration = timeline.duration
	end

	stopCurrentAction(0.06)
	currentActionToken += 1
	local actionToken = currentActionToken
	currentActionSlot = slot
	currentActionLockedUntil = if slot == "attack" then now + runtimeDuration else 0
	publishPlaybackPercent(slot)

	local track = fallbackTrack
	local composed = false
	if slot == "attack" then
		-- The original RobloxLineage attack contract keeps the legs on live combat
		-- locomotion and samples only the upper-body subtree from the attack clip.
		-- This avoids attack-authored leg/root keys fighting planted movement/facing.
		attackLowerBodyActive = true
		refreshLoop()
		local composedTrack, composeError = AttackUpperBodyComposer.Begin(character, descriptor, playbackSpeed)
		if composedTrack then
			track = composedTrack
			composed = true
		else
			warn(("[game1][animation] upper-body attack composition unavailable; using full-body fallback: %s")
				:format(tostring(composeError)))
		end
	end

	currentAction = track
	currentActionComposed = composed
	currentActionTimeline = timeline
	currentActionClipId = clipId
	if not composed then
		track.Looped = false
		currentActionSeam = createSeam(descriptor, track, false)
		if currentActionSeam then
			currentActionSeam:Play(0.06, playbackSpeed)
		else
			track:Play(0.06, 1, playbackSpeed)
		end
	else
		currentActionSeam = nil
	end

	character:SetAttribute("AnimationActionSlot", slot)
	character:SetAttribute("AnimationActionClip", clipId)
	if slot == "attack" then
		character:SetAttribute("AnimationActionEndsAt", currentActionLockedUntil)
		character:SetAttribute("AnimationAttackBounced", false)
		character:SetAttribute("AnimationAttackUpperBodyComposed", composed)
		character:SetAttribute("AnimationAttackLowerBodySlot", movementSlot())
		local boundCharacter = character
		local boundTrack = track
		local exitBlend = if composed then AttackUpperBodyComposer.GetExitBlendSeconds() else 0
		if composed and runtimeDuration > exitBlend + 0.01 then
			task.delay(runtimeDuration - exitBlend, function()
				if character == boundCharacter
					and currentAction == boundTrack
					and currentActionToken == actionToken
					and currentActionComposed
				then
					AttackUpperBodyComposer.BeginExitBlend()
				end
			end)
		end
		task.delay(runtimeDuration, function()
			finishAttackPresentation(boundCharacter, boundTrack, actionToken)
		end)
	end

	return {
		track = track,
		clipId = clipId,
		playbackSpeed = playbackSpeed,
		animationSpeedPercent = animationSpeedPercent,
		durationSeconds = runtimeDuration,
		endsAt = currentActionLockedUntil,
		timeline = timeline,
		upperBodyComposed = composed,
		lowerBodySlot = if slot == "attack" then movementSlot() else nil,
	}
end

function CharacterAnimationController.BounceCurrentAttack(clipId: string, reverseSpeedMultiplier: number?): (boolean, number)
	if not character
		or currentActionSlot ~= "attack"
		or not currentAction
		or currentActionClipId ~= tostring(clipId or "")
	then
		return false, 0
	end

	local track = currentAction :: AnimationTrack
	local timeline = currentActionTimeline
	local playbackSpeed = math.max(0.01, tonumber(timeline and timeline.playbackSpeed) or 1)
	local multiplier = math.max(0.1, tonumber(reverseSpeedMultiplier) or 2)
	local reverseSpeed = playbackSpeed * multiplier
	local sourceTime = math.max(0, tonumber(track.TimePosition) or 0)
	local rewindSeconds = sourceTime / reverseSpeed
	local exitBlend = if currentActionComposed then AttackUpperBodyComposer.GetExitBlendSeconds() else 0

	currentActionToken += 1
	local bounceToken = currentActionToken
	currentActionLockedUntil = os.clock() + rewindSeconds + exitBlend
	character:SetAttribute("AnimationActionEndsAt", currentActionLockedUntil)
	character:SetAttribute("AnimationAttackBounced", true)

	if currentActionSeam then
		currentActionSeam:Stop(0)
		currentActionSeam = nil
	end

	if currentActionComposed then
		AttackUpperBodyComposer.SetPlaybackSpeed(-reverseSpeed)
	else
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
		if character ~= boundCharacter or currentAction ~= boundTrack or currentActionToken ~= bounceToken then
			return
		end
		pcall(function()
			boundTrack.TimePosition = 0
		end)
		if currentActionComposed then
			AttackUpperBodyComposer.SetPlaybackSpeed(0)
			AttackUpperBodyComposer.BeginExitBlend()
			if exitBlend > 0 then
				task.delay(exitBlend, function()
					finishAttackPresentation(boundCharacter, boundTrack, bounceToken)
				end)
			else
				finishAttackPresentation(boundCharacter, boundTrack, bounceToken)
			end
		else
			boundTrack:AdjustSpeed(0)
			finishAttackPresentation(boundCharacter, boundTrack, bounceToken)
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
	RunService.PreAnimation:Connect(maintainRuntimeAnimationTails)
end

return CharacterAnimationController
