local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local SkeletonHitRegionResolver = require(script.Parent:WaitForChild("SkeletonHitRegionResolver"))

local EntityHitboxService = {}
local started = false
local bindings: { [Model]: any } = {}

local function damageableModel(instance: Instance): Model?
    local current: Instance? = instance
    while current and current ~= Workspace do
        if current:IsA("Model") and current:GetAttribute("Damageable") == true then
            return current
        end
        current = current.Parent
    end
    return nil
end

local function segmentFrame(fromPosition: Vector3, toPosition: Vector3): (CFrame, number)
    local delta = toPosition - fromPosition
    local length = delta.Magnitude
    if length <= 0.001 then
        return CFrame.new(fromPosition), 0
    end
    local xAxis = delta.Unit
    local helper = if math.abs(xAxis.Y) < 0.95 then Vector3.yAxis else Vector3.zAxis
    local zAxis = xAxis:Cross(helper).Unit
    local yAxis = zAxis:Cross(xAxis).Unit
    return CFrame.fromMatrix((fromPosition + toPosition) * 0.5, xAxis, yAxis, zAxis), length
end

local function makePosePart(folder: Folder, name: string, shape: Enum.PartType): Part
    local part = Instance.new("Part")
    part.Name = name
    part.Shape = shape
    part.Transparency = 1
    part.CastShadow = false
    part.Anchored = true
    part.CanCollide = false
    part.CanTouch = false
    part.CanQuery = true
    part:SetAttribute("Game1PoseHitbox", true)
    part:SetAttribute("HitZone", "body")
    part:SetAttribute("DamageMultiplier", 1)
    part.Parent = folder
    return part
end

local function updateBinding(binding: any)
    for _, record in binding.records do
        if record.part.Parent and record.bone.Parent then
            if record.kind == "head" then
                local headPosition = SkeletonHitRegionResolver.TransformedBoneFrame(record.bone).Position
                local center = headPosition
                if record.tipBone and record.tipBone.Parent then
                    local tipPosition = SkeletonHitRegionResolver.TransformedBoneFrame(record.tipBone).Position
                    center = (headPosition + tipPosition) * 0.5
                elseif record.parentBone and record.parentBone.Parent then
                    local parentPosition = SkeletonHitRegionResolver.TransformedBoneFrame(record.parentBone).Position
                    local axis = headPosition - parentPosition
                    if axis.Magnitude > 0.001 then
                        center = headPosition + axis.Unit * record.diameter * 0.22
                    end
                end
                record.part.CFrame = CFrame.new(center)
            else
                local fromPosition = SkeletonHitRegionResolver.TransformedBoneFrame(record.parentBone).Position
                local toPosition = SkeletonHitRegionResolver.TransformedBoneFrame(record.bone).Position
                local frame, length = segmentFrame(fromPosition, toPosition)
                record.part.CFrame = frame
                record.part.Size = Vector3.new(
                    math.max(0.1, length + record.radius * 2),
                    record.radius * 2,
                    record.radius * 2
                )
            end
        end
    end
end

local function disableVisualQueries(visual: Model)
    for _, descendant in visual:GetDescendants() do
        if descendant:IsA("BasePart") then
            descendant.CanQuery = false
        end
    end
end

function EntityHitboxService.Detach(entity: Model)
    bindings[entity] = nil
    local folder = entity:FindFirstChild("CombatPoseHitboxes")
    if folder then
        folder:Destroy()
    end
    entity:SetAttribute("PoseHitboxMode", nil)
    entity:SetAttribute("PoseHitboxCount", nil)
    entity:SetAttribute("HeadHitboxBoneName", nil)
end

function EntityHitboxService.Attach(entity: Model, visual: Model): any
    EntityHitboxService.Detach(entity)
    local resolved = SkeletonHitRegionResolver.Resolve(visual)
    local folder = Instance.new("Folder")
    folder.Name = "CombatPoseHitboxes"
    folder.Parent = entity
    local records = {}

    for index, candidate in resolved.segments do
        local radius = SkeletonHitRegionResolver.SegmentRadius(candidate.bone.Name, candidate.length)
        local part = makePosePart(folder, string.format("Segment_%02d", index), Enum.PartType.Cylinder)
        part:SetAttribute("BoneName", candidate.bone.Name)
        table.insert(records, {
            kind = "segment",
            part = part,
            bone = candidate.bone,
            parentBone = candidate.parentBone,
            radius = radius,
        })
    end

    local headBone = resolved.headBone
    if headBone then
        local tipBone = resolved.headTipBone
        local tipDistance = 0
        if tipBone then
            tipDistance = (
                SkeletonHitRegionResolver.TransformedBoneFrame(tipBone).Position
                - SkeletonHitRegionResolver.TransformedBoneFrame(headBone).Position
            ).Magnitude
        end
        local diameter = math.clamp(
            math.max(1.05, tipDistance * 1.9, (tonumber(resolved.skeletonHeight) or 0) * 0.24),
            1.05,
            2.8
        )
        local part = makePosePart(folder, "Head", Enum.PartType.Ball)
        part.Size = Vector3.new(diameter, diameter, diameter)
        part:SetAttribute("BoneName", headBone.Name)
        part:SetAttribute("HitZone", "head")
        part:SetAttribute("DamageMultiplier", 2)
        table.insert(records, {
            kind = "head",
            part = part,
            bone = headBone,
            parentBone = headBone.Parent,
            tipBone = tipBone,
            diameter = diameter,
        })
    end

    if #records == 0 then
        folder:Destroy()
        entity:SetAttribute("PoseHitboxMode", "root_fallback")
        entity:SetAttribute("PoseHitboxCount", 0)
        warn(("[game1][hitbox] no usable bone segments for %s; RootCollider remains the fallback target"):format(entity:GetFullName()))
        return { count = 0, probe = nil, headBoneName = "", hasHead = false }
    end

    disableVisualQueries(visual)
    local binding = { entity = entity, folder = folder, records = records }
    bindings[entity] = binding
    updateBinding(binding)

    entity:SetAttribute("PoseHitboxMode", "bone_segments")
    entity:SetAttribute("PoseHitboxCount", #records)
    entity:SetAttribute("HeadHitboxBoneName", headBone and headBone.Name or "")

    local probe = records[1].part
    assert(damageableModel(probe) == entity, ("entity %s has no pose-following damage hitbox"):format(entity:GetFullName()))
    return {
        count = #records,
        probe = probe,
        headBoneName = headBone and headBone.Name or "",
        hasHead = headBone ~= nil,
    }
end

function EntityHitboxService.Start()
    if started then
        return
    end
    started = true
    RunService.Heartbeat:Connect(function()
        for entity, binding in bindings do
            if entity.Parent and binding.folder.Parent == entity then
                updateBinding(binding)
            else
                bindings[entity] = nil
            end
        end
    end)
    print("[game1][hitbox] pose-following combat hitboxes ready")
end

return table.freeze(EntityHitboxService)
