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

local function movementDirection(entry): Vector3?
	return horizontalDirection(entry.root.AssemblyLinearVelocity)
		or horizontalDirection(entry.root.CFrame.LookVector)
end

function ActorLowerBodyPose.AlignToMovement(entry)
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


return table.freeze(ActorLowerBodyPose)
