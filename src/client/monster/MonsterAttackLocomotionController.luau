-- Roblox Studio: StarterPlayer.StarterPlayerScripts.game1Client.MonsterAnimation.MonsterAttackLocomotionController (ModuleScript)
-- Keeps monster legs in authored Run while the server-owned attack continues on the upper body.
-- The shared actor pool enforces one resident budget across NPCs and monsters.
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Config = require(script.Parent:WaitForChild("MonsterAnimationCompositionConfig"))
local MonsterSkeletonMap = require(script.Parent:WaitForChild("MonsterSkeletonMap"))
local MonsterLocomotionSampler = require(script.Parent:WaitForChild("MonsterLocomotionSampler"))
local Pool = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorSamplerPool"))
local ActorLowerBodyPose = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorLowerBodyPose"))

local LocalVisibility = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("MnpcLocalVisibility"))
local RigObserver = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("MnpcRigObserver"))
local Controller = {}
local started = false
local entries = {}
local activeEntries = {}
local warned = {}

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

local function suppressCombatRootTranslation(entry)
	-- Navigation Humanoid is the sole owner of world displacement during aggro,
	-- chase and attack. RootBone translation (including vertical motion) from
	-- authored clips can pull the visual waist below the terrain while its
	-- collision shell stays grounded. Preserve the animated rotation and limbs.
	for _, bone in entry.rootMotionBones do
		if bone.Parent then
			bone.Transform = bone.Transform.Rotation
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
	if active then
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
	entry.sampler = nil
	Pool:Release(sampler)
end

local function acquireSampler(entry): boolean
	if entry.sampler then return true end
	if entry.acquiring or os.clock() < (entry.retrySamplerAt or 0) then return false end
	local runId = tostring(entry.model:GetAttribute("MonsterRunAnimationId") or "")
	if not string.match(runId, "^%d+$") or runId == "0" then
		entry.disabled = true
		return false
	end
	local baseKey = "monster|" .. samplerBaseKey(entry.model)
	local phase = tonumber(entry.model:GetAttribute("MonsterAnimationPhase")) or 0
	local speed = tonumber(entry.model:GetAttribute("MonsterAttackPursuitPlaybackSpeed")) or 1
	entry.acquiring = true
	local sampler, err = Pool:Acquire(baseKey, function()
		return MonsterLocomotionSampler.new(entry.visual, runId, speed, phase)
	end, speed, phase)
	entry.acquiring = false
	if not sampler then
		if err ~= "budget" then
			warnOnce(baseKey, err or "could not create monster locomotion sampler")
			entry.retrySamplerAt = os.clock() + 2
		end
		return false
	end
	if entries[entry.model] ~= entry or not entry.model.Parent
		or not entry.root.Parent or not entry.visual.Parent
		or entry.model:GetAttribute("LifeState") ~= "Alive"
		or entry.model:GetAttribute("MonsterAttackPursuitActive") ~= true or not LocalVisibility.Full(entry.model) then
		Pool:Release(sampler)
		return false
	end
	entry.sampler = sampler
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
	local visual = model:FindFirstChild("ImportedRig")
	local root = model:FindFirstChild("HumanoidRootPart")
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
		connections = {},
		disabled = false,
	}
	entries[model] = entry
	local function refreshActive()
		setEntryActive(entry, entry.sampler ~= nil or model:GetAttribute("MonsterCombatActive") == true
			or model:GetAttribute("MonsterAttackPursuitActive") == true)
	end
	table.insert(entry.connections, model:GetAttributeChangedSignal("MonsterAttackPursuitActive"):Connect(refreshActive))
	table.insert(entry.connections, model:GetAttributeChangedSignal("MonsterCombatActive"):Connect(refreshActive))
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
	table.insert(entry.connections, model.AncestryChanged:Connect(function()
		if not model:IsDescendantOf(Workspace) then unbind(model) end
	end))
	refreshActive()
end

local function bindFolder(folder: Folder)
    RigObserver.Watch(folder, entries, bindMonster, unbind)
end

local function step(deltaTime: number)
	local camera = Workspace.CurrentCamera
	if not camera then
		return
	end
	local now = os.clock()
	local maxDistanceSquared = Config.MaxDistance * Config.MaxDistance
	for entry in activeEntries do
		local model = entry.model
		if not model.Parent or not entry.root.Parent or not entry.visual.Parent then
			unbind(model)
			continue
		end
		local cameraDelta = entry.root.Position - camera.CFrame.Position
		local distanceSquared = cameraDelta:Dot(cameraDelta)
		local alive = tostring(model:GetAttribute("LifeState")) == "Alive"
        -- Death owns the whole rig immediately; never blend running legs into Death.
        if not alive or not LocalVisibility.Full(model) then
            entry.weight = 0
            releaseSampler(entry)
            setEntryActive(entry, false)
            continue
        end
		local pursuitActive = model:GetAttribute("MonsterAttackPursuitActive") == true and alive
		local combatActive = model:GetAttribute("MonsterCombatActive") == true and alive
		-- Combat activates the same existing PreSimulation loop during Chase as
		-- well as Attack. Never stack imported RootBone translation on movement.
		if (combatActive or pursuitActive) and distanceSquared <= maxDistanceSquared then
			suppressCombatRootTranslation(entry)
		end
		local wantsComposition = pursuitActive and distanceSquared <= maxDistanceSquared
		if wantsComposition and not entry.sampler and not entry.disabled then
			acquireSampler(entry)
		end
		if entry.sampler then
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
				ActorLowerBodyPose.AlignToMovement(entry, deltaTime)
			end
			if entry.weight <= 0 and not wantsComposition then
				releaseSampler(entry)
				if not pursuitActive and not combatActive then
					setEntryActive(entry, false)
				end
			end
		elseif not pursuitActive and not combatActive then
			setEntryActive(entry, false)
		end
	end
	Pool:Cleanup(now)
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
		Config.MaxComposedActors,
		Config.MaxDistance
	))
end

return table.freeze(Controller)
