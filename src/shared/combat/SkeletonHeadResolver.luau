local SkeletonHeadResolver = {}

local SIDE_TOKENS = {
    l = true,
    r = true,
    left = true,
    right = true,
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

local function isHeadBoneName(name: string): boolean
    for _, token in ipairs(boneTokens(name)) do
        if token == "head" or token == "face" then
            return true
        end
    end
    return false
end

function SkeletonHeadResolver.Resolve(visual: Model): any
    for _, descendant in ipairs(visual:GetDescendants()) do
        if descendant:IsA("Bone") and isHeadBoneName(descendant.Name) then
            local parent = descendant.Parent
            return {
                headBone = descendant,
                headParentBone = if parent and parent:IsA("Bone") then parent else nil,
            }
        end
    end
    return {
        headBone = nil,
        headParentBone = nil,
    }
end

function SkeletonHeadResolver.TransformedBoneFrame(bone: Bone): CFrame
    return transformedBoneFrame(bone)
end

return table.freeze(SkeletonHeadResolver)
