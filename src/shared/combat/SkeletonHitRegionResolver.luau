local SkeletonHitRegionResolver = {}

-- Hit regions are semantic and virtual. We intentionally do not match body parts
-- with loose substrings: e.g. "forehead" must never become a "head" segment.
local MAX_GENERIC_POSE_SEGMENTS = 20
local SIDE_TOKENS = {
    l = true,
    r = true,
    left = true,
    right = true,
}
local GENERIC_EXCLUDED_TOKENS = {
    nub = true,
    finger = true,
    thumb = true,
    index = true,
    middle = true,
    ring = true,
    pinky = true,
    palm = true,
    ponytail = true,
    toe = true,
    heel = true,
    weapon = true,
    shield = true,
    breast = true,
    brow = true,
    forehead = true,
    lid = true,
    eye = true,
    ear = true,
    nose = true,
    lip = true,
    jaw = true,
    chin = true,
    cheek = true,
    tongue = true,
    teeth = true,
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

local function boneTokens(name: string): { string }
    local normalized = string.lower(name):gsub("[%._%-]+", " ")
    local result = {}
    for token in string.gmatch(normalized, "[%w]+") do
        if tonumber(token) == nil and SIDE_TOKENS[token] ~= true then
            table.insert(result, token)
        end
    end
    return result
end

local function hasToken(tokens: { string }, wanted: string): boolean
    for _, token in tokens do
        if token == wanted then
            return true
        end
    end
    return false
end

local function hasPair(tokens: { string }, first: string, second: string): boolean
    for index = 1, #tokens - 1 do
        if tokens[index] == first and tokens[index + 1] == second then
            return true
        end
    end
    return false
end

local function semanticRole(name: string): string?
    local tokens = boneTokens(name)

    -- Exact tokens/sequences only. This is the important distinction from the
    -- old substring resolver where "forehead" matched "head".
    if hasToken(tokens, "spine") then
        return "spine"
    elseif hasToken(tokens, "neck") then
        return "neck"
    elseif hasToken(tokens, "head") or hasToken(tokens, "face") then
        return "head"
    elseif hasToken(tokens, "clavicle") or hasToken(tokens, "shoulder") then
        return "shoulder"
    elseif hasToken(tokens, "upperarm") or hasPair(tokens, "upper", "arm") then
        return "upper_arm"
    elseif hasToken(tokens, "forearm") or hasPair(tokens, "lower", "arm") then
        return "forearm"
    elseif hasToken(tokens, "hand") then
        return "hand"
    elseif hasToken(tokens, "thigh") or hasPair(tokens, "upper", "leg") then
        return "thigh"
    elseif hasToken(tokens, "shin") or hasToken(tokens, "calf") or hasPair(tokens, "lower", "leg") then
        return "shin"
    elseif hasToken(tokens, "foot") then
        return "foot"
    end
    return nil
end

local function isGenericExcluded(name: string): boolean
    for _, token in boneTokens(name) do
        if GENERIC_EXCLUDED_TOKENS[token] == true then
            return true
        end
    end
    return false
end

local function segmentRadius(role: string, length: number, skeletonHeight: number): number
    -- Scale all widths from the actual skeleton height instead of fixed stud
    -- minima. Fixed 0.58/0.98 radii were visibly too fat on smaller imported rigs.
    local height = math.max(0.1, skeletonHeight)
    local ratio = 0.035
    if role == "spine" then
        ratio = 0.075
    elseif role == "neck" then
        ratio = 0.045
    elseif role == "shoulder" then
        ratio = 0.050
    elseif role == "upper_arm" then
        ratio = 0.040
    elseif role == "forearm" then
        ratio = 0.034
    elseif role == "hand" then
        ratio = 0.038
    elseif role == "thigh" then
        ratio = 0.052
    elseif role == "shin" then
        ratio = 0.040
    elseif role == "foot" then
        ratio = 0.040
    end

    local byHeight = height * ratio
    -- Keep pathological rigs bounded without imposing a large universal minimum.
    local byLengthCap = math.max(0.08, length * 0.42)
    return math.clamp(math.min(byHeight, byLengthCap), 0.08, height * 0.10)
end

function SkeletonHitRegionResolver.Resolve(visual: Model): any
    local candidates = {}
    local preferred = {}
    local headBone: Bone? = nil
    local minBoneY = math.huge
    local maxBoneY = -math.huge

    for _, descendant in visual:GetDescendants() do
        if descendant:IsA("Bone") then
            local position = transformedBoneFrame(descendant).Position
            minBoneY = math.min(minBoneY, position.Y)
            maxBoneY = math.max(maxBoneY, position.Y)

            local role = semanticRole(descendant.Name)
            if role == "head" and headBone == nil then
                headBone = descendant
            end

            if descendant.Parent and descendant.Parent:IsA("Bone") then
                local parentBone = descendant.Parent :: Bone
                local length = (position - transformedBoneFrame(parentBone).Position).Magnitude
                if length > 0.04 and not isGenericExcluded(descendant.Name) then
                    local candidate = {
                        bone = descendant,
                        parentBone = parentBone,
                        length = length,
                        role = role,
                    }
                    table.insert(candidates, candidate)
                    if role ~= nil and role ~= "head" then
                        table.insert(preferred, candidate)
                    end
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
            local candidate = candidates[index]
            candidate.role = candidate.role or "generic"
            table.insert(selected, candidate)
        end
    end

    local skeletonHeight = if minBoneY < math.huge and maxBoneY > -math.huge
        then math.max(0.1, maxBoneY - minBoneY)
        else 1

    return {
        segments = selected,
        headBone = headBone,
        skeletonHeight = skeletonHeight,
        boneCount = #candidates,
    }
end

function SkeletonHitRegionResolver.TransformedBoneFrame(bone: Bone): CFrame
    return transformedBoneFrame(bone)
end

function SkeletonHitRegionResolver.SegmentRadius(role: string, length: number, skeletonHeight: number): number
    return segmentRadius(role, length, skeletonHeight)
end

function SkeletonHitRegionResolver.HeadRadius(skeletonHeight: number): number
    return math.clamp(math.max(0.1, skeletonHeight) * 0.085, 0.22, 0.72)
end

function SkeletonHitRegionResolver.SemanticRole(name: string): string?
    return semanticRole(name)
end

return table.freeze(SkeletonHitRegionResolver)
