local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local AttackConfig = require(CombatShared:WaitForChild("AttackConfig"))
local AimPoseController = require(script.Parent.Parent.Parent:WaitForChild("combat"):WaitForChild("AimPoseController"))

local AttackUpperBodyComposer = {}

local started = false
local active = false
local activeCharacter: Model? = nil
local targetBridge: Bone? = nil
local targetHost: BasePart? = nil
local sourceProxy: Model? = nil
local sourceBridge: Bone? = nil
local sourceHost: BasePart? = nil
local sourceAnimation: Animation? = nil
local sourceTrack: AnimationTrack? = nil
local sourcePlaybackSpeed = 1
local sourcePoseFrozen = false
local blendStartedAt = 0
local exitBlendStartedAt = 0
local exitBlendRequested = false
local upperPairs = {}

local function spineOrder(name: string): number?
	local lower = string.lower(name)
	if lower == "spine" then
		return 0
	end
	local suffix = string.match(lower, "^spine%.(%d+)$")
	if suffix then
		return tonumber(suffix)
	end
	return nil
end

local function findUpperBodyBridge(root: Instance): Bone?
	local preferred = root:FindFirstChild("spine.001", true)
	if preferred and preferred:IsA("Bone") then
		return preferred
	end

	local candidates = {}
	for _, object in root:GetDescendants() do
		if object:IsA("Bone") then
			local order = spineOrder(object.Name)
			if order ~= nil and order >= 1 then
				table.insert(candidates, { bone = object, order = order })
			end
		end
	end
	table.sort(candidates, function(left, right)
		return left.order < right.order
	end)
	return if candidates[1] then candidates[1].bone else nil
end

local function findNamedBone(root: Instance, name: string): Bone?
	local object = root:FindFirstChild(name, true)
	return if object and object:IsA("Bone") then object else nil
end

local function nearestBasePart(instance: Instance?): BasePart?
	local current = instance
	while current do
		if current:IsA("BasePart") then
			return current
		end
		current = current.Parent
	end
	return nil
end

local function parentWorldCFrame(bone: Bone): CFrame?
	local parent = bone.Parent
	if not parent then
		return nil
	end
	if parent:IsA("Bone") then
		return parent.TransformedWorldCFrame
	end
	if parent:IsA("BasePart") then
		return parent.CFrame
	end
	return nil
end

local function smoothstep(alpha: number): number
	local value = math.clamp(alpha, 0, 1)
	return value * value * (3 - 2 * value)
end

local function destroyProxy()
	AimPoseController.SetPoseDrivenExternally(false)
	upperPairs = {}
	targetBridge = nil
	targetHost = nil
	sourceBridge = nil
	sourceHost = nil
	sourcePlaybackSpeed = 1
	sourcePoseFrozen = false
	blendStartedAt = 0
	exitBlendStartedAt = 0
	exitBlendRequested = false
	if sourceTrack then
		pcall(function()
			sourceTrack:Stop(0)
			sourceTrack:Destroy()
		end)
		sourceTrack = nil
	end
	if sourceAnimation then
		sourceAnimation:Destroy()
		sourceAnimation = nil
	end
	if sourceProxy then
		sourceProxy:Destroy()
		sourceProxy = nil
	end
	activeCharacter = nil
	active = false
end

local function prepareProxy(visual: Model): (Model?, Animator?, string?)
	local oldArchivable = visual.Archivable
	visual.Archivable = true
	local okClone, cloneOrError = pcall(function()
		return visual:Clone()
	end)
	visual.Archivable = oldArchivable
	if not okClone or not cloneOrError then
		return nil, nil, "could not clone Visual: " .. tostring(cloneOrError)
	end

	local proxy = cloneOrError :: Model
	proxy.Name = "__Game1AttackUpperBodyProxy"
	for _, object in proxy:GetDescendants() do
		if object:IsA("Bone") then
			-- Clone() can capture the currently evaluated locomotion pose. The proxy
			-- must contain only the source attack animation.
			object.Transform = CFrame.identity
		elseif object:IsA("BasePart") then
			object.Anchored = true
			object.CanCollide = false
			object.CanTouch = false
			object.CanQuery = false
			object.Transparency = 1
			object.LocalTransparencyModifier = 1
		elseif object:IsA("Decal") or object:IsA("Texture") then
			object.Transparency = 1
		elseif object:IsA("ParticleEmitter") or object:IsA("Trail") or object:IsA("Beam") then
			object.Enabled = false
		elseif object:IsA("Script") or object:IsA("LocalScript") then
			object:Destroy()
		end
	end

	local animationController = proxy:FindFirstChildWhichIsA("AnimationController", true)
	if not animationController then
		proxy:Destroy()
		return nil, nil, "attack source proxy has no AnimationController"
	end
	local animator = animationController:FindFirstChildWhichIsA("Animator")
	if not animator then
		animator = Instance.new("Animator")
		animator.Parent = animationController
	end

	proxy.Parent = Workspace
	proxy:PivotTo(visual:GetPivot())
	return proxy, animator, nil
end

local function buildUpperPairs(proxy: Model, bridge: Bone): ({ any }, string?)
	local pairs = {}
	for _, targetObject in bridge:GetDescendants() do
		if targetObject:IsA("Bone") then
			local sourceObject = findNamedBone(proxy, targetObject.Name)
			if sourceObject then
				table.insert(pairs, {
					target = targetObject,
					source = sourceObject,
				})
			end
		end
	end
	if #pairs == 0 then
		return {}, "no upper-body descendant bones matched the source attack"
	end
	return pairs, nil
end

local function blendWeight(now: number): (number, boolean)
	local entrySeconds = math.max(0, tonumber(AttackConfig.UpperBodyAttackEntryBlendSeconds) or 0.10)
	local exitSeconds = math.max(0, tonumber(AttackConfig.UpperBodyAttackExitBlendSeconds) or 0.12)
	local entry = if entrySeconds > 0 then smoothstep((now - blendStartedAt) / entrySeconds) else 1
	if not exitBlendRequested then
		return entry, false
	end
	local exitLinear = if exitSeconds > 0 then math.clamp((now - exitBlendStartedAt) / exitSeconds, 0, 1) else 1
	return entry * (1 - smoothstep(exitLinear)), exitLinear >= 1
end

function AttackUpperBodyComposer.IsActive(): boolean
	return active
end

function AttackUpperBodyComposer.GetExitBlendSeconds(): number
	return math.max(0, tonumber(AttackConfig.UpperBodyAttackExitBlendSeconds) or 0.12)
end

function AttackUpperBodyComposer.BeginExitBlend()
	if not active or exitBlendRequested then
		return
	end
	exitBlendRequested = true
	exitBlendStartedAt = os.clock()
end

function AttackUpperBodyComposer.Begin(character: Model, descriptor: any, playbackSpeed: number): (AnimationTrack?, string?)
	local visual = character:FindFirstChild("Visual")
	if not visual or not visual:IsA("Model") then
		return nil, "visible character rig is missing"
	end
	local bridge = findUpperBodyBridge(visual)
	if not bridge then
		return nil, "upper-body bridge bone is missing"
	end
	local host = nearestBasePart(bridge)
	if not host then
		return nil, "upper-body bridge has no BasePart host"
	end

	local proxy, animator, proxyError = prepareProxy(visual)
	if not proxy or not animator then
		return nil, proxyError or "could not create attack source proxy"
	end
	local proxyBridge = findNamedBone(proxy, bridge.Name)
	if not proxyBridge then
		proxy:Destroy()
		return nil, "source proxy bridge bone is missing: " .. bridge.Name
	end
	local proxyHost = nearestBasePart(proxyBridge)
	if not proxyHost then
		proxy:Destroy()
		return nil, "source proxy bridge has no BasePart host"
	end
	local pairs, pairError = buildUpperPairs(proxy, bridge)
	if pairError then
		proxy:Destroy()
		return nil, pairError
	end

	local animation = Instance.new("Animation")
	animation.Name = "AttackUpperBody_" .. tostring(descriptor.clipId or "attack")
	animation.AnimationId = tostring(descriptor.animationId or "")
	local okLoad, trackOrError = pcall(function()
		return animator:LoadAnimation(animation)
	end)
	if not okLoad then
		animation:Destroy()
		proxy:Destroy()
		return nil, "could not load source attack: " .. tostring(trackOrError)
	end

	local track = trackOrError :: AnimationTrack
	track.Looped = false
	track.Priority = Enum.AnimationPriority.Action
	pcall(function()
		track:Play(0, 0, 0)
	end)
	local deadline = os.clock() + math.max(0.1, tonumber(AttackConfig.UpperBodyAttackTrackReadySeconds) or 1)
	while track.Length <= 0.01 and os.clock() < deadline do
		RunService.Heartbeat:Wait()
	end
	if track.Length <= 0.01 then
		track:Destroy()
		animation:Destroy()
		proxy:Destroy()
		return nil, "source attack track did not become ready"
	end
	track:Stop(0)
	track.TimePosition = 0

	destroyProxy()
	active = true
	activeCharacter = character
	AimPoseController.SetPoseDrivenExternally(true)
	targetBridge = bridge
	targetHost = host
	sourceProxy = proxy
	sourceBridge = proxyBridge
	sourceHost = proxyHost
	sourceAnimation = animation
	sourceTrack = track
	upperPairs = pairs
	sourcePlaybackSpeed = math.max(0.01, tonumber(playbackSpeed) or 1)
	sourcePoseFrozen = false
	blendStartedAt = os.clock()
	exitBlendStartedAt = 0
	exitBlendRequested = false

	track:Play(0, 1, sourcePlaybackSpeed)
	pcall(function()
		track.TimePosition = 0
	end)
	return track, nil
end

function AttackUpperBodyComposer.End()
	destroyProxy()
end

local function holdSourceTerminalPose(deltaTime: number)
	local track = sourceTrack
	if not active or not track or sourcePoseFrozen then
		return
	end
	local length = tonumber(track.Length) or 0
	if length <= 0.05 then
		return
	end
	local terminalLead = math.max(1 / 240, tonumber(AttackConfig.UpperBodyAttackTerminalLeadSeconds) or (1 / 120))
	local terminalTime = math.max(0, length - terminalLead)
	local projectedStep = math.max(1 / 240, math.max(0, deltaTime) * sourcePlaybackSpeed * 1.25)
	if track.TimePosition + projectedStep >= terminalTime then
		if track.TimePosition < terminalTime then
			track.TimePosition = terminalTime
		end
		track:AdjustSpeed(0)
		sourcePoseFrozen = true
	end
end

local function step(deltaTime: number)
	if not active then
		return
	end
	local currentCharacter = activeCharacter
	local target = targetBridge
	local targetRoot = targetHost
	local source = sourceBridge
	local sourceRoot = sourceHost
	if not currentCharacter or not currentCharacter.Parent
		or not target or not target.Parent
		or not targetRoot or not targetRoot.Parent
		or not source or not source.Parent
		or not sourceRoot or not sourceRoot.Parent
	then
		destroyProxy()
		return
	end

	-- Animator has already evaluated the visible lower-body combat stance for this
	-- frame. Save that upper-body pose before replacing only the bridge subtree.
	local baseBridgeTransform = target.Transform
	for _, pair in ipairs(upperPairs) do
		if pair.target.Parent and pair.source.Parent then
			pair.baseTransform = pair.target.Transform
		end
	end

	-- Map the attack bridge orientation from the invisible source rig into the
	-- visible rig while preserving the lower-body driven parent chain.
	target.Transform = source.Transform
	local parentWorld = parentWorldCFrame(target)
	if not parentWorld then
		target.Transform = baseBridgeTransform
		return
	end
	local sourceArmature = sourceRoot.CFrame:ToObjectSpace(source.TransformedWorldCFrame)
	local mappedAttackWorld = targetRoot.CFrame * sourceArmature
	local currentWorld = target.TransformedWorldCFrame
	local desiredWorld = CFrame.new(currentWorld.Position) * mappedAttackWorld.Rotation
	local currentTransform = target.Transform
	local currentLocal = parentWorld:ToObjectSpace(currentWorld)
	local effectiveBase = currentLocal * currentTransform:Inverse()
	local desiredLocal = parentWorld:ToObjectSpace(desiredWorld)
	local attackBridgeTransform = effectiveBase:Inverse() * desiredLocal

	local weight, exitComplete = blendWeight(os.clock())
	target.Transform = baseBridgeTransform:Lerp(attackBridgeTransform, weight)
	for _, pair in ipairs(upperPairs) do
		if pair.target.Parent and pair.source.Parent and pair.baseTransform then
			pair.target.Transform = pair.baseTransform:Lerp(pair.source.Transform, weight)
		end
	end

	-- Final owner for this frame, matching RobloxLineage: aim is applied only
	-- after locomotion + source attack + bridge compensation are complete.
	AimPoseController.StepAfterExternalPose(deltaTime)

	if exitComplete then
		destroyProxy()
	end
end

function AttackUpperBodyComposer.Start()
	if started then
		return
	end
	started = true
	RunService.PreAnimation:Connect(holdSourceTerminalPose)
	RunService.PreSimulation:Connect(step)
end

return AttackUpperBodyComposer
