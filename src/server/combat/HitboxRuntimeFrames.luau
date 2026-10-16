-- Cached runtime transforms of bone-local hitboxes, one update per frame.
-- The authoritative frame serial belongs to EntityHitboxService.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local SkeletonHeadResolver = require(Shared:WaitForChild("combat"):WaitForChild("SkeletonHeadResolver"))

local HitboxRuntimeFrames = {}
local function transformedBoneFrame(bone: Bone): CFrame
    return SkeletonHeadResolver.TransformedBoneFrame(bone)
end

local function boxAnchorFrame(anchor: Instance): CFrame?
    if anchor:IsA("Bone") then
        return transformedBoneFrame(anchor)
    elseif anchor:IsA("BasePart") then
        return anchor.CFrame
    end
    return nil
end

function HitboxRuntimeFrames.Refresh(binding: any, frameSerial: number)
    if binding.worldFrameSerial == frameSerial then
        return
    end
    binding.worldFrameSerial = frameSerial

    if binding.headBox then
        local anchorFrame = boxAnchorFrame(binding.headBox.anchor)
        binding.worldHeadCFrame = anchorFrame and (anchorFrame * binding.headBox.localCFrame) or nil
    else
        binding.worldHeadCFrame = nil
    end

    local frames = binding.worldBodyCFrames
    table.clear(frames)
    for index, box in ipairs(binding.bodyBoxes) do
        local anchorFrame = boxAnchorFrame(box.anchor)
        frames[index] = anchorFrame and (anchorFrame * box.localCFrame) or nil
    end
end

return table.freeze(HitboxRuntimeFrames)
