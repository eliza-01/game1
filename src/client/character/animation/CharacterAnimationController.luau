local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local AnimationShared = Shared:WaitForChild("animation")
local DeathAnimationPolicy = require(CombatShared:WaitForChild("DeathAnimationPolicy"))
local AttackTimelineConfig = require(CombatShared:WaitForChild("AttackTimelineConfig"))
local AnimationSpeedScaling = require(AnimationShared:WaitForChild("AnimationSpeedScaling"))

local AnimationResolver = require(script.Parent:WaitForChild("AnimationResolver"))
local AnimationTrackCache = require(script.Parent:WaitForChild("AnimationTrackCache"))

local CharacterAnimationController = {}

local localPlayer = Players.LocalPlayer
local started = false
local character: Model? = nil
local animator: Animator? = nil
local cache = nil
local currentLoop = nil
local currentLoopClipId = ""
local currentAction = nil
local currentActionSlot = ""
local currentActionLockedUntil = 0
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
	currentLoopClipId = ""
	currentAction = nil
	currentActionSlot = ""
	currentActionLockedUntil = 0
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
	return AnimationSpeedScaling.ResolveForModel(character, channel)
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
	local state = string.lower(tostring(character:GetAttribute("MovementState") or "idle"))
	if state == "walk" then
		return "walk"
	elseif state == "run" then
		return "run"
	end
	return "idle"
end

local function applyBackwardPlayback(track: AnimationTrack, slot: string)
	if not character then
		return
	end
	local backward = tostring(character:GetAttribute("AnimationMovementDirection") or "Forward") == "Backward"
	local playbackScale = animationPlaybackScale(slot)
	if not backward or slot ~= "walk" then
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

local function refreshLoop()
	if not character or not cache or lifeTransition then
		return
	end
	local slot = movementSlot()
	local descriptor = AnimationResolver.ResolveLocomotion(character, slot)
	if not descriptor then
		if currentLoop then
			currentLoop:Stop(0.12)
		end
		currentLoop = nil
		currentLoopClipId = ""
		character:SetAttribute("AnimationResolvedSlot", slot)
		character:SetAttribute("AnimationResolvedClip", "")
		return
	end
	local clipId = tostring(descriptor.clipId or "")
	publishPlaybackPercent(slot)
	if currentLoop and currentLoopClipId == clipId then
		applyBackwardPlayback(currentLoop, slot)
		return
	end
	local nextTrack = cache:Get(descriptor)
	if not nextTrack then
		return
	end
	if currentLoop and currentLoop.IsPlaying then
		currentLoop:Stop(0.15)
	end
	currentLoop = nextTrack
	currentLoopClipId = clipId
	nextTrack:Play(0.15, 1, animationPlaybackScale(slot))
	applyBackwardPlayback(nextTrack, slot)
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

local function playDeath()
	if not character or not cache then
		return
	end
	local boundCharacter = character
	local descriptor = AnimationResolver.Resolve(boundCharacter, "base", nil, "death")
	local track = descriptor and cache:Get(descriptor) or nil

	if currentLoop and currentLoop.IsPlaying then
		currentLoop:Stop(0)
	end
	currentLoop = nil
	currentLoopClipId = ""
	if currentAction and currentAction.IsPlaying then
		currentAction:Stop(0)
	end
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
	if currentLoop and currentLoop.IsPlaying then
		currentLoop:Stop(0.08)
	end
	currentLoop = nil
	currentLoopClipId = ""
	if currentAction and currentAction.IsPlaying then
		currentAction:Stop(0.04)
	end
	currentAction = track
	currentActionSlot = slot
	currentActionLockedUntil = 0
	publishPlaybackPercent(slot)
	track:Play(0.06, 1, animationPlaybackScale(slot))
	character:SetAttribute("AnimationActionSlot", slot)
	character:SetAttribute("AnimationActionClip", tostring(descriptor.clipId or ""))
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
	elseif current == "Alive" and previous ~= "Alive" then
		deathTrack = nil
		deathTerminalPoseHeld = false
		deathTerminalReported = false
		lifeTransition = true
		if currentAction and currentAction.IsPlaying then
			currentAction:Stop(0)
		end
		currentAction = nil
		currentActionSlot = ""
		currentActionLockedUntil = 0
		character:SetAttribute("AnimationActionEndsAt", nil)
		playBaseLifeAction("revive", function()
			if not character then return end
			lifeTransition = false
			refreshLoop()
		end)
	else
		refreshLoop()
	end
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
	for _, attribute in ipairs({ "MovementState", "AnimationMovementDirection", "AnimationWeaponSet", "RunSpeed", AnimationSpeedScaling.DebugOverrideAttribute }) do
		table.insert(connections, newCharacter:GetAttributeChangedSignal(attribute):Connect(refreshLoop))
	end
	table.insert(connections, newCharacter:GetAttributeChangedSignal("LifeState"):Connect(handleLifeState))
	refreshLoop()
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
	local track = cache:Get(descriptor)
	if not track then
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

	if currentAction and currentAction.IsPlaying then
		currentAction:Stop(0.06)
	end
	currentAction = track
	currentActionSlot = slot
	currentActionLockedUntil = if slot == "attack" then now + runtimeDuration else 0
	track.Looped = false
	publishPlaybackPercent(slot)
	track:Play(0.06, 1, playbackSpeed)
	character:SetAttribute("AnimationActionSlot", slot)
	character:SetAttribute("AnimationActionClip", clipId)
	if slot == "attack" then
		character:SetAttribute("AnimationActionEndsAt", currentActionLockedUntil)
		local boundCharacter = character
		local boundTrack = track
		local unlockAt = currentActionLockedUntil
		task.delay(runtimeDuration, function()
			if character ~= boundCharacter or currentAction ~= boundTrack or currentActionLockedUntil ~= unlockAt then
				return
			end
			currentActionLockedUntil = 0
			currentActionSlot = ""
			currentAction = nil
			boundCharacter:SetAttribute("AnimationActionEndsAt", nil)
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
	}
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
	localPlayer.CharacterAdded:Connect(bindCharacter)
	localPlayer.CharacterRemoving:Connect(function(removing)
		if removing == character then
			clearCharacter()
		end
	end)
	if localPlayer.Character then
		task.spawn(bindCharacter, localPlayer.Character)
	end
	RunService.PreAnimation:Connect(maintainDeathTerminalPose)
end

return CharacterAnimationController
