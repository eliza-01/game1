-- Offline, one complete authored keyframe. No Animator, guessing rest pose,
-- ambiguous target mapping, or easing approximation at an unkeyed time.
local Preview = require(script.Parent.StudioTimelinePreview)
local Sampler = require(script.Parent.StudioTimelinePoseSampler)
local IdlePose = {}

function IdlePose.Apply(visual: Model, sequence: KeyframeSequence, phase: number): any
    local duration = Preview.SequenceDuration(sequence)
    assert(duration > 0, "MNPC idle clip has no duration")
    local names = {}
    for _, node in visual:GetDescendants() do
        if node:IsA("Bone") or node:IsA("Motor6D") then
            local bucket = names[node.Name] or {}
            table.insert(bucket, node)
            names[node.Name] = bucket
        end
    end
    local frames = sequence:GetKeyframes()
    assert(#frames <= 1200, "MNPC idle has too many keyframes")
    local poseCount = 0
    for _, keyframe in frames do
        local seen = {}
        for _, pose in keyframe:GetDescendants() do
            if pose:IsA("Pose") then
                poseCount += 1
                assert(poseCount <= 200000, "MNPC idle pose budget exceeded")
                local targets = names[pose.Name]
                if targets then
                    assert(#targets == 1 and targets[1]:IsA("Bone"), "MNPC idle target ambiguous/unsupported: " .. pose.Name)
                    local target = targets[1]
                    assert(not seen[target], "MNPC duplicate idle target: " .. pose.Name)
                    seen[target] = true
                    local parent = pose.Parent
                    if parent and parent:IsA("Pose") and names[parent.Name] then
                        assert(target.Parent == names[parent.Name][1], "MNPC idle hierarchy mismatch: " .. pose.Name)
                    end
                    local _, angle = pose.CFrame:ToAxisAngle()
                    local neutral = pose.CFrame.Position.Magnitude <= 0.00001 and math.abs(angle) <= 0.00001
                    assert(math.abs(pose.Weight - 1) <= 0.0001 or (neutral and math.abs(pose.Weight) <= 0.0001),
                        "MNPC weighted moving pose is unsupported: " .. pose.Name)
                else
                    -- Neutral synthetic hierarchy nodes may wrap the real bone
                    -- tracks; never ignore an unmatched moving target.
                    local _, angle = pose.CFrame:ToAxisAngle()
                    assert(pose.CFrame.Position.Magnitude <= 0.00001 and math.abs(angle) <= 0.00001,
                        "MNPC idle moving target not found: " .. pose.Name)
                end
            end
        end
    end
    local sampler = Sampler.new(game:GetService("TweenService"))
    local tracks = sampler.Build(visual, sequence)
    assert(#tracks > 0 and #tracks <= 512, "MNPC idle has no supported bone tracks")
    -- Intersect actual sample timestamps, then pick the nearest to requested
    -- phase. At this time the existing sampler returns authored CFrames.
    local common = {}
    for _, sample in tracks[1].samples do
        assert(not common[sample.time], "MNPC duplicate keyframe time")
        common[sample.time] = true
    end
    for _, track in tracks do
        assert(track.target:IsA("Bone"), "MNPC only supports bone idle tracks")
        local times = {}
        for _, sample in track.samples do
            assert(not times[sample.time], "MNPC duplicate keyframe time")
            times[sample.time] = true
        end
        for time in pairs(common) do
            if not times[time] then common[time] = nil end
        end
    end
    local selected, distance = nil, math.huge
    for time in pairs(common) do
        local delta = math.abs(time - duration * phase)
        if time > 0 and (delta < distance or (delta == distance and (selected == nil or time < selected))) then
            selected, distance = time, delta
        end
    end
    assert(selected ~= nil, "MNPC idle has no complete nonzero authored keyframe")
    -- Apply the exact values, including Constant easing and sparse tracks.
    -- Do not interpolate: the engine's native blend/easing is not assumed.
    for _, track in tracks do
        for _, sample in track.samples do
            if sample.time == selected then
                track.target.Transform = sample.cframe
                break
            end
        end
    end
    return {mode = "authored_keyframe", duration = duration, time = selected, animatedBones = #tracks}
end

return table.freeze(IdlePose)
