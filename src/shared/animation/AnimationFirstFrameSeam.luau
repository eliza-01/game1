-- Runtime-only loop seam for published animations.
--
-- The authored/published asset is never rewritten. The primary AnimationTrack
-- remains the timing source at all times: it stays looped when the descriptor
-- is looped and keeps the exact playback speed supplied by the caller.
--
-- When enabled, a second instance of the same asset is frozen on frame zero.
-- During only the final authored source frame, weights are blended from the
-- primary terminal pose toward that frozen first pose. At the natural loop
-- wrap both tracks represent frame zero, so ownership can return to the primary
-- without stopping, seeking or restarting it. This makes the seam independent
-- from RunSpeed / Animation Speed % timing.
local AnimationFirstFrameSeam = {}
AnimationFirstFrameSeam.__index = AnimationFirstFrameSeam

AnimationFirstFrameSeam.SourceFrameSeconds = 1 / 30

local function finite(value: any, fallback: number): number
    local numeric = tonumber(value)
    if numeric == nil or numeric ~= numeric or numeric == math.huge or numeric == -math.huge then
        return fallback
    end
    return numeric
end

function AnimationFirstFrameSeam.new(primary: AnimationTrack, companion: AnimationTrack, looped: boolean)
    return setmetatable({
        primary = primary,
        companion = companion,
        looped = looped == true,
        speed = 1,
        phase = "idle",
        previousTime = 0,
        companionActive = false,
        completedSignaled = false,
    }, AnimationFirstFrameSeam)
end

function AnimationFirstFrameSeam:IsPlaying(): boolean
    return self.phase == "playing" or self.phase == "blend"
end

function AnimationFirstFrameSeam:_hideCompanion()
    if self.companionActive or self.companion.IsPlaying then
        self.companion:AdjustWeight(0, 0)
        self.companion:Stop(0)
    end
    self.companionActive = false
end

function AnimationFirstFrameSeam:_ensureCompanion()
    if self.companionActive and self.companion.IsPlaying then
        return
    end
    if self.companion.IsPlaying then
        self.companion:Stop(0)
    end
    self.companion.Looped = false
    self.companion:Play(0, 0, 1)
    self.companion.TimePosition = 0
    self.companion:AdjustSpeed(0)
    self.companion:AdjustWeight(0, 0)
    self.companionActive = true
end

function AnimationFirstFrameSeam:_setBlend(progress: number)
    local alpha = math.clamp(progress, 0, 1)
    self:_ensureCompanion()
    -- Only pose weights change. The primary clock and playback speed continue
    -- untouched so the seam cannot stretch or stall the animation cycle.
    self.primary:AdjustWeight(1 - alpha, 0)
    self.companion:AdjustWeight(alpha, 0)
    self.phase = "blend"
end

function AnimationFirstFrameSeam:_restorePrimary()
    self.primary:AdjustWeight(1, 0)
    self:_hideCompanion()
    self.phase = "playing"
end

function AnimationFirstFrameSeam:Play(fadeTime: number?, playbackSpeed: number?)
    self:Stop(0)
    self.speed = math.max(0.01, finite(playbackSpeed, 1))
    self.previousTime = 0
    self.completedSignaled = false
    self.phase = "playing"

    self.primary.Looped = self.looped
    self.companion.Looped = false
    self.primary:Play(math.max(0, finite(fadeTime, 0)), 1, self.speed)
    self.primary.TimePosition = 0
    self.primary:AdjustWeight(1, 0)
end

function AnimationFirstFrameSeam:AdjustSpeed(playbackSpeed: number?)
    self.speed = math.max(0.01, finite(playbackSpeed, self.speed))
    if self.primary.IsPlaying then
        self.primary:AdjustSpeed(self.speed)
    end
end

-- Returns: completedOneShot, completedLoopCycle.
function AnimationFirstFrameSeam:Step(_deltaTimeSim: number): (boolean, boolean)
    if self.phase ~= "playing" and self.phase ~= "blend" then
        return false, false
    end

    local length = math.max(0, finite(self.primary.Length, 0))
    if length <= 0 then
        return false, false
    end

    local current = math.clamp(finite(self.primary.TimePosition, 0), 0, length)
    local wrapped = self.looped
        and self.primary.IsPlaying
        and current + 1e-5 < self.previousTime
        and self.previousTime > length * 0.5

    if wrapped then
        -- The primary has already looped naturally. At this instant the
        -- companion and primary are both on frame zero, so restoring weight is
        -- visually neutral and does not alter the primary timeline.
        self:_restorePrimary()
        self.previousTime = current
        return false, true
    end

    local blendStart = math.max(0, length - AnimationFirstFrameSeam.SourceFrameSeconds)
    if self.primary.IsPlaying and current >= blendStart then
        local span = math.max(1e-5, length - blendStart)
        self:_setBlend((current - blendStart) / span)
    elseif self.primary.IsPlaying then
        if self.phase == "blend" or self.companionActive then
            self:_restorePrimary()
        end
    elseif not self.looped then
        -- A one-shot ends on its own schedule. Holding frame zero after natural
        -- completion is presentation-only; no synthetic duration is added to
        -- gameplay/attack timing.
        self:_setBlend(1)
        self.phase = "complete"
        if not self.completedSignaled then
            self.completedSignaled = true
            self.previousTime = current
            return true, false
        end
    end

    self.previousTime = current
    return false, false
end

function AnimationFirstFrameSeam:Stop(fadeTime: number?)
    local fade = math.max(0, finite(fadeTime, 0))
    if self.primary.IsPlaying then
        self.primary:AdjustWeight(1, 0)
        self.primary:Stop(fade)
    end
    if self.companion.IsPlaying then
        self.companion:Stop(fade)
    end
    self.phase = "idle"
    self.previousTime = 0
    self.companionActive = false
    self.completedSignaled = false
end

return table.freeze(AnimationFirstFrameSeam)
