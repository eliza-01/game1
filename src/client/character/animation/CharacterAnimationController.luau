local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local AnimationShared = Shared:WaitForChild("animation")
local CharacterShared = Shared:WaitForChild("character")
local DeathAnimationPolicy = require(CombatShared:WaitForChild("DeathAnimationPolicy"))
local AttackTimelineConfig = require(CombatShared:WaitForChild("AttackTimelineConfig"))
local GameplayFallback = require(CombatShared:WaitForChild("GameplayAttackFallback"))
local HitPlan = require(CombatShared:WaitForChild("MeleeHitPlan"))
local TestPolicy = require(Shared:WaitForChild("dev"):WaitForChild("GameplayTestAnimationPolicy"))
local WeaponBounceConfig = require(CombatShared:WaitForChild("WeaponBounceConfig"))
local AnimationSpeedScaling = require(AnimationShared:WaitForChild("AnimationSpeedScaling"))
local CharacterMovementConfig = require(CharacterShared:WaitForChild("CharacterMovementConfig"))
local GameOptions = require(Shared:WaitForChild("GameOptions"))

local AnimationResolver = require(script.Parent:WaitForChild("AnimationResolver"))
local AnimationTrackCache = require(script.Parent:WaitForChild("AnimationTrackCache"))
local SocialAnimationPlayback = require(script.Parent:WaitForChild("SocialAnimationPlayback"))
local AttackUpperBodyComposer = require(script.Parent:WaitForChild("AttackUpperBodyComposer"))

local CharacterAnimationController = {}

local localPlayer = Players.LocalPlayer
local started = false
local character: Model? = nil
local animator: Animator? = nil
local cache = nil
local warmResult = nil
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
local reviveTrack: AnimationTrack? = nil
local reviveTerminalPoseHeld = false
local lifeRequest = nil
local nextAnimatorProbe = 0
local nextLoopProbe = 0
local loopPending = false
local revealAfterEvaluation = false
local awaitingRevivePose = false
local reviveReportPending = false
local LIFE_LOAD_SECONDS = 8
local RETRY_SECONDS = 0.25

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
    warmResult = nil
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
	reviveTrack = nil
	reviveTerminalPoseHeld = false
	lifeRequest = nil
	nextAnimatorProbe = 0
	nextLoopProbe = 0
	loopPending = false
	revealAfterEvaluation = false
	awaitingRevivePose = false
	reviveReportPending = false
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
	if normalizedChannel == "run" and not attackLowerBodyActive and character:GetAttribute("GameplayTestHubRunMultiplier") == 3 then
		percent *= 3
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

local function stopCurrentAction(fadeTime: number?, retainLifePose: boolean?)
	local retaining = retainLifePose == true and currentAction ~= nil
		and (currentAction == reviveTrack or currentAction == deathTrack)
	if not retaining then
		if currentAction == reviveTrack then reviveTrack = nil end
		if currentAction == deathTrack then deathTrack = nil end
	end
	if character and currentActionSlot == "attack" then
		character:SetAttribute("AnimationAttackUpperBodyComposed", false)
		character:SetAttribute("AnimationAttackLowerBodySlot", nil)
		character:SetAttribute("AnimationAttackBridgeBone", nil)
		character:SetAttribute("AnimationActionEndsAt", nil)
	end
	if currentActionComposed then
		AttackUpperBodyComposer.End()
	elseif not retaining and currentAction and currentAction.IsPlaying then
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
	if track.IsPlaying and track.Length > 0 then
		if track.Speed >= 0 then track.TimePosition = math.max(0, track.Length - 0.001) end
		track:AdjustSpeed(-playbackScale)
	end
end

local function releaseLifeHold()
	if not deathTrack and not reviveTrack and currentActionSlot ~= "death" and currentActionSlot ~= "revive" then return end
	if currentActionSlot == "death" or currentActionSlot == "revive" then
		stopCurrentAction(0.10)
		currentAction = nil
		currentActionSlot = ""
		character:SetAttribute("AnimationActionSlot", nil)
		character:SetAttribute("AnimationActionClip", nil)
	end
	-- An accepted attack may already own the action slot while its locomotion
	-- is still loading. Retire only the detached life hold, never the attack.
	if deathTrack and deathTrack.IsPlaying then deathTrack:Stop(0.10) end
	if reviveTrack and reviveTrack.IsPlaying then reviveTrack:Stop(0.10) end
	deathTrack = nil
	reviveTrack = nil
	deathTerminalPoseHeld = false
	reviveTerminalPoseHeld = false
	print("[game1][animation-life] successor ready; life pose released")
end

refreshLoop = function()
	if not character or lifeTransition then return end
	if not cache then loopPending = true; return end
	loopPending = false
	-- The server attribute owns the stun lifetime. Interrupt any composed attack
	-- and reuse the published social clip in the existing action/cache owner.
	if character:GetAttribute("SkillStunned") == true then
		if currentActionSlot ~= "stun" then
			if airborneSequence ~= -1 then jumpStartFinished = true end
			local descriptor = SocialAnimationPlayback.Resolve(character, "unaware")
			local track = descriptor and cache:Get(descriptor) or nil
			if not cache:IsLoaded(track) then
				if currentActionSlot == "attack" then stopCurrentAction(0.06); currentAction = nil; currentActionSlot = "" end
				loopPending = true
				return
			end
			-- Keep the existing locomotion under the full-body stun action.
			local replacesLife = deathTrack ~= nil or reviveTrack ~= nil
			if replacesLife then
				track.Looped = true
				track:Play(0, 1, animationPlaybackScale("social", descriptor.animationId))
			end
			if currentActionSlot == "death" or currentActionSlot == "revive" then
				releaseLifeHold()
			else
				stopCurrentAction(0.06)
				if replacesLife then releaseLifeHold() end
			end
			currentAction = track
			currentActionSlot = "stun"
			currentActionLockedUntil = 0
			character:SetAttribute("AnimationActionSlot", "stun")
			character:SetAttribute("AnimationActionClip", descriptor.clipId or "")
			character:SetAttribute("AnimationResolvedSlot", "stun")
			character:SetAttribute("AnimationResolvedClip", descriptor.clipId or "")
			track.Looped = true
			if not replacesLife then track:Play(0.06, 1, animationPlaybackScale("social", descriptor.animationId)) end
		end
		return
	elseif currentActionSlot == "stun" then
		stopCurrentAction(0.1)
		currentAction = nil
		currentActionSlot = ""
		character:SetAttribute("AnimationActionSlot", nil)
		character:SetAttribute("AnimationActionClip", nil)
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
			disconnectJumpStart()
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
		-- Missing locomotion must not remove the last visible pose.
		loopPending = true
		character:SetAttribute("AnimationResolvedSlot", slot)
		character:SetAttribute("AnimationResolvedClip", "")
		return
	end

	local clipId = tostring(descriptor.clipId or "")
	local playbackScale = animationPlaybackScale(slot, descriptor.animationId)
	if not attackLowerBodyActive then
		publishPlaybackPercent(slot)
	end
	if currentLoop and currentLoopClipId == clipId and currentLoop.IsPlaying then
		releaseLifeHold()
		applyBackwardPlayback(currentLoop, slot)
		return
	end

	local nextTrack = cache:Get(descriptor)
	if not cache:IsLoaded(nextTrack) then
		loopPending = true
		if currentLoop and currentLoop.IsPlaying then return end
		local idle = AnimationResolver.Resolve(character, "base", nil, "idle")
		local idleTrack = idle and cache:Get(idle) or nil
		if not cache:IsLoaded(idleTrack) then return end
		descriptor = idle
		nextTrack = idleTrack
		slot = "idle"
		clipId = tostring(idle.clipId or "")
		playbackScale = animationPlaybackScale(slot, idle.animationId)
	end
	local isJumpSlot = slot == "jump_start" or slot == "jump_loop"
	local previousLoop = currentLoop
	disconnectJumpStart()
	currentLoop = nextTrack
	currentLoopClipId = clipId
	nextTrack.Looped = descriptor.looped == true
	if reviveTrack or deathTrack then
		-- Full replacement weight before fading an Action4 hold: two unequal
		-- fade lengths must not expose the rig's bind pose between tracks.
		nextTrack:Play(0, 1, playbackScale)
	elseif isJumpSlot then
		nextTrack:Play(0.05, 1, playbackScale)
	else
		-- Preserve the existing locomotion blend for walk/run/idle.
		nextTrack:Play(0.15, 1, playbackScale)
	end
	if previousLoop and previousLoop ~= nextTrack and previousLoop.IsPlaying then
		previousLoop:Stop(if isJumpSlot then 0.05 else 0.15)
	end
	releaseLifeHold()
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
	if deathTerminalReported or character ~= boundCharacter or not boundCharacter.Parent then return end
	local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes")
	local event = remotes and remotes:FindFirstChild("DeathTerminalReached")
	if event and event:IsA("RemoteEvent") then
		deathTerminalReported = true
		event:FireServer(boundCharacter)
	end
end

local function notifyReviveAnimationFinished(boundCharacter: Model, visualReady: boolean): boolean
	if character ~= boundCharacter or tostring(boundCharacter:GetAttribute("LifeState") or "") ~= "Reviving" then return false end
	local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes")
	local remote = remotes and remotes:FindFirstChild("ReviveAnimationFinished")
	if remote and remote:IsA("RemoteEvent") then
		remote:FireServer(boundCharacter, visualReady)
		return true
	end
	return false
end

local function playBaseLifeAction(slot: string)
	-- Resolve once per life transition; no asynchronous Stopped callback can
	-- release the new character or retire a pose before its successor is ready.
	lifeRequest = { slot = slot, deadline = os.clock() + LIFE_LOAD_SECONDS, nextProbe = 0 }
end

local function playDeath()
	deathTerminalPoseHeld = false
	deathTerminalReported = false
	playBaseLifeAction("death")
end

local function stepLifeRequest()
	local request = lifeRequest
	local boundCharacter = character
	if not request or not boundCharacter then return end
	local now = os.clock()
	if now < request.nextProbe then return end
	request.nextProbe = now + RETRY_SECONDS
	if cache then
		request.descriptor = request.descriptor or AnimationResolver.Resolve(boundCharacter, "base", nil, request.slot)
		request.track = request.track or (request.descriptor and cache:Get(request.descriptor))
	end
	local track = request.track
	if cache and cache:IsLoaded(track) then
		local slot = request.slot
		-- Start at full weight before retiring any existing pose. The same
		-- terminal latch is used for death and revive; no second pose owner.
		local oldAction = currentAction
		local wasComposed = currentActionComposed
		DeathAnimationPolicy.Start(track, animationPlaybackScale(slot, track.Animation and track.Animation.AnimationId))
		if oldAction ~= track or wasComposed then stopCurrentAction(0) end
		if deathTrack and deathTrack ~= track and deathTrack.IsPlaying then deathTrack:Stop(0) end
		if reviveTrack and reviveTrack ~= track and reviveTrack.IsPlaying then reviveTrack:Stop(0) end
		stopCurrentLoop(0)
		currentLoop = nil
		currentLoopClipId = ""
		currentAction = track
		currentActionSlot = slot
		currentActionLockedUntil = 0
		boundCharacter:SetAttribute("AnimationActionEndsAt", nil)
		boundCharacter:SetAttribute("AnimationActionSlot", slot)
		boundCharacter:SetAttribute("AnimationActionClip", tostring(request.descriptor.clipId or ""))
		publishPlaybackPercent(slot)
		lifeRequest = nil
		if slot == "death" then
			deathTrack = track
			reviveTrack = nil
			boundCharacter:SetAttribute("DeathAnimationStartedAt", now)
			boundCharacter:SetAttribute("DeathTerminalPoseHeld", false)
		else
			deathTrack = nil
			reviveTrack = track
			reviveTerminalPoseHeld = false
			revealAfterEvaluation = true
		end
		print(("[game1][animation-life] %s ready · %s · length %.3f"):format(slot, tostring(request.descriptor.animationId), track.Length))
	elseif now >= request.deadline and not request.reported then
		request.reported = true
		warn(("[game1][animation-life] %s not ready after %ds · %s"):format(request.slot, LIFE_LOAD_SECONDS,
			tostring(request.descriptor and request.descriptor.animationId or "no descriptor/Animator")))
		if request.slot == "revive" then
			-- A failed visual may not indefinitely disable a returned player.
			lifeRequest = nil
			reviveReportPending = true
			if boundCharacter:GetAttribute("LifeState") == "Alive" then
				lifeTransition = false
				refreshLoop()
			end
		end
		-- Death keeps its prior pose and retries; never fabricate the terminal edge.
	end
end

local function maintainDeathTerminalPose(deltaTimeSim: number)
	local boundCharacter = character
	local track = deathTrack
	if not boundCharacter or not track then return end
	local state = boundCharacter:GetAttribute("LifeState")
	if state ~= "Dying" and state ~= "DeathIdle" then return end
	if not deathTerminalPoseHeld then
		local step = if state == "DeathIdle" then track.Length / math.max(0.01, track.Speed) else deltaTimeSim
		local reached, terminalTime = DeathAnimationPolicy.LatchVisibleTerminalPose(track, step)
		if not reached then return end
		deathTerminalPoseHeld = true
		boundCharacter:SetAttribute("DeathAnimationLength", track.Length)
		boundCharacter:SetAttribute("DeathAnimationTerminalTime", terminalTime)
		boundCharacter:SetAttribute("AnimationResolvedSlot", "death_idle")
		boundCharacter:SetAttribute("DeathTerminalPoseHeld", true)
		boundCharacter:SetAttribute("DeathTerminalPoseHeldAt", os.clock())
	end
	if state == "Dying" then notifyDeathTerminalReached(boundCharacter) end
end

local function handleLifeState()
	if not character then return end
	local current = tostring(character:GetAttribute("LifeState") or "Alive")
	local previous = lastLifeState
	lastLifeState = current
	if current == "Dying" and previous ~= "Dying" then
		lifeTransition = true
		reviveReportPending = false
		-- Cancel composed attack immediately even while the death clip loads.
		-- Native locomotion remains underneath until Death actually starts.
		if currentActionComposed or currentActionSlot == "attack" then
			stopCurrentAction(0.06)
			currentAction = nil
			currentActionSlot = ""
		end
		playDeath()
	elseif current == "DeathIdle" then
		lifeTransition = true
		if not deathTrack and not lifeRequest then playDeath() end
	elseif current == "Reviving" and previous ~= "Reviving" then
		lifeTransition = true
		character:SetAttribute("RevivePoseReady", false)
		awaitingRevivePose = true
		reviveReportPending = false
		playBaseLifeAction("revive")
	elseif current == "Alive" and previous == "Reviving" then
		lifeRequest = nil
		reviveReportPending = false
		lifeTransition = false
		refreshLoop() -- releases the held revive pose ONLY when locomotion is ready
	elseif current == "Alive" and previous ~= "Alive" then
		lifeTransition = true
		playBaseLifeAction("revive")
	else
		refreshLoop()
	end
end

local function attachAnimator(newCharacter: Model): boolean
	if character ~= newCharacter or cache then return cache ~= nil end
	animator = findAnimator(newCharacter)
	if not animator then return false end
	cache = AnimationTrackCache.new(animator)
	local boundCache = cache
	local descriptors = AnimationResolver.ListForCharacter(newCharacter)
	task.spawn(function()
		local result = boundCache:Prewarm(descriptors, 4)
		if character ~= newCharacter or cache ~= boundCache then return end
		warmResult = result
		print(("[game1][animation] prewarm %d/%d ready in %.3fs"):format(result.ready, result.total, result.elapsed))
	end)
	return true
end

local function maintainDeathPose(deltaTimeSim: number)
	local boundCharacter = character
	if not boundCharacter then return end
	local now = os.clock()
	if revealAfterEvaluation then
		revealAfterEvaluation = false
		awaitingRevivePose = false
		boundCharacter:SetAttribute("RevivePoseReady", true)
	end
	if not cache and now >= nextAnimatorProbe then
		nextAnimatorProbe = now + RETRY_SECONDS
		if attachAnimator(boundCharacter) then
			print("[game1][animation-life] late Animator attached")
			refreshLoop()
		end
	end
	stepLifeRequest()
	maintainDeathTerminalPose(deltaTimeSim)
	if reviveTrack and currentAction == reviveTrack and lifeTransition and not reviveTerminalPoseHeld then
		local reached = DeathAnimationPolicy.LatchVisibleTerminalPose(reviveTrack, deltaTimeSim)
		if reached then
			reviveTerminalPoseHeld = true
			reviveReportPending = true
			print("[game1][animation-life] revive terminal held")
			if lastLifeState == "Alive" then lifeTransition = false; refreshLoop() end
		end
	end
	if reviveReportPending and lastLifeState == "Reviving" then
		if notifyReviveAnimationFinished(boundCharacter, reviveTerminalPoseHeld) then reviveReportPending = false end
	end
	if not lifeTransition and now >= nextLoopProbe and (loopPending or (currentLoop and not currentLoop.IsPlaying)) then
		nextLoopProbe = now + RETRY_SECONDS
		refreshLoop()
	end
	if awaitingRevivePose and lastLifeState == "Alive" and currentLoop and currentLoop.IsPlaying then
		-- Fallback revive: reveal only after the first evaluated locomotion pose.
		revealAfterEvaluation = true
	end
end

local function bindCharacter(newCharacter: Model)
	if localPlayer.Character ~= newCharacter or character == newCharacter then return end
	clearCharacter()
	character = newCharacter
	lastLifeState = "Alive"
	local initialLifeState = tostring(newCharacter:GetAttribute("LifeState") or "Alive")
	lifeTransition = initialLifeState ~= "Alive"
	if not attachAnimator(newCharacter) then
		nextAnimatorProbe = os.clock() + RETRY_SECONDS
		warn("[game1][animation] Animator missing; visual unavailable, gameplay continues; retrying")
	end
	local refreshAttributes = { "SkillStunned", "GameplayTestHubRunMultiplier", "MovementState", "InCombat", "AnimationMovementDirection", "AnimationWeaponSet", "RunSpeed", "AttackSpeed", "AttackMovementLocomotionMode", "AttackMovementRunSpeedMultiplier", "AnimationAirborne", "AnimationJumpSequence" }
	for _, attribute in ipairs(refreshAttributes) do
		table.insert(connections, newCharacter:GetAttributeChangedSignal(attribute):Connect(refreshLoop))
	end
	table.insert(connections, newCharacter:GetAttributeChangedSignal("LifeState"):Connect(handleLifeState))
	handleLifeState()
	print("[game1][animation] character animation profile bound")
end

-- This function ACCEPTS an attack immediately from authored metadata.  Loading
-- the animation can take many frames or fail; it has no veto over gameplay.
function CharacterAnimationController.PlayAction(slot: string)
    if not character or lifeTransition then return nil end
    if character:GetAttribute("SkillStunned") == true then return nil end
    local now = os.clock()
    if currentActionSlot == "attack" and now < currentActionLockedUntil then return nil end
    local descriptor = AnimationResolver.ResolveAction(character, slot)
    if not descriptor and slot ~= "attack" then return nil end
    local clipId = tostring(descriptor and descriptor.clipId or "")

    if slot ~= "attack" then
        if not cache then return nil end
        local track = cache:Get(descriptor)
        if not cache:IsLoaded(track) then return nil end
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
    local fallback = false
    local isMelee = character:GetAttribute("EquippedWeaponType") ~= "bow"
    local isDual = character:GetAttribute("EquippedWeaponType") == "dualswords"
    if not timeline or (isMelee and not HitPlan.Resolve(timeline, isDual)) then
        timeline = GameplayFallback.Resolve(character)
        if not timeline then
            warn(("[game1][animation] attack clip has no usable timeline: %s"):format(clipId))
            return nil
        end
        clipId = GameplayFallback.ClipId
        fallback = true
    end
    local actionStartedAt = os.clock()
    local runtimeDuration = timeline.duration
    -- Combat timing remains independent of visual readiness. Keep a detached
    -- life hold underneath the attack until real locomotion can replace it.
    stopCurrentAction(0.06, not (currentLoop and currentLoop.IsPlaying))
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
    if fallback then
        boundCharacter:SetAttribute("AnimationAttackCompositionError", "GP timing-only fallback")
    end
    -- A published GP attack can still be previewed with the explicit temporary
    -- timing schedule. Never borrow an attack from 1hs or claim authored hits.
    local previewAuthored = fallback and descriptor ~= nil and TestPolicy.BorrowsLocomotion(
        boundCharacter, tostring(boundCharacter:GetAttribute("AnimationWeaponSet") or ""))
    if not fallback or previewAuthored then
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
    end

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

-- The creation curtain observes the existing per-character cache job.
-- Never create a second cache or block respawn indefinitely.
function CharacterAnimationController.WaitForPrewarm(model: Model, current: () -> boolean, deadline: number): boolean
    while current() and os.clock() < deadline do
        if character == model and warmResult then
            return warmResult.total > 0 and warmResult.failed == 0
        end
        RunService.Heartbeat:Wait()
    end
    return false
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
