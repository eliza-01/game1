-- Exact OBB / ray tests for precomputed hitboxes. No entity registry,
-- networking, damage, or EditableMesh access.
local HitboxRuntimeFrames = require(script.Parent:WaitForChild("HitboxRuntimeFrames"))
local HitboxSpatialQueries = {}
local SAT_EPSILON = 1e-6

local function obbIntersects(aFrame: CFrame, aSize: Vector3, bFrame: CFrame, bSize: Vector3): boolean
    local a0 = aFrame.RightVector
    local a1 = aFrame.UpVector
    local a2 = -aFrame.LookVector
    local b0 = bFrame.RightVector
    local b1 = bFrame.UpVector
    local b2 = -bFrame.LookVector

    local ah0, ah1, ah2 = aSize.X * 0.5, aSize.Y * 0.5, aSize.Z * 0.5
    local bh0, bh1, bh2 = bSize.X * 0.5, bSize.Y * 0.5, bSize.Z * 0.5

    local r00, r01, r02 = a0:Dot(b0), a0:Dot(b1), a0:Dot(b2)
    local r10, r11, r12 = a1:Dot(b0), a1:Dot(b1), a1:Dot(b2)
    local r20, r21, r22 = a2:Dot(b0), a2:Dot(b1), a2:Dot(b2)
    local ar00, ar01, ar02 = math.abs(r00) + SAT_EPSILON, math.abs(r01) + SAT_EPSILON, math.abs(r02) + SAT_EPSILON
    local ar10, ar11, ar12 = math.abs(r10) + SAT_EPSILON, math.abs(r11) + SAT_EPSILON, math.abs(r12) + SAT_EPSILON
    local ar20, ar21, ar22 = math.abs(r20) + SAT_EPSILON, math.abs(r21) + SAT_EPSILON, math.abs(r22) + SAT_EPSILON

    local delta = bFrame.Position - aFrame.Position
    local t0, t1, t2 = delta:Dot(a0), delta:Dot(a1), delta:Dot(a2)

    if math.abs(t0) > ah0 + bh0 * ar00 + bh1 * ar01 + bh2 * ar02 then return false end
    if math.abs(t1) > ah1 + bh0 * ar10 + bh1 * ar11 + bh2 * ar12 then return false end
    if math.abs(t2) > ah2 + bh0 * ar20 + bh1 * ar21 + bh2 * ar22 then return false end

    if math.abs(t0 * r00 + t1 * r10 + t2 * r20) > ah0 * ar00 + ah1 * ar10 + ah2 * ar20 + bh0 then return false end
    if math.abs(t0 * r01 + t1 * r11 + t2 * r21) > ah0 * ar01 + ah1 * ar11 + ah2 * ar21 + bh1 then return false end
    if math.abs(t0 * r02 + t1 * r12 + t2 * r22) > ah0 * ar02 + ah1 * ar12 + ah2 * ar22 + bh2 then return false end

    if math.abs(t2 * r10 - t1 * r20) > ah1 * ar20 + ah2 * ar10 + bh1 * ar02 + bh2 * ar01 then return false end
    if math.abs(t2 * r11 - t1 * r21) > ah1 * ar21 + ah2 * ar11 + bh0 * ar02 + bh2 * ar00 then return false end
    if math.abs(t2 * r12 - t1 * r22) > ah1 * ar22 + ah2 * ar12 + bh0 * ar01 + bh1 * ar00 then return false end

    if math.abs(t0 * r20 - t2 * r00) > ah0 * ar20 + ah2 * ar00 + bh1 * ar12 + bh2 * ar11 then return false end
    if math.abs(t0 * r21 - t2 * r01) > ah0 * ar21 + ah2 * ar01 + bh0 * ar12 + bh2 * ar10 then return false end
    if math.abs(t0 * r22 - t2 * r02) > ah0 * ar22 + ah2 * ar02 + bh0 * ar11 + bh1 * ar10 then return false end

    if math.abs(t1 * r00 - t0 * r10) > ah0 * ar10 + ah1 * ar00 + bh1 * ar22 + bh2 * ar21 then return false end
    if math.abs(t1 * r01 - t0 * r11) > ah0 * ar11 + ah1 * ar01 + bh0 * ar22 + bh2 * ar20 then return false end
    if math.abs(t1 * r02 - t0 * r12) > ah0 * ar12 + ah1 * ar02 + bh0 * ar21 + bh1 * ar20 then return false end

    return true
end

local function sphereIntersectsBox(center: Vector3, radius: number, boxCFrame: CFrame, boxSize: Vector3): boolean
    local localCenter = boxCFrame:PointToObjectSpace(center)
    local half = boxSize * 0.5
    local closest = Vector3.new(
        math.clamp(localCenter.X, -half.X, half.X),
        math.clamp(localCenter.Y, -half.Y, half.Y),
        math.clamp(localCenter.Z, -half.Z, half.Z)
    )
    return (localCenter - closest).Magnitude <= radius
end

local function closestPointOnBox(boxCFrame: CFrame, boxSize: Vector3, worldPoint: Vector3): Vector3
    local localPoint = boxCFrame:PointToObjectSpace(worldPoint)
    local half = boxSize * 0.5
    return boxCFrame:PointToWorldSpace(Vector3.new(
        math.clamp(localPoint.X, -half.X, half.X),
        math.clamp(localPoint.Y, -half.Y, half.Y),
        math.clamp(localPoint.Z, -half.Z, half.Z)
    ))
end

function HitboxSpatialQueries.BoxContact(binding: any, weaponCFrame: CFrame, weaponSize: Vector3, originPosition: Vector3?, frameSerial: number): any?
    if not sphereIntersectsBox(binding.root.Position, binding.definition.broadRadius, weaponCFrame, weaponSize) then
        return nil
    end
    HitboxRuntimeFrames.Refresh(binding, frameSerial)

    if binding.headBox and binding.worldHeadCFrame
        and obbIntersects(weaponCFrame, weaponSize, binding.worldHeadCFrame, binding.headBox.size)
    then
        local hitPosition = closestPointOnBox(binding.worldHeadCFrame, binding.headBox.size, weaponCFrame.Position)
        return {
            boneName = binding.headBone and binding.headBone.Name or "",
            geometryRole = "head",
            hitPosition = hitPosition,
        }
    end

    local bestPosition = nil
    local bestDistance = math.huge
    local bestBoneName = ""
    for index, bodyBox in ipairs(binding.bodyBoxes) do
        local worldCFrame = binding.worldBodyCFrames[index]
        if worldCFrame and obbIntersects(weaponCFrame, weaponSize, worldCFrame, bodyBox.size) then
            local contact = closestPointOnBox(worldCFrame, bodyBox.size, weaponCFrame.Position)
            local distance = if typeof(originPosition) == "Vector3"
                then (contact - originPosition).Magnitude
                else (contact - weaponCFrame.Position).Magnitude
            if distance < bestDistance then
                bestDistance = distance
                bestPosition = contact
                bestBoneName = if bodyBox.anchor:IsA("Bone") then bodyBox.anchor.Name else ""
            end
        end
    end

    if not bestPosition then
        return nil
    end
    return {
        boneName = bestBoneName,
        geometryRole = "body",
        hitPosition = bestPosition,
    }
end

local function rayBoxDistance(
    rayOrigin: Vector3,
    rayDirection: Vector3,
    maxDistance: number,
    boxCFrame: CFrame,
    boxSize: Vector3
): number?
    local localOrigin = boxCFrame:PointToObjectSpace(rayOrigin)
    local localDirection = boxCFrame:VectorToObjectSpace(rayDirection)
    local half = boxSize * 0.5
    local tMin = 0
    local tMax = maxDistance

    local function clipAxis(originAxis: number, directionAxis: number, halfAxis: number): boolean
        if math.abs(directionAxis) <= 1e-8 then
            return math.abs(originAxis) <= halfAxis
        end
        local inverse = 1 / directionAxis
        local near = (-halfAxis - originAxis) * inverse
        local far = (halfAxis - originAxis) * inverse
        if near > far then
            near, far = far, near
        end
        tMin = math.max(tMin, near)
        tMax = math.min(tMax, far)
        return tMin <= tMax
    end

    if not clipAxis(localOrigin.X, localDirection.X, half.X)
        or not clipAxis(localOrigin.Y, localDirection.Y, half.Y)
        or not clipAxis(localOrigin.Z, localDirection.Z, half.Z)
    then
        return nil
    end
    return tMin
end

local function raySegmentNearSphere(
    rayOrigin: Vector3,
    rayDirection: Vector3,
    maxDistance: number,
    center: Vector3,
    radius: number
): boolean
    local along = math.clamp((center - rayOrigin):Dot(rayDirection), 0, maxDistance)
    local closest = rayOrigin + rayDirection * along
    return (center - closest).Magnitude <= radius
end

function HitboxSpatialQueries.AimContact(
    binding: any,
    rayOrigin: Vector3,
    rayDirection: Vector3,
    maxDistance: number,
    frameSerial: number
): any?
    if not raySegmentNearSphere(
        rayOrigin,
        rayDirection,
        maxDistance,
        binding.root.Position,
        binding.definition.broadRadius
    ) then
        return nil
    end

    HitboxRuntimeFrames.Refresh(binding, frameSerial)
    local bestDistance = math.huge
    local bestZone = nil
    local bestBoneName = ""

    -- Head is tested first and wins exact boundary ties. This does not deal
    -- damage by itself; it only classifies the first combat hitbox under the
    -- center-screen aim line.
    if binding.headBox and binding.worldHeadCFrame then
        local distance = rayBoxDistance(
            rayOrigin,
            rayDirection,
            maxDistance,
            binding.worldHeadCFrame,
            binding.headBox.size
        )
        if distance ~= nil then
            bestDistance = distance
            bestZone = "head"
            bestBoneName = binding.headBone and binding.headBone.Name or ""
        end
    end

    for index, bodyBox in ipairs(binding.bodyBoxes) do
        local worldCFrame = binding.worldBodyCFrames[index]
        if worldCFrame then
            local distance = rayBoxDistance(rayOrigin, rayDirection, maxDistance, worldCFrame, bodyBox.size)
            if distance ~= nil and distance < bestDistance - SAT_EPSILON then
                bestDistance = distance
                bestZone = "body"
                bestBoneName = if bodyBox.anchor:IsA("Bone") then bodyBox.anchor.Name else ""
            end
        end
    end

    if not bestZone then
        return nil
    end
    return {
        zone = bestZone,
        boneName = bestBoneName,
        distance = bestDistance,
        hitPosition = rayOrigin + rayDirection * bestDistance,
    }
end

return table.freeze(HitboxSpatialQueries)
