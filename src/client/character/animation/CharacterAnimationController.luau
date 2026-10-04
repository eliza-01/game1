local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

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
local connections = {}

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
	if not backward or slot ~= "walk" then
		track:AdjustSpeed(1)
		return
	end
	task.spawn(function()
		local deadline = os.clock() + 1
		while track.IsPlaying and track.Length <= 0 and os.clock() < deadline do
			RunService.Heartbeat:Wait()
		end
		if track.IsPlaying and track.Length > 0 then
			track.TimePosition = math.max(0, track.Length - 0.001)
			track:AdjustSpeed(-1)
		end
	end)
end

local function refreshLoop()
	if not character or not cache then
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
	nextTrack:Play(0.15, 1, 1)
	applyBackwardPlayback(nextTrack, slot)
	character:SetAttribute("AnimationResolvedSlot", slot)
	character:SetAttribute("AnimationResolvedClip", clipId)
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
	local boundCache = cache
	local descriptors = AnimationResolver.ListForCharacter(newCharacter)
	task.spawn(function()
		local result = boundCache:Prewarm(descriptors, 4)
		if character ~= newCharacter or cache ~= boundCache then
			return
		end
		print(("[game1][animation] prewarm %d/%d ready in %.3fs"):format(result.ready, result.total, result.elapsed))
	end)
	for _, attribute in ipairs({ "MovementState", "AnimationMovementDirection", "AnimationWeaponSet" }) do
		table.insert(connections, newCharacter:GetAttributeChangedSignal(attribute):Connect(refreshLoop))
	end
	refreshLoop()
	print("[game1][animation] character animation profile bound")
end

function CharacterAnimationController.PlayAction(slot: string)
	if not character or not cache then
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
	if currentAction and currentAction.IsPlaying then
		currentAction:Stop(0.06)
	end
	currentAction = track
	track:Play(0.06, 1, 1)
	character:SetAttribute("AnimationActionSlot", slot)
	character:SetAttribute("AnimationActionClip", tostring(descriptor.clipId or ""))
	return track
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
end

return CharacterAnimationController
