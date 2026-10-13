-- Shared lower-body leg-root orientation for actors with full-body attack clips.
-- Keeps the authored weapon/torso attack while independently walking/running.
local Config = require(script.Parent:WaitForChild("ActorAnimationCompositionConfig"))
local ActorLowerBodyPose = {}

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

local VELOCITY_FILTER_RESPONSE = 14

local function movementDirection(entry, dt: number): Vector3?
    local live = horizontalDirection(entry.root.AssemblyLinearVelocity)
    if live then
        local old = entry.lowerMovementDirection
        if old then
            local alpha = 1 - math.exp(-VELOCITY_FILTER_RESPONSE * math.clamp(dt, 0, 0.1))
            local blend = old:Lerp(live, alpha)
            entry.lowerMovementDirection = if blend.Magnitude > 0.05 then blend.Unit else live
        else
            entry.lowerMovementDirection = live
        end
    end
    -- Preserve the last travel heading when coming to a halt. Never substitute
    -- root.LookVector: it faces the target and can differ by 180 degrees.
    return entry.lowerMovementDirection
end

function ActorLowerBodyPose.AlignToMovement(entry, dt: number?)
	if not entry.sampler or entry.weight <= 0 or #entry.lowerRootPaths == 0 then
		return
	end
	local direction = movementDirection(entry, dt or 1 / 60)
	if not direction then
		return
	end

	-- During attacks AlignOrientation points the wrapper toward the target, NOT
	-- the direction of travel. Map the authored Run lower-body branches into the
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


return table.freeze(ActorLowerBodyPose)
