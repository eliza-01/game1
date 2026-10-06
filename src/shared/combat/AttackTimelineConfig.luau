-- Authoritative attack-animation timeline configuration.
--
-- Every gameplay attack clip must be registered here. `duration` is the source
-- animation duration at 100% playback. Event positions can be authored either
-- in source-animation seconds (`time`) or as a 0..1 fraction (`normalizedTime`).
-- Runtime timing is divided by the same playback speed used by the Animator.
-- The final playback percentage is resolved by AnimationSpeedScaling from gameplay
-- stats (or a temporary runtime debug override), so presentation and gameplay
-- events remain on the same authored animation phase.
--
-- `result` links an animation event to gameplay. game1 currently implements
-- `melee_damage`; the event schema is deliberately generic so later attacks can
-- add Hit2 / Release / HitStart / HitEnd without putting timing constants in the
-- controller or server combat code.
local AttackTimelineConfig = {}

AttackTimelineConfig.SchemaVersion = 1
AttackTimelineConfig.EndGuardSeconds = 0.03
AttackTimelineConfig.EventNames = table.freeze({
    Hit = true,
    Hit2 = true,
    HitStart = true,
    HitEnd = true,
    Release = true,
})
AttackTimelineConfig.ResultTypes = table.freeze({
    MeleeDamage = "melee_damage",
    ProjectileRelease = "projectile_release",
})

local BY_CLIP = table.freeze({
    ["human_female__weapon__1hs__attack__01"] = table.freeze({
        duration = 1.866666674,
        events = table.freeze({
            Hit = table.freeze({ normalizedTime = 0.50, result = "melee_damage" }),
        }),
    }),
    ["human_female__weapon__1hs__attack__02"] = table.freeze({
        duration = 1.866666674,
        events = table.freeze({
            Hit = table.freeze({ normalizedTime = 0.50, result = "melee_damage" }),
        }),
    }),
    ["human_female__weapon__1hs__attack__03"] = table.freeze({
        duration = 1.866666674,
        events = table.freeze({
            Hit = table.freeze({ normalizedTime = 0.50, result = "melee_damage" }),
        }),
    }),
    ["monster__gremlin__attack__01"] = table.freeze({
        duration = 1.799999952,
        events = table.freeze({
            Hit = table.freeze({ normalizedTime = 0.50, result = "melee_damage" }),
        }),
    }),
})

AttackTimelineConfig.ByClip = BY_CLIP

local function copyRuntimeEvent(source: any, baseDuration: number, playbackSpeed: number): any
    local sourceTime = tonumber(source and source.time)
    local normalized = tonumber(source and source.normalizedTime)
    if sourceTime == nil and normalized ~= nil then
        sourceTime = math.clamp(normalized, 0, 1) * baseDuration
    end
    sourceTime = math.clamp(sourceTime or 0, 0, baseDuration)
    return {
        time = sourceTime / playbackSpeed,
        sourceTime = sourceTime,
        normalizedTime = if baseDuration > 0 then sourceTime / baseDuration else 0,
        result = tostring(source and source.result or ""),
    }
end

function AttackTimelineConfig.ResolveBase(clipId: any): any?
    local source = BY_CLIP[tostring(clipId or "")]
    if type(source) ~= "table" then
        return nil
    end
    local duration = tonumber(source.duration) or 0
    if duration <= 0 then
        return nil
    end
    return source
end

function AttackTimelineConfig.ResolveRuntime(clipId: any, animationSpeedPercent: any, _duplicateFirstFrameAtEnd: any?): any?
    local source = AttackTimelineConfig.ResolveBase(clipId)
    if not source then
        return nil
    end

    local baseDuration = math.max(0.001, tonumber(source.duration) or 0)
    local clipPercent = math.clamp(tonumber(animationSpeedPercent) or 100, 1, 400)
    local playbackSpeed = math.max(0.01, clipPercent / 100)
    local events = {}
    for eventName, event in pairs(source.events or {}) do
        events[tostring(eventName)] = copyRuntimeEvent(event, baseDuration, playbackSpeed)
    end

    local sourceAnimationDuration = baseDuration / playbackSpeed
    -- Runtime first-frame seam is presentation-only. It never extends the
    -- authored attack timeline or changes when an attack may complete.
    local runtimeTailDuration = 0
    local animationDuration = sourceAnimationDuration
    return {
        clipId = tostring(clipId),
        baseDuration = baseDuration,
        sourceAnimationDuration = sourceAnimationDuration,
        runtimeTailDuration = runtimeTailDuration,
        animationDuration = animationDuration,
        duration = animationDuration + AttackTimelineConfig.EndGuardSeconds,
        playbackSpeed = playbackSpeed,
        animationSpeedPercent = clipPercent,
        events = events,
    }
end

return table.freeze(AttackTimelineConfig)
