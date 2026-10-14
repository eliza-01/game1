-- Animation registry adapter: loading, priority, playback speed.
-- Does not decide which animation to play or when to transition actor state.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local AnimationShared = Shared:WaitForChild("animation")
local NpcConfig = require(Shared:WaitForChild("npc"):WaitForChild("NpcAnimationConfig"))
local AnimationSpeedScaling = require(AnimationShared:WaitForChild("AnimationSpeedScaling"))

local NpcAnimationTracks = {}

local priorities = {
    Idle = Enum.AnimationPriority.Idle,
    Movement = Enum.AnimationPriority.Movement,
    Action = Enum.AnimationPriority.Action,
    Action2 = Enum.AnimationPriority.Action2,
    Action3 = Enum.AnimationPriority.Action3,
    Action4 = Enum.AnimationPriority.Action4,
}

local Compatibility = require(AnimationShared:WaitForChild("AnimationCompatibility"))

function NpcAnimationTracks.PublishedRows(profile: any?, slot: string, weaponSet: string?): {any}
    local slots = profile and profile.slots
    local rows = slots and slots[slot]
    if typeof(rows) ~= "table" then return {} end
    local activeSet = tostring(weaponSet or "unarmed")
    local valid = {}
    for _, row in ipairs(rows) do
        if tostring(row.animationId or ""):match("^rbxassetid://%d+$")
            and Compatibility.Allowed(row, activeSet) then
            table.insert(valid, row)
        end
    end
    table.sort(valid, function(a, b)
        local rankA = Compatibility.Rank(a, activeSet)
        local rankB = Compatibility.Rank(b, activeSet)
        if rankA ~= rankB then return rankA < rankB end
        return tostring(a.clipId or a.animationId) < tostring(b.clipId or b.animationId)
    end)
    if slot == "idle" then
        -- A single preferred stance, plus all compatible weighted specials.
        local result = {}
        local baseFound = false
        for _, row in ipairs(valid) do
            if row.role == "special" or row.sourceSlot == "idle_special" then
                table.insert(result, row)
            elseif not baseFound then
                table.insert(result, 1, row)
                baseFound = true
            end
        end
        return result
    end
    if slot == "death" then
        -- Terminal state prefers an authored reusable base death.
        for _, row in ipairs(valid) do
            if row.weaponSet == "base" then return {row} end
        end
    end
    if #valid == 0 then return {} end
    -- Stance/actions pick a single matching subtype family before cross-type
    -- fallback. Variant attacks within that family retain weighted selection.
    local firstRank = Compatibility.Rank(valid[1], activeSet)
    local result = {}
    for _, row in ipairs(valid) do
        if Compatibility.Rank(row, activeSet) == firstRank then
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

function NpcAnimationTracks.Load(animator: Animator, row: any?, looped: boolean): any?
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
    return { row = row, track = track }
end

function NpcAnimationTracks.Play(entity: Model, clip: any?, channel: string, fade: number?, speedPercentOverride: number?): boolean
    if not clip then
        return false
    end
    local _, isCustom = AnimationSpeedScaling.RuleForAnimation(entity, channel, clip.row and clip.row.animationId)
    local percent = if isCustom
        then AnimationSpeedScaling.ResolveForAnimation(entity, channel, clip.row and clip.row.animationId)
        else (speedPercentOverride or AnimationSpeedScaling.ResolveForModel(entity, channel))
    entity:SetAttribute("AnimationPlaybackSpeedPercent", percent)
    local speed = percent / 100
    local success, failure = pcall(function()
        if clip.track.IsPlaying then
            clip.track:AdjustSpeed(speed)
        else
            clip.track:Play(fade or NpcConfig.TransitionSeconds, 1, speed)
        end
    end)
    if not success then
        warn("[game1][npc] animation playback failed: " .. tostring(failure))
        return false
    end
    clip.playbackSpeed = speed
    return true
end

function NpcAnimationTracks.SecondsRemaining(clip: any?): number?
    if not clip or not clip.track or not clip.track.IsPlaying then return nil end
    local length = tonumber(clip.track.Length) or 0
    if length <= 0 then return nil end
    local position = tonumber(clip.track.TimePosition) or 0
    local speed = math.max(0.01, tonumber(clip.playbackSpeed) or 1)
    return math.max(0, length - position) / speed
end

function NpcAnimationTracks.Stop(clip: any?, fade: number?)
    if not clip then
        return
    end
    local success, failure = pcall(function()
        if clip.track.IsPlaying then
            clip.track:Stop(fade or NpcConfig.TransitionSeconds)
        end
    end)
    if not success then
        warn("[game1][npc] animation stop failed: " .. tostring(failure))
    end
end

return table.freeze(NpcAnimationTracks)
