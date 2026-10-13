-- Roblox Studio: StarterPlayer.StarterPlayerScripts.game1Client.MonsterAnimation.ActorLocomotionSampler (ModuleScript)
-- Pooled invisible locomotion pose source. A sampler is leased exclusively while an actor is composed so individual phase offsets never synchronize visible legs.
local Workspace = game:GetService("Workspace")

local ActorSkeletonMap = require(script.Parent:WaitForChild("ActorSkeletonMap"))

local ActorLocomotionSampler = {}
ActorLocomotionSampler.__index = ActorLocomotionSampler

local function prepareProxy(visual: Model): (Model?, Animator?, string?)
	local oldArchivable = visual.Archivable
	visual.Archivable = true
	local okClone, cloneOrError = pcall(function()
		return visual:Clone()
	end)
	visual.Archivable = oldArchivable
	if not okClone or not cloneOrError then
		return nil, nil, "could not clone actor visual: " .. tostring(cloneOrError)
	end
	local proxy = cloneOrError :: Model
	proxy.Name = "__game1ActorLocomotionSampler"
	for _, object in proxy:GetDescendants() do
		if object:IsA("Bone") then
			object.Transform = CFrame.identity
		elseif object:IsA("BasePart") then
			object.Anchored = true
			object.CanCollide = false
			object.CanTouch = false
			object.CanQuery = false
			object.CastShadow = false
			object.Transparency = 1
			object.LocalTransparencyModifier = 1
		elseif object:IsA("ParticleEmitter") or object:IsA("Trail") or object:IsA("Beam") then
			object.Enabled = false
		elseif object:IsA("Script") or object:IsA("LocalScript") then
			object:Destroy()
		end
	end
	local controller = proxy:FindFirstChildWhichIsA("AnimationController", true)
	if not controller then
		controller = Instance.new("AnimationController")
		controller.Name = "AnimationController"
		controller.Parent = proxy
	end
	local animator = controller:FindFirstChildWhichIsA("Animator")
	if not animator then
		animator = Instance.new("Animator")
		animator.Parent = controller
	end
	proxy.Parent = Workspace
	return proxy, animator, nil
end

function ActorLocomotionSampler.new(visual: Model, animationId: string, playbackSpeed: number, startPhase: number?)
	local proxy, animator, errorMessage = prepareProxy(visual)
	if not proxy or not animator then
		return nil, errorMessage
	end
	local animation = Instance.new("Animation")
	animation.Name = "ActorAttackPursuitLocomotionSource"
	animation.AnimationId = "rbxassetid://" .. animationId
	local okLoad, trackOrError = pcall(function()
		return animator:LoadAnimation(animation)
	end)
	animation:Destroy()
	if not okLoad then
		proxy:Destroy()
		return nil, "could not load actor locomotion source: " .. tostring(trackOrError)
	end
	local track = trackOrError :: AnimationTrack
	track.Looped = true
	track.Priority = Enum.AnimationPriority.Movement
	local okPlay, playError = pcall(function()
		track:Play(0, 1, math.max(0.01, playbackSpeed))
	end)
	if not okPlay then
		track:Destroy()
		proxy:Destroy()
		return nil, "could not play actor locomotion source: " .. tostring(playError)
	end
	local sampler = setmetatable({
		proxy = proxy,
		track = track,
		bones = ActorSkeletonMap.BuildBonePathMap(proxy),
		users = 0,
		lastUsedAt = os.clock(),
		lastAnchorAt = 0,
		phase = 0,
		phasePending = false,
	}, ActorLocomotionSampler)
	sampler:SetPhase(startPhase or 0)
	return sampler, nil
end


function ActorLocomotionSampler:SetPlaybackSpeed(playbackSpeed: number)
	if not self.track then
		return
	end
	local speed = math.max(0.01, tonumber(playbackSpeed) or 1)
	pcall(function()
		self.track:AdjustSpeed(speed)
	end)
end

function ActorLocomotionSampler:SetPhase(phase: number)
	self.phase = math.clamp(tonumber(phase) or 0, 0, 0.999999)
	self.phasePending = true
	local length = tonumber(self.track and self.track.Length) or 0
	if length > 0.01 and self.track and self.track.IsPlaying then
		self.track.TimePosition = self.phase * length
		self.phasePending = false
	end
end

function ActorLocomotionSampler:GetBone(path: string): Bone?
	return self.bones[path]
end

function ActorLocomotionSampler:GetBoneRelativeToPivot(path: string): CFrame?
	local bone = self.bones[path]
	if not bone or not bone.Parent or not self.proxy.Parent then
		return nil
	end
	return self.proxy:GetPivot():ToObjectSpace(bone.TransformedWorldCFrame)
end

function ActorLocomotionSampler:IsReady(): boolean
	local ready = self.track ~= nil and self.track.Length > 0.01
	if ready and self.phasePending then
		self.track.TimePosition = self.phase * self.track.Length
		self.phasePending = false
	end
	return ready
end

function ActorLocomotionSampler:Touch()
	self.lastUsedAt = os.clock()
end

function ActorLocomotionSampler:AnchorNear(cameraCFrame: CFrame, now: number, interval: number)
	if now - self.lastAnchorAt < interval or not self.proxy.Parent then
		return
	end
	self.lastAnchorAt = now
	self.proxy:PivotTo(CFrame.new(cameraCFrame.Position + Vector3.new(0, -24, 0)))
end

function ActorLocomotionSampler:Destroy()
	if self.track then
		pcall(function()
			self.track:Stop(0)
			self.track:Destroy()
		end)
	end
	if self.proxy then
		self.proxy:Destroy()
	end
	self.bones = {}
end

return ActorLocomotionSampler
