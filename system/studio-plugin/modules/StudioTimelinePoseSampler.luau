-- Offline pose extraction and interpolation for a preview rig. No UI or HTTP dependencies.
local StudioTimelinePoseSampler = {}

function StudioTimelinePoseSampler.new(TweenService)
    local function addTimelineTarget(targetMap: any, name: string, target: Instance)
        if name == "" then
            return
        end
        local bucket = targetMap[name]
        if bucket == nil then
            bucket = {}
            targetMap[name] = bucket
        end
        if table.find(bucket, target) == nil then
            table.insert(bucket, target)
        end
    end

    local function collectTimelineTargets(preview: Model): any
        local targetMap = {}
        for _, descendant in ipairs(preview:GetDescendants()) do
            if descendant:IsA("Bone") then
                addTimelineTarget(targetMap, descendant.Name, descendant)
            elseif descendant:IsA("Motor6D") then
                addTimelineTarget(targetMap, descendant.Name, descendant)
                if descendant.Part1 ~= nil then
                    addTimelineTarget(targetMap, descendant.Part1.Name, descendant)
                end
            end
        end
        return targetMap
    end

    local function timelineTargetTransform(target: Instance): CFrame
        if target:IsA("Bone") or target:IsA("Motor6D") then
            return target.Transform
        end
        return CFrame.new()
    end

    local function setTimelineTargetTransform(target: Instance, transform: CFrame)
        if target:IsA("Bone") or target:IsA("Motor6D") then
            target.Transform = transform
        end
    end

    local function timelinePoseTarget(pose: Pose, targetMap: any): Instance?
        local bucket = targetMap[pose.Name]
        if bucket == nil or #bucket == 0 then
            return nil
        end
        if #bucket == 1 then
            return bucket[1]
        end
        local parentPose = pose.Parent
        if parentPose and parentPose:IsA("Pose") then
            for _, candidate in ipairs(bucket) do
                if candidate:IsA("Bone") then
                    local candidateParent = candidate.Parent
                    if candidateParent and candidateParent.Name == parentPose.Name then
                        return candidate
                    end
                elseif candidate:IsA("Motor6D") and candidate.Part0 and candidate.Part0.Name == parentPose.Name then
                    return candidate
                end
            end
        end
        return bucket[1]
    end

    local function buildTimelinePoseTracks(preview: Model, sequence: KeyframeSequence): any
        local targetMap = collectTimelineTargets(preview)
        local tracksByTarget = {}
        local keyframes = sequence:GetKeyframes()
        table.sort(keyframes, function(a, b)
            return a.Time < b.Time
        end)
        for _, keyframe in ipairs(keyframes) do
            for _, descendant in ipairs(keyframe:GetDescendants()) do
                if descendant:IsA("Pose") then
                    local target = timelinePoseTarget(descendant, targetMap)
                    if target ~= nil then
                        local track = tracksByTarget[target]
                        if track == nil then
                            track = {
                                target = target,
                                defaultTransform = timelineTargetTransform(target),
                                samples = {},
                            }
                            tracksByTarget[target] = track
                        end
                        table.insert(track.samples, {
                            time = keyframe.Time,
                            cframe = descendant.CFrame,
                            style = descendant.EasingStyle.Name,
                            direction = descendant.EasingDirection.Name,
                        })
                    end
                end
            end
        end
        local tracks = {}
        for _, track in pairs(tracksByTarget) do
            table.sort(track.samples, function(a, b)
                return a.time < b.time
            end)
            table.insert(tracks, track)
        end
        return tracks
    end

    local easingStyles = {}
    for _, item in ipairs(Enum.EasingStyle:GetEnumItems()) do
        easingStyles[item.Name] = item
    end
    local easingDirections = {}
    for _, item in ipairs(Enum.EasingDirection:GetEnumItems()) do
        easingDirections[item.Name] = item
    end

    local function timelineEasingAlpha(alpha: number, styleName: string, directionName: string): number
        alpha = math.clamp(alpha, 0, 1)
        if styleName == "Constant" then
            return if alpha >= 1 then 1 else 0
        end
        local style = easingStyles[styleName] or Enum.EasingStyle.Linear
        local direction = easingDirections[directionName] or Enum.EasingDirection.Out
        local ok, value = pcall(function()
            return TweenService:GetValue(alpha, style, direction)
        end)
        return if ok then value else alpha
    end

    local function sampleTimelineTrack(track: any, timePosition: number): CFrame
        local samples = track.samples
        if #samples == 0 then
            return track.defaultTransform
        end
        if timePosition <= samples[1].time then
            if samples[1].time <= 0.0005 then
                return samples[1].cframe
            end
            local alpha = timelineEasingAlpha(timePosition / samples[1].time, "Linear", "Out")
            return track.defaultTransform:Lerp(samples[1].cframe, alpha)
        end
        for index = 1, #samples - 1 do
            local current = samples[index]
            local following = samples[index + 1]
            if timePosition <= following.time then
                local span = math.max(following.time - current.time, 0.000001)
                local alpha = timelineEasingAlpha((timePosition - current.time) / span, current.style, current.direction)
                return current.cframe:Lerp(following.cframe, alpha)
            end
        end
        return samples[#samples].cframe
    end

    local function applyTimelinePose(poseTracks: any, timePosition: number)
        for _, track in ipairs(poseTracks) do
            if track.target.Parent ~= nil then
                setTimelineTargetTransform(track.target, sampleTimelineTrack(track, timePosition))
            end
        end
    end


    return {
        Build = buildTimelinePoseTracks,
        Apply = applyTimelinePose,
    }
end

return table.freeze(StudioTimelinePoseSampler)
