local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local SkeletonHitRegionResolver = require(CombatShared:WaitForChild("SkeletonHitRegionResolver"))

local EntityHitboxService = {}
local started = false
local bindings: { [Model]: any } = {}

local function damageableModelFromPart(part: Instance): Model?
    local current: Instance? = part
    while current and current ~= Workspace do
        if current:IsA("Model") and current:GetAttribute("Damageable") == true then
            return current
        end
        current = current.Parent
    end
    return nil
end

local function overlapParams(exclude: Model?): OverlapParams
    local params = OverlapParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = if exclude then { exclude } else {}
    return params
end

local function sphereIntersectsBox(boxCFrame: CFrame, halfSize: Vector3, center: Vector3, radius: number): boolean
    local localPoint = boxCFrame:PointToObjectSpace(center)
    local dx = math.max(math.abs(localPoint.X) - halfSize.X, 0)
    local dy = math.max(math.abs(localPoint.Y) - halfSize.Y, 0)
    local dz = math.max(math.abs(localPoint.Z) - halfSize.Z, 0)
    return dx * dx + dy * dy + dz * dz <= radius * radius
end

local function clipSlab(
    origin: number,
    delta: number,
    extent: number,
    tMin: number,
    tMax: number
): (boolean, number, number)
    if math.abs(delta) <= 1e-8 then
        return origin >= -extent and origin <= extent, tMin, tMax
    end
    local inverse = 1 / delta
    local first = (-extent - origin) * inverse
    local second = (extent - origin) * inverse
    if first > second then
        first, second = second, first
    end
    tMin = math.max(tMin, first)
    tMax = math.min(tMax, second)
    return tMin <= tMax, tMin, tMax
end

local function capsuleIntersectsBox(
    boxCFrame: CFrame,
    halfSize: Vector3,
    fromPosition: Vector3,
    toPosition: Vector3,
    radius: number
): boolean
    -- Minkowski-expand the attack OBB by the capsule radius, then clip the
    -- animated bone segment against that box. This is conservative only at the
    -- eight rounded corners and is much tighter than the old physical cylinders.
    local fromLocal = boxCFrame:PointToObjectSpace(fromPosition)
    local toLocal = boxCFrame:PointToObjectSpace(toPosition)
    local delta = toLocal - fromLocal
    local expanded = halfSize + Vector3.new(radius, radius, radius)
    local tMin = 0
    local tMax = 1

    local ok
    ok, tMin, tMax = clipSlab(fromLocal.X, delta.X, expanded.X, tMin, tMax)
    if not ok then
        return false
    end
    ok, tMin, tMax = clipSlab(fromLocal.Y, delta.Y, expanded.Y, tMin, tMax)
    if not ok then
        return false
    end
    ok, tMin, tMax = clipSlab(fromLocal.Z, delta.Z, expanded.Z, tMin, tMax)
    return ok
end

function EntityHitboxService.Detach(entity: Model)
    bindings[entity] = nil
    -- Clean up legacy proxy folders if this place was saved while the old
    -- Heartbeat-following implementation was active.
    local legacyFolder = entity:FindFirstChild("CombatPoseHitboxes")
    if legacyFolder then
        legacyFolder:Destroy()
    end
    entity:SetAttribute("PoseHitboxMode", nil)
    entity:SetAttribute("PoseHitboxCount", nil)
    entity:SetAttribute("HeadHitboxBoneName", nil)
end

function EntityHitboxService.Attach(entity: Model, visual: Model): any
    EntityHitboxService.Detach(entity)
    local resolved = SkeletonHitRegionResolver.Resolve(visual)
    local records = {}

    for _, candidate in resolved.segments do
        table.insert(records, {
            kind = "segment",
            bone = candidate.bone,
            parentBone = candidate.parentBone,
            role = candidate.role,
            radius = SkeletonHitRegionResolver.SegmentRadius(
                tostring(candidate.role or "generic"),
                candidate.length,
                resolved.skeletonHeight
            ),
        })
    end

    if resolved.headBone then
        table.insert(records, {
            kind = "head",
            bone = resolved.headBone,
            radius = SkeletonHitRegionResolver.HeadRadius(resolved.skeletonHeight),
        })
    end

    if #records == 0 then
        entity:SetAttribute("PoseHitboxMode", "root_fallback")
        entity:SetAttribute("PoseHitboxCount", 0)
        warn(("[game1][hitbox] no usable virtual bone regions for %s; RootCollider remains the fallback target")
            :format(entity:GetFullName()))
        return { count = 0, probe = nil, headBoneName = "", hasHead = false }
    end

    bindings[entity] = {
        entity = entity,
        visual = visual,
        records = records,
    }
    entity:SetAttribute("PoseHitboxMode", "virtual_bone_regions")
    entity:SetAttribute("PoseHitboxCount", #records)
    entity:SetAttribute("HeadHitboxBoneName", resolved.headBone and resolved.headBone.Name or "")

    return {
        count = #records,
        probe = nil,
        headBoneName = resolved.headBone and resolved.headBone.Name or "",
        hasHead = resolved.headBone ~= nil,
    }
end

function EntityHitboxService.HasBinding(entity: Model): boolean
    local binding = bindings[entity]
    return binding ~= nil and entity.Parent ~= nil and binding.visual.Parent ~= nil
end

function EntityHitboxService.QueryBox(entity: Model, boxCFrame: CFrame, boxSize: Vector3): any?
    local binding = bindings[entity]
    if not binding or not entity.Parent or not binding.visual.Parent then
        return nil
    end

    local halfSize = boxSize * 0.5
    local headHit = false
    local headRadius = 0
    for _, record in binding.records do
        if record.bone.Parent then
            if record.kind == "head" then
                local center = SkeletonHitRegionResolver.TransformedBoneFrame(record.bone).Position
                if sphereIntersectsBox(boxCFrame, halfSize, center, record.radius) then
                    headHit = true
                    headRadius = record.radius
                end
            elseif record.parentBone.Parent then
                local fromPosition = SkeletonHitRegionResolver.TransformedBoneFrame(record.parentBone).Position
                local toPosition = SkeletonHitRegionResolver.TransformedBoneFrame(record.bone).Position
                if capsuleIntersectsBox(boxCFrame, halfSize, fromPosition, toPosition, record.radius) then
                    -- Body wins over head for broad melee boxes, matching the old
                    -- RobloxLineage rule that a tall sweep must not become a free headshot.
                    return {
                        hitZone = "body",
                        damageMultiplier = 1,
                        boneName = record.bone.Name,
                        role = record.role,
                        radius = record.radius,
                        hitPosition = (fromPosition + toPosition) * 0.5,
                    }
                end
            end
        end
    end

    if headHit then
        local headBoneName = binding.entity:GetAttribute("HeadHitboxBoneName") or ""
        local headPosition = nil
        for _, record in binding.records do
            if record.kind == "head" and record.bone.Parent then
                headPosition = SkeletonHitRegionResolver.TransformedBoneFrame(record.bone).Position
                break
            end
        end
        return {
            hitZone = "head",
            damageMultiplier = 2,
            boneName = headBoneName,
            role = "head",
            radius = headRadius,
            hitPosition = headPosition,
        }
    end
    return nil
end

function EntityHitboxService.QueryDamageablesInBox(exclude: Model?, boxCFrame: CFrame, boxSize: Vector3): { any }
    local results = {}
    local seen: { [Model]: boolean } = {}

    -- Virtual animated hit regions are authoritative for bound rigs. Query them
    -- directly instead of relying on a broadphase RootCollider/mesh overlap first;
    -- otherwise a posed limb can visibly intersect the weapon volume yet be missed.
    for entity, binding in pairs(bindings) do
        if entity ~= exclude
            and entity.Parent ~= nil
            and binding.visual.Parent ~= nil
            and entity:GetAttribute("Damageable") == true
        then
            local hit = EntityHitboxService.QueryBox(entity, boxCFrame, boxSize)
            if hit then
                seen[entity] = true
                table.insert(results, {
                    model = entity,
                    hit = hit,
                    mode = "virtual_bone_regions",
                })
            end
        end
    end

    -- Models without a virtual rig (currently the Studio training dummy and any
    -- explicit root-fallback entity) use their queryable physical hitbox.
    for _, part in ipairs(Workspace:GetPartBoundsInBox(boxCFrame, boxSize, overlapParams(exclude))) do
        local entity = damageableModelFromPart(part)
        if entity and entity ~= exclude and not seen[entity] and entity:GetAttribute("Damageable") == true then
            if not EntityHitboxService.HasBinding(entity) then
                seen[entity] = true
                table.insert(results, {
                    model = entity,
                    hit = {
                        hitZone = "body",
                        damageMultiplier = 1,
                        boneName = part.Name,
                        role = "root_fallback",
                        radius = 0,
                        hitPosition = part.Position,
                    },
                    mode = "root_fallback",
                    part = part,
                })
            end
        end
    end

    return results
end

function EntityHitboxService.Start()
    if started then
        return
    end
    started = true
    -- No Heartbeat connection and no queryable proxy Parts. Bone regions are
    -- evaluated directly at the exact combat query time, so there is nothing
    -- server-replicated that can visually trail the client-owned character.
    print("[game1][hitbox] virtual bone-region combat queries ready")
end

return table.freeze(EntityHitboxService)
