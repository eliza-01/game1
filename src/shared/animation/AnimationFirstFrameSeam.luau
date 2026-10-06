-- Runtime-only first-frame tail for published animations.
--
-- The authored/published asset is never rewritten. When enabled for a clip,
-- game1 freezes the primary track at its visible terminal pose and crossfades
-- to a second instance of the same asset frozen at TimePosition=0 for one
-- source animation frame. Looped clips then restart from frame zero; one-shot
-- clips remain on that first-frame tail until their owner releases the action.
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

function AnimationFirstFrameSeam.RuntimeTailSeconds(playbackSpeed: any): number
    local speed = math.max(0.01, math.abs(finite(playbackSpeed, 1)))
    return AnimationFirstFrameSeam.SourceFrameSeconds / speed
end

function AnimationFirstFrameSeam.new(primary: AnimationTrack, companion: AnimationTrack, looped: boolean)
    return setmetatable({
        primary = primary,
        companion = companion,
        looped = looped == true,
        speed = 1,
        phase = "idle",
        tailElapsed = 0,
        tailDuration = AnimationFirstFrameSeam.SourceFrameSeconds,
        completedSignaled = false,
    }, AnimationFirstFrameSeam)
end

function AnimationFirstFrameSeam:IsPlaying(): boolean
    return self.phase == "playing" or self.phase == "tail"
end

function AnimationFirstFrameSeam:Play(fadeTime: number?, playbackSpeed: number?)
    self:Stop(0)
    self.speed = math.max(0.01, finite(playbackSpeed, 1))
    self.tailDuration = AnimationFirstFrameSeam.RuntimeTailSeconds(self.speed)
    self.tailElapsed = 0
    self.completedSignaled = false
    self.phase = "playing"

    self.primary.Looped = false
    self.companion.Looped = false
    self.primary:Play(math.max(0, finite(fadeTime, 0)), 1, self.speed)
    self.primary.TimePosition = 0
end

function AnimationFirstFrameSeam:AdjustSpeed(playbackSpeed: number?)
    self.speed = math.max(0.01, finite(playbackSpeed, self.speed))
    self.tailDuration = AnimationFirstFrameSeam.RuntimeTailSeconds(self.speed)
    if self.phase == "playing" and self.primary.IsPlaying then
        self.primary:AdjustSpeed(self.speed)
    end
end

function AnimationFirstFrameSeam:_beginTail()
    local length = math.max(0, finite(self.primary.Length, 0))
    if length <= 0 then
        return
    end

    -- Latch just inside the valid source interval so AnimationTrack never owns
    -- the natural-stop edge. The companion is the same published animation,
    -- held on frame zero. Weight interpolation creates the synthetic tail.
    self.primary.TimePosition = math.max(0, length - 0.001)
    self.primary:AdjustSpeed(0)

    if self.companion.IsPlaying then
        self.companion:Stop(0)
    end
    self.companion.Looped = false
    self.companion:Play(0, 0, 1)
    self.companion.TimePosition = 0
    self.companion:AdjustSpeed(0)

    self.tailElapsed = 0
    self.tailDuration = AnimationFirstFrameSeam.RuntimeTailSeconds(self.speed)
    self.primary:AdjustWeight(0, self.tailDuration)
    self.companion:AdjustWeight(1, self.tailDuration)
    self.phase = "tail"
end

-- Returns: completedOneShot, completedLoopCycle.
function AnimationFirstFrameSeam:Step(deltaTimeSim: number): (boolean, boolean)
    if self.phase == "playing" then
        if not self.primary.IsPlaying then
            return false, false
        end
        local length = math.max(0, finite(self.primary.Length, 0))
        if length <= 0 then
            return false, false
        end
        local current = math.max(0, finite(self.primary.TimePosition, 0))
        local dt = math.max(1 / 240, finite(deltaTimeSim, 0))
        local projected = current + self.speed * dt * 1.5
        if projected >= length - 0.0005 then
            self:_beginTail()
        end
        return false, false
    end

    if self.phase ~= "tail" then
        return false, false
    end

    self.tailElapsed += math.max(0, finite(deltaTimeSim, 0))
    if self.tailElapsed + 1e-5 < self.tailDuration then
        return false, false
    end

    self.primary:Stop(0)
    if self.looped then
        -- Companion and restarted primary are both exactly frame zero here, so
        -- handing weight back to the primary is visually neutral.
        self.primary.Looped = false
        self.primary:Play(0, 1, self.speed)
        self.primary.TimePosition = 0
        self.companion:Stop(0)
        self.phase = "playing"
        self.tailElapsed = 0
        return false, true
    end

    self.phase = "complete"
    if not self.completedSignaled then
        self.completedSignaled = true
        return true, false
    end
    return false, false
end

function AnimationFirstFrameSeam:Stop(fadeTime: number?)
    local fade = math.max(0, finite(fadeTime, 0))
    if self.primary.IsPlaying then
        self.primary:Stop(fade)
    end
    if self.companion.IsPlaying then
        self.companion:Stop(fade)
    end
    self.phase = "idle"
    self.tailElapsed = 0
    self.completedSignaled = false
end

return table.freeze(AnimationFirstFrameSeam)
