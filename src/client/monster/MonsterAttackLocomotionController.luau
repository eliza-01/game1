-- Roblox Studio: StarterPlayer.StarterPlayerScripts.game1Client.MonsterAnimation.MonsterAttackLocomotionController (ModuleScript)
-- Keeps monster legs in authored Run while the server-owned attack continues on the upper body.
-- Samplers are pooled by rig/run identity but leased exclusively so nearby monsters keep independent phases.
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Config = require(script.Parent:WaitForChild("MonsterAnimationCompositionConfig"))
local MonsterSkeletonMap = require(script.Parent:WaitForChild("MonsterSkeletonMap"))
local MonsterLocomotionSampler = require(script.Parent:WaitForChild("MonsterLocomotionSampler"))

local Controller = {}
local started = false
local entries = {}
local activeEntries = {}
local samplers = {}
local samplerSerial = 0
local warned = {}
local lastCleanupAt = 0

local function warnOnce(key: string, message: string)
	if warned[key] then
		return
	end
	warned[key] = true
	warn("[game1][MONSTER_ANIM] " .. message)
end

local function approach(current: number, target: number, delta: number): number
	if current < target then
		return math.min(target, current + delta)
	end
	return math.max(target, current - delta)
end

local function parentTransformedWorldCFrame(bone: Bone): CFrame?
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

local function horizontalDirection(vector: Vector3): Vector3?
	local flat = Vector3.new(vector.X, 0, vector.Z)
	if flat.Magnitude <= Config.MovementDirectionMinSpeed then
		return nil
	end
	return flat.Unit
end

local function movementDirection(entry): Vector3?
	return horizontalDirection(entry.root.AssemblyLinearVelocity)
		or horizontalDirection(entry.root.CFrame.LookVector)
end

local function resolveRootMotionBones(visual: Model): { Bone }
	local result = {}
	for _, object in visual:GetDescendants() do
		if object:IsA("Bone") then
			local runtimeBridge = object:GetAttribute("Game1RuntimeAnimationRoot") == true
			local namedBridge = object.Name == "RootBone" and object.Parent and object.Parent:IsA("BasePart")
			if runtimeBridge or namedBridge then
				table.insert(result, object)
			end
		end
	end
	return result
end

local function suppressHorizontalAttackRootMotion(entry)
	-- The attack clip may contain authored forward/back root translation. During
	-- server-owned pursuit that displacement stacks on top of physical motion and
	-- looks like short teleports. Keep the authored rotation and vertical motion,
	-- but let the navigation Humanoid own all horizontal world displacement.
	for _, bone in entry.rootMotionBones do
		if bone.Parent then
			local transform = bone.Transform
			bone.Transform = CFrame.new(0, transform.Position.Y, 0) * transform.Rotation
		end
	end
end

local function alignLowerBodyRootsToMovement(entry)
	if not entry.sampler or entry.weight <= 0 or #entry.lowerRootPaths == 0 then
		return
	end
	local direction = movementDirection(entry)
	if not direction then
		return
	end

	-- The wrapper/root is owned by Humanoid.AutoRotate and therefore follows the
	-- actual travel direction. Map the authored Run lower-body branches into that
	-- movement frame instead of inheriting any large yaw authored into Atk01.
	-- Only independent leg subtrees are compensated; pelvis/spine ownership stays
	-- with the attack so the torso can still twist naturally above the hips.
	local movementRoot = CFrame.lookAlong(Vector3.zero, direction, Vector3.yAxis)
	local desiredVisualRotation = (movementRoot * entry.visualRootOffsetRotation).Rotation
	for _, path in entry.lowerRootPaths do
		local targetBone = entry.targetBones[path]
		local sourceRelative = entry.sampler:GetBoneRelativeToPivot(path)
		if targetBone and targetBone.Parent and sourceRelative then
			local parentWorld = parentTransformedWorldCFrame(targetBone)
			if parentWorld then
				local currentTransform = targetBone.Transform
				local currentWorld = targetBone.TransformedWorldCFrame
				local currentLocal = parentWorld:ToObjectSpace(currentWorld)
				local effectiveBase = currentLocal * currentTransform:Inverse()
				local desiredRotation = (desiredVisualRotation * sourceRelative.Rotation).Rotation
				local desiredWorld = CFrame.new(currentWorld.Position) * desiredRotation
				local desiredLocal = parentWorld:ToObjectSpace(desiredWorld)
				local alignedTransform = effectiveBase:Inverse() * desiredLocal
				targetBone.Transform = currentTransform:Lerp(alignedTransform, entry.weight)
			end
		end
	end
end

local function samplerBaseKey(model: Model): string
	return table.concat({
		tostring(model:GetAttribute("MonsterVisualKey") or ""),
		tostring(model:GetAttribute("MonsterRunAnimationId") or ""),
	}, "|")
end

local function setEntryActive(entry, active: boolean)
	if active and not entry.disabled then
		activeEntries[entry] = true
	else
		activeEntries[entry] = nil
	end
end

local function releaseSampler(entry)
	local sampler = entry.sampler
	if not sampler then
		return
	end
	sampler.users = math.max(0, sampler.users - 1)
	sampler:Touch()
	entry.sampler = nil
	entry.samplerKey = nil
end

local function acquireSampler(entry): boolean
	if entry.sampler then
		return true
	end
	local runId = tostring(entry.model:GetAttribute("MonsterRunAnimationId") or "")
	if not string.match(runId, "^%d+$") or runId == "0" then
		entry.disabled = true
		setEntryActive(entry, false)
		return false
	end
	local baseKey = samplerBaseKey(entry.model)
	local sampler = nil
	local cacheKey = nil
	for key, candidate in samplers do
		if candidate.baseKey == baseKey and candidate.users <= 0 then
			sampler = candidate
			cacheKey = key
			break
		end
	end
	local phase = tonumber(entry.model:GetAttribute("MonsterAnimationPhase")) or 0
	if not sampler then
		local playbackSpeed = tonumber(entry.model:GetAttribute("MonsterAttackPursuitPlaybackSpeed")) or 1
		local created, errorMessage = MonsterLocomotionSampler.new(entry.visual, runId, playbackSpeed, phase)
		if not created then
			warnOnce(baseKey, errorMessage or "could not create monster locomotion sampler")
			entry.disabled = true
			setEntryActive(entry, false)
			return false
		end
		sampler = created
		sampler.baseKey = baseKey
		samplerSerial += 1
		cacheKey = baseKey .. "#" .. tostring(samplerSerial)
		samplers[cacheKey] = sampler
	else
		sampler:SetPhase(phase)
		sampler:SetPlaybackSpeed(tonumber(entry.model:GetAttribute("MonsterAttackPursuitPlaybackSpeed")) or 1)
	end
	sampler.users = 1
	sampler:Touch()
	entry.sampler = sampler
	entry.samplerKey = cacheKey
	return true
end

local function unbind(model: Model)
	local entry = entries[model]
	if not entry then
		return
	end
	for _, connection in entry.connections do
		connection:Disconnect()
	end
	releaseSampler(entry)
	setEntryActive(entry, false)
	entries[model] = nil
end

local function bindMonster(model: Model)
	if entries[model] or model:GetAttribute("Game1MonsterRuntime") ~= true then
		return
	end
	task.spawn(function()
		local visual = model:FindFirstChild("ImportedRig") or model
		local root = model:FindFirstChild("HumanoidRootPart") or model:WaitForChild("HumanoidRootPart", 5)
		if not visual or not visual:IsA("Model") or not root or not root:IsA("BasePart") or not model.Parent or entries[model] then
			return
		end
		local lowerPaths = MonsterSkeletonMap.ResolveLowerBodyPaths(visual)
		local lowerRootPaths = MonsterSkeletonMap.ResolveIndependentLowerBodyRoots(visual, lowerPaths)
		if #lowerPaths == 0 then
			warnOnce(tostring(model:GetAttribute("MonsterVisualKey") or model.Name), "no lower-body bone branches resolved; attack locomotion composition disabled for this rig")
			return
		end
		local entry = {
			model = model,
			visual = visual,
			root = root,
			targetBones = MonsterSkeletonMap.BuildBonePathMap(visual),
			lowerPaths = lowerPaths,
			lowerRootPaths = lowerRootPaths,
			visualRootOffsetRotation = root.CFrame:ToObjectSpace(visual:GetPivot()).Rotation,
			rootMotionBones = resolveRootMotionBones(visual),
			weight = 0,
			sampler = nil,
			samplerKey = nil,
			connections = {},
			disabled = false,
		}
		entries[model] = entry
		table.insert(entry.connections, model:GetAttributeChangedSignal("MonsterAttackPursuitActive"):Connect(function()
			if model:GetAttribute("MonsterAttackPursuitActive") == true then
				setEntryActive(entry, true)
			end
		end))
		table.insert(entry.connections, model:GetAttributeChangedSignal("MonsterAttackPursuitPlaybackSpeed"):Connect(function()
			if entry.sampler then
				entry.sampler:SetPlaybackSpeed(tonumber(model:GetAttribute("MonsterAttackPursuitPlaybackSpeed")) or 1)
			end
			if model:GetAttribute("MonsterAttackPursuitActive") == true then
				setEntryActive(entry, true)
			end
		end))
		table.insert(entry.connections, model.Destroying:Connect(function()
			unbind(model)
		end))
		if model:GetAttribute("MonsterAttackPursuitActive") == true then
			setEntryActive(entry, true)
		end
	end)
end

local function bindFolder(folder: Folder)
	for _, child in folder:GetChildren() do
		if child:IsA("Model") then
			bindMonster(child)
		end
	end
	folder.ChildAdded:Connect(function(child)
		if child:IsA("Model") then
			bindMonster(child)
		end
	end)
end

local function cleanupSamplers(now: number)
	if now - lastCleanupAt < 1 then
		return
	end
	lastCleanupAt = now
	for key, sampler in samplers do
		if sampler.users <= 0 and now - sampler.lastUsedAt >= Config.SamplerIdleTtlSeconds then
			sampler:Destroy()
			samplers[key] = nil
		end
	end
end

local function step(deltaTime: number)
	local camera = Workspace.CurrentCamera
	if not camera then
		return
	end
	local now = os.clock()
	local activeCount = 0
	local maxDistanceSquared = Config.MaxDistance * Config.MaxDistance
	for entry in activeEntries do
		local model = entry.model
		if not model.Parent or not entry.root.Parent or not entry.visual.Parent then
			unbind(model)
			continue
		end
		local cameraDelta = entry.root.Position - camera.CFrame.Position
		local distanceSquared = cameraDelta:Dot(cameraDelta)
		local pursuitActive = model:GetAttribute("MonsterAttackPursuitActive") == true
			and tostring(model:GetAttribute("LifeState")) == "Alive"
		if pursuitActive then
			suppressHorizontalAttackRootMotion(entry)
		end
		local wantsComposition = pursuitActive and distanceSquared <= maxDistanceSquared
		if wantsComposition and not entry.sampler and activeCount < Config.MaxComposedMonsters then
			acquireSampler(entry)
		end
		if entry.sampler then
			activeCount += 1
			entry.sampler:AnchorNear(camera.CFrame, now, Config.SamplerAnchorInterval)
			local targetWeight = if wantsComposition then 1 else 0
			local duration = if targetWeight > entry.weight then Config.EntryBlendSeconds else Config.ExitBlendSeconds
			local stepSize = if duration > 0 then math.max(0, deltaTime) / duration else 1
			entry.weight = approach(entry.weight, targetWeight, stepSize)
			if entry.weight > 0 and entry.sampler:IsReady() then
				for _, path in entry.lowerPaths do
					local targetBone = entry.targetBones[path]
					local sourceBone = entry.sampler:GetBone(path)
					if targetBone and targetBone.Parent and sourceBone and sourceBone.Parent then
						targetBone.Transform = targetBone.Transform:Lerp(sourceBone.Transform, entry.weight)
					end
				end
				alignLowerBodyRootsToMovement(entry)
			end
			if entry.weight <= 0 and not wantsComposition then
				releaseSampler(entry)
				if not pursuitActive then
					setEntryActive(entry, false)
				end
			end
		elseif not pursuitActive then
			setEntryActive(entry, false)
		end
	end
	cleanupSamplers(now)
end

function Controller.Start()
	if started then
		return
	end
	started = true
	local current = Workspace:FindFirstChild("Monsters")
	if current and current:IsA("Folder") then
		bindFolder(current)
	end
	Workspace.ChildAdded:Connect(function(child)
		if child.Name == "Monsters" and child:IsA("Folder") then
			bindFolder(child)
		end
	end)
	RunService.PreSimulation:Connect(step)
	print(("[game1][MONSTER_ANIM] attack locomotion composition ready · max %d · radius %d"):format(
		Config.MaxComposedMonsters,
		Config.MaxDistance
	))
end

return table.freeze(Controller)
