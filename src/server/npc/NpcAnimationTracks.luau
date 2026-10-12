-- Animation registry adapter: loading, priority, playback speed and runtime seam.
-- Does not decide which animation to play or when to transition actor state.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local AnimationShared = Shared:WaitForChild("animation")
local NpcConfig = require(Shared:WaitForChild("npc"):WaitForChild("NpcAnimationConfig"))
local AnimationSpeedScaling = require(AnimationShared:WaitForChild("AnimationSpeedScaling"))
local AnimationFirstFrameSeam = require(AnimationShared:WaitForChild("AnimationFirstFrameSeam"))

local NpcAnimationTracks = {}

local priorities = {
    Idle = Enum.AnimationPriority.Idle,
    Movement = Enum.AnimationPriority.Movement,
    Action = Enum.AnimationPriority.Action,
    Action2 = Enum.AnimationPriority.Action2,
    Action3 = Enum.AnimationPriority.Action3,
    Action4 = Enum.AnimationPriority.Action4,
}

function NpcAnimationTracks.PublishedRows(profile: any?, slot: string): {any}
    local slots = profile and profile.slots
    local rows = slots and slots[slot]
    local result = {}
    if typeof(rows) ~= "table" then
        return result
    end
    for _, row in ipairs(rows) do
        if tostring(row.weaponSet or NpcConfig.WeaponSet) == NpcConfig.WeaponSet
            and tostring(row.animationId or ""):match("^rbxassetid://%d+$") then
            table.insert(result, row)
        end
    end
    return result
end

local function load(animator: Animator, animationId: string): AnimationTrack?
    local animation = Instance.new("Animation")
    animation.AnimationId = animationId
    local success, result = pcall(function()
        return animator:LoadAnimation(animation)
    end)
    animation:Destroy()
    if not success then
        warn("[game1][npc] animation load failed: " .. tostring(result))
        return nil
    end
    return result :: AnimationTrack
end

function NpcAnimationTracks.Load(animator: Animator, row: any?, looped: boolean, allowSeam: boolean?): any?
    if not row then
        return nil
    end
    local animationId = tostring(row.animationId)
    local track = load(animator, animationId)
    if not track then
        return nil
    end
    track.Looped = looped
    track.Priority = priorities[tostring(row.priority or "")] or (if looped then Enum.AnimationPriority.Idle else Enum.AnimationPriority.Action)
    local seam = nil
    if row.duplicateFirstFrameAtEnd == true and allowSeam ~= false then
        local companion = load(animator, animationId)
        if companion then
            companion.Priority = track.Priority
            seam = AnimationFirstFrameSeam.new(track, companion, looped)
        end
    end
    return { row = row, track = track, seam = seam }
end

function NpcAnimationTracks.Play(entity: Model, clip: any?, channel: string, fade: number?): boolean
    if not clip then
        return false
    end
    local percent = AnimationSpeedScaling.ResolveForModel(entity, channel)
    entity:SetAttribute("AnimationPlaybackSpeedPercent", percent)
    local speed = percent / 100
    local success, failure = pcall(function()
        if clip.seam then
            clip.seam:Play(fade or NpcConfig.TransitionSeconds, speed)
        elseif clip.track.IsPlaying then
            clip.track:AdjustSpeed(speed)
        else
            clip.track:Play(fade or NpcConfig.TransitionSeconds, 1, speed)
        end
    end)
    if not success then
        warn("[game1][npc] animation playback failed: " .. tostring(failure))
        return false
    end
    -- The presentation uses the same speed to schedule one-shot crossfades.
    clip.playbackSpeed = speed
    return true
end

-- Seconds remaining on an active one-shot at the exact playback speed chosen by Play.
-- nil means that Roblox has not resolved the asset length or the track has stopped.
function NpcAnimationTracks.SecondsRemaining(clip: any?): number?
    if not clip or not clip.track or not clip.track.IsPlaying then
        return nil
    end
    local length = tonumber(clip.track.Length) or 0
    if length <= 0 then
        return nil
    end
    local position = tonumber(clip.track.TimePosition) or 0
    local speed = math.max(0.01, tonumber(clip.playbackSpeed) or 1)
    return math.max(0, length - position) / speed
end

function NpcAnimationTracks.Stop(clip: any?, fade: number?)
    if not clip then
        return
    end
    local success, failure = pcall(function()
        if clip.seam then
            clip.seam:Stop(fade or NpcConfig.TransitionSeconds)
        elseif clip.track.IsPlaying then
            clip.track:Stop(fade or NpcConfig.TransitionSeconds)
        end
    end)
    if not success then
        warn("[game1][npc] animation stop failed: " .. tostring(failure))
    end
end

function NpcAnimationTracks.Step(clip: any?, delta: number): (boolean, boolean)
    if clip and clip.seam then
        return clip.seam:Step(delta)
    end
    return false, false
end

return table.freeze(NpcAnimationTracks)
