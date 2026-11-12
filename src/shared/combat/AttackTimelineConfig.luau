-- Runtime resolver for Asset Manager-authored attack timelines.
--
-- Asset Manager owns normalized event positions. Runtime converts them to the
-- exact playback speed used by the animation system. Character melee windows
-- are interpreted separately by CharacterAttackWindow; monster attacks keep
-- their current single Hit event semantics.
local CharacterAttackCadence = require(script.Parent:WaitForChild("CharacterAttackCadence"))

local AttackTimelineConfig = {}

AttackTimelineConfig.SchemaVersion = 2
AttackTimelineConfig.EndGuardSeconds = 0.03
AttackTimelineConfig.EventNames = table.freeze({
    HitStart = true,
    HitEnd = true,
    Hit = true,
    Release = true,
})

local BY_CLIP = require(script.Parent:WaitForChild("AttackTimelineData"))
AttackTimelineConfig.ByClip = BY_CLIP

local function copyRuntimeEvent(source: any, sourceDuration: number, playbackSpeed: number): any
    local normalizedTime = math.clamp(tonumber(source and source.normalizedTime) or 0, 0, 1)
    local sourceTime = normalizedTime * sourceDuration
    return {
        time = sourceTime / playbackSpeed,
        sourceTime = sourceTime,
        normalizedTime = normalizedTime,
    }
end

function AttackTimelineConfig.ResolveBase(clipId: any): any?
    local source = BY_CLIP[tostring(clipId or "")]
    if type(source) ~= "table" or (tonumber(source.duration) or 0) <= 0 then
        return nil
    end
    return source
end

function AttackTimelineConfig.ResolveRuntime(clipId: any, animationSpeedPercent: any): any?
    local source = AttackTimelineConfig.ResolveBase(clipId)
    if not source then
        return nil
    end

    local sourceDuration = math.max(0.001, tonumber(source.duration) or 0)
    local speedPercent = math.clamp(tonumber(animationSpeedPercent) or 100, 1, 400)
    local playbackSpeed = math.max(0.01, speedPercent / 100)
    local events = {}
    for eventName, event in pairs(source.events or {}) do
        events[tostring(eventName)] = copyRuntimeEvent(event, sourceDuration, playbackSpeed)
    end

    local playbackDuration = sourceDuration / playbackSpeed
    return {
        clipId = tostring(clipId),
        duration = playbackDuration + AttackTimelineConfig.EndGuardSeconds,
        playbackDuration = playbackDuration,
        playbackSpeed = playbackSpeed,
        animationSpeedPercent = speedPercent,
        events = events,
    }
end


-- Player-character attacks have a stat-defined *gameplay* cadence.  The source
-- duration is only used to fit the authored clip into that cadence; unlike
-- ResolveRuntime, this cannot make different character clips attack at different
-- rates.  Reserve EndGuardSeconds at the end for animation/pose cleanup.
function AttackTimelineConfig.ResolveCharacterRuntime(clipId: any, attackSpeed: any): any?
    local source = AttackTimelineConfig.ResolveBase(clipId)
    if not source then
        return nil
    end

    local sourceDuration = math.max(0.001, tonumber(source.duration) or 0)
    local statValue = CharacterAttackCadence.NormalizeAttackSpeed(attackSpeed)
    local gameplayDuration = CharacterAttackCadence.DurationForStat(statValue)
    local playbackDuration = math.max(0.001, gameplayDuration - AttackTimelineConfig.EndGuardSeconds)
    local playbackSpeed = sourceDuration / playbackDuration
    local events = {}
    for eventName, event in pairs(source.events or {}) do
        events[tostring(eventName)] = copyRuntimeEvent(event, sourceDuration, playbackSpeed)
    end

    return {
        clipId = tostring(clipId),
        duration = gameplayDuration,
        playbackDuration = playbackDuration,
        playbackSpeed = playbackSpeed,
        animationSpeedPercent = playbackSpeed * 100,
        attackSpeedStat = statValue,
        events = events,
    }
end

return table.freeze(AttackTimelineConfig)
