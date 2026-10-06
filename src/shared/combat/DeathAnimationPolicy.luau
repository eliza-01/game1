-- Canonical death playback contract.
--
-- A corpse must never depend on AnimationTrack's natural-stop edge to preserve
-- its terminal pose. PreAnimation detects the last animation step, moves the
-- track to a deterministic point just inside the clip, converts it to a looped
-- hold, and freezes it at full weight. Setting Looped before freezing prevents
-- the Animator from deactivating the track on the same scheduler frame.
--
-- If a frame hitch let Roblox stop the track first, the elapsed-time fallback
-- reactivates that exact terminal hold. This makes Death -> DeathIdle independent
-- of render FPS / scheduler timing while still playing effectively the full clip.
local DeathAnimationPolicy = {}
local startedAt = setmetatable({}, { __mode = "k" })

DeathAnimationPolicy.TerminalSafetySeconds = 0.02

function DeathAnimationPolicy.Start(track: AnimationTrack)
    track.Looped = false
    track.Priority = Enum.AnimationPriority.Action4
    track:Play(0, 1, 1)
    track.TimePosition = 0
    track:AdjustWeight(1, 0)
    startedAt[track] = os.clock()
end

local function holdTerminalPose(track: AnimationTrack, terminalTime: number)
    track.Looped = true
    if not track.IsPlaying then
        track:Play(0, 1, 1)
    end
    track.TimePosition = terminalTime
    track:AdjustWeight(1, 0)
    track:AdjustSpeed(0)
end

function DeathAnimationPolicy.LatchVisibleTerminalPose(track: AnimationTrack, deltaTimeSim: number): (boolean, number?)
    local length = tonumber(track.Length) or 0
    if length <= 0 then
        return false, nil
    end

    local terminalTime = math.max(0, length - math.min(DeathAnimationPolicy.TerminalSafetySeconds, length * 0.05))
    local current = math.max(0, tonumber(track.TimePosition) or 0)
    local speed = math.max(0, tonumber(track.Speed) or 0)
    local step = math.max(0, tonumber(deltaTimeSim) or 0) * speed
    local elapsed = math.max(0, os.clock() - (startedAt[track] or os.clock()))

    if current < terminalTime and current + step < terminalTime and elapsed < terminalTime then
        return false, current
    end

    holdTerminalPose(track, terminalTime)
    return true, terminalTime
end

return table.freeze(DeathAnimationPolicy)
