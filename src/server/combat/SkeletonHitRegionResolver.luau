local SkeletonHitRegionResolver = {}

local MAX_GENERIC_POSE_SEGMENTS = 32
local POSE_BONE_MARKERS = {
    "spine", "neck", "head", "clavicle", "upperarm", "forearm", "hand", "thigh", "calf", "foot",
}

local function transformedBoneFrame(bone: Bone): CFrame
    local ok, frame = pcall(function()
        return bone.TransformedWorldCFrame
    end)
    if ok and typeof(frame) == "CFrame" then
        return frame
    end
    return bone.WorldCFrame
end

local function normalizedBoneName(name: string): string
    return string.lower(name)
end

local function isExcludedHelperBone(name: string): boolean
    local normalized = normalizedBoneName(name)
    return string.find(normalized, "nub", 1, true) ~= nil
        or string.find(normalized, "finger", 1, true) ~= nil
        or string.find(normalized, "ponytail", 1, true) ~= nil
        or string.find(normalized, "toe", 1, true) ~= nil
end

local function isPoseBone(name: string): boolean
    if isExcludedHelperBone(name) then
        return false
    end
    local normalized = normalizedBoneName(name)
    for _, marker in POSE_BONE_MARKERS do
        if string.find(normalized, marker, 1, true) then
            return true
        end
    end
    return false
end

local function isHeadBone(name: string): boolean
    local normalized = normalizedBoneName(name)
    return string.find(normalized, "head", 1, true) ~= nil
        and string.find(normalized, "nub", 1, true) == nil
end

local function headTipBone(headBone: Bone): Bone?
    local best: Bone? = nil
    local bestDistance = 0
    local headPosition = transformedBoneFrame(headBone).Position
    for _, child in headBone:GetChildren() do
        if child:IsA("Bone") then
            local normalized = normalizedBoneName(child.Name)
            local semanticTip = string.find(normalized, "nub", 1, true) ~= nil
                or string.find(normalized, "head", 1, true) ~= nil
            if semanticTip then
                local distance = (transformedBoneFrame(child).Position - headPosition).Magnitude
                if distance > bestDistance then
                    best = child
                    bestDistance = distance
                end
            end
        end
    end
    return best
end

local function segmentRadius(name: string, length: number): number
    local normalized = normalizedBoneName(name)
    if string.find(normalized, "spine", 1, true) then
        return math.clamp(math.max(0.58, length * 0.58), 0.58, 0.98)
    elseif string.find(normalized, "clavicle", 1, true) then
        return math.clamp(math.max(0.34, length * 0.3), 0.34, 0.5)
    elseif string.find(normalized, "thigh", 1, true) then
        return math.clamp(math.max(0.35, length * 0.26), 0.35, 0.55)
    elseif string.find(normalized, "upperarm", 1, true) then
        return math.clamp(math.max(0.29, length * 0.24), 0.29, 0.46)
    elseif string.find(normalized, "calf", 1, true) or string.find(normalized, "forearm", 1, true) then
        return math.clamp(math.max(0.24, length * 0.21), 0.24, 0.4)
    elseif string.find(normalized, "hand", 1, true) or string.find(normalized, "foot", 1, true) then
        return math.clamp(math.max(0.23, length * 0.2), 0.23, 0.36)
    elseif string.find(normalized, "neck", 1, true) then
        return math.clamp(math.max(0.32, length * 0.3), 0.32, 0.46)
    end
    return math.clamp(math.max(0.23, length * 0.2), 0.23, 0.42)
end

function SkeletonHitRegionResolver.Resolve(visual: Model): any
    local candidates = {}
    local preferred = {}
    local headBone: Bone? = nil
    local minBoneY = math.huge
    local maxBoneY = -math.huge

    for _, descendant in visual:GetDescendants() do
        if descendant:IsA("Bone") then
            local y = transformedBoneFrame(descendant).Position.Y
            minBoneY = math.min(minBoneY, y)
            maxBoneY = math.max(maxBoneY, y)
        end
        if descendant:IsA("Bone") and descendant.Parent and descendant.Parent:IsA("Bone") then
            local parentBone = descendant.Parent :: Bone
            local length = (transformedBoneFrame(descendant).Position - transformedBoneFrame(parentBone).Position).Magnitude
            if length > 0.08 then
                local candidate = { bone = descendant, parentBone = parentBone, length = length }
                table.insert(candidates, candidate)
                if isPoseBone(descendant.Name) then
                    table.insert(preferred, candidate)
                end
                if isHeadBone(descendant.Name) then
                    headBone = descendant
                end
            end
        end
    end

    local selected = preferred
    if #selected < 5 then
        table.sort(candidates, function(left, right)
            return left.length > right.length
        end)
        selected = {}
        for index = 1, math.min(#candidates, MAX_GENERIC_POSE_SEGMENTS) do
            table.insert(selected, candidates[index])
        end
    end

    return {
        segments = selected,
        headBone = headBone,
        headTipBone = headBone and headTipBone(headBone) or nil,
        skeletonHeight = if minBoneY < math.huge and maxBoneY > -math.huge then math.max(0, maxBoneY - minBoneY) else 0,
        boneCount = #candidates,
    }
end

function SkeletonHitRegionResolver.TransformedBoneFrame(bone: Bone): CFrame
    return transformedBoneFrame(bone)
end

function SkeletonHitRegionResolver.SegmentRadius(name: string, length: number): number
    return segmentRadius(name, length)
end

return table.freeze(SkeletonHitRegionResolver)
