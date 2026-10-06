local HitSparkBurst = {}

local BASE_ANGLES_DEGREES = table.freeze({ -144, -72, 0, 72, 144, 36, 108, -108 })
local rng = Random.new()

local function makeBeam(config: any, parent: Instance, index: number): any
    local tail = Instance.new("Attachment")
    tail.Name = ("SparkTail%02d"):format(index)
    tail.Parent = parent

    local head = Instance.new("Attachment")
    head.Name = ("SparkHead%02d"):format(index)
    head.Parent = parent

    local beam = Instance.new("Beam")
    beam.Name = ("ImpactSpark%02d"):format(index)
    beam.Attachment0 = tail
    beam.Attachment1 = head
    beam.Enabled = false
    beam.FaceCamera = true
    beam.Segments = 1
    beam.Width0 = config.SparkWidthTail
    beam.Width1 = config.SparkWidthHead
    beam.CurveSize0 = 0
    beam.CurveSize1 = 0
    beam.LightEmission = 1
    beam.LightInfluence = 0
    beam.Brightness = config.SparkBrightness
    beam.ZOffset = 0.05
    beam.Color = ColorSequence.new({
        ColorSequenceKeypoint.new(0, Color3.fromRGB(255, 245, 194)),
        ColorSequenceKeypoint.new(0.45, Color3.fromRGB(255, 184, 63)),
        ColorSequenceKeypoint.new(1, Color3.fromRGB(224, 96, 24)),
    })
    beam.Transparency = NumberSequence.new({
        NumberSequenceKeypoint.new(0, 0.03),
        NumberSequenceKeypoint.new(0.68, 0.10),
        NumberSequenceKeypoint.new(1, 0.72),
    })
    beam.Parent = parent

    return {
        tail = tail,
        head = head,
        beam = beam,
        origin = Vector3.zero,
        direction = Vector3.new(1, 0, 0),
        segmentLength = config.SparkLengthMin,
        speed = config.SparkTravelSpeedMin,
        baseWidthTail = config.SparkWidthTail,
        baseWidthHead = config.SparkWidthHead,
    }
end

function HitSparkBurst.Create(parent: Instance, config: any, index: number): any
    local part = Instance.new("Part")
    part.Name = ("HitSparkSlot%02d"):format(index)
    part.Size = Vector3.new(0.05, 0.05, 0.05)
    part.Transparency = 1
    part.Anchored = true
    part.CanCollide = false
    part.CanTouch = false
    part.CanQuery = false
    part.CastShadow = false
    part.Parent = parent

    local streaks = table.create(config.CriticalSparkCount)
    for sparkIndex = 1, config.CriticalSparkCount do
        streaks[sparkIndex] = makeBeam(config, part, sparkIndex)
    end

    return {
        part = part,
        streaks = streaks,
        age = 0,
        duration = 0,
        active = false,
        activeCount = 0,
    }
end

local function configureStreak(streak: any, config: any, sparkIndex: number)
    local angle = BASE_ANGLES_DEGREES[sparkIndex]
        + rng:NextNumber(-config.SparkDirectionJitterDegrees, config.SparkDirectionJitterDegrees)
    local radians = math.rad(angle)
    local depth = rng:NextNumber(-config.SparkDepthJitter, config.SparkDepthJitter)
    local direction = Vector3.new(math.cos(radians), math.sin(radians), depth).Unit
    local origin = Vector3.new(
        rng:NextNumber(-config.SparkOriginSpreadX, config.SparkOriginSpreadX),
        rng:NextNumber(-config.SparkOriginSpreadY, config.SparkOriginSpreadY),
        rng:NextNumber(-config.SparkOriginDepth, config.SparkOriginDepth)
    )
    local length = rng:NextNumber(config.SparkLengthMin, config.SparkLengthMax)

    streak.origin = origin
    streak.direction = direction
    streak.segmentLength = length
    streak.speed = rng:NextNumber(config.SparkTravelSpeedMin, config.SparkTravelSpeedMax)
    streak.tail.Position = origin
    streak.head.Position = origin + direction * length
    streak.beam.Width0 = streak.baseWidthTail
    streak.beam.Width1 = streak.baseWidthHead
    streak.beam.Enabled = true
end

function HitSparkBurst.Emit(slot: any, config: any, position: Vector3, cameraCFrame: CFrame, critical: boolean)
    slot.part.CFrame = CFrame.lookAt(position, position + cameraCFrame.LookVector, cameraCFrame.UpVector)
    slot.age = 0
    slot.duration = if critical then config.CriticalSparkDuration else config.NormalSparkDuration
    slot.activeCount = if critical then config.CriticalSparkCount else config.NormalSparkCount
    slot.active = true

    for sparkIndex, streak in ipairs(slot.streaks) do
        if sparkIndex <= slot.activeCount then
            configureStreak(streak, config, sparkIndex)
        else
            streak.beam.Enabled = false
        end
    end
end

function HitSparkBurst.Step(slot: any, dt: number)
    if not slot.active then return end
    slot.age += dt
    if slot.age >= slot.duration then
        slot.active = false
        for _, streak in ipairs(slot.streaks) do
            streak.beam.Enabled = false
        end
        return
    end

    local fadeStart = slot.duration * 0.62
    local widthScale = 1
    if slot.age > fadeStart then
        widthScale = math.max(0.2, 1 - (slot.age - fadeStart) / math.max(0.001, slot.duration - fadeStart))
    end

    for sparkIndex = 1, slot.activeCount do
        local streak = slot.streaks[sparkIndex]
        local travel = streak.speed * slot.age
        local tail = streak.origin + streak.direction * travel
        streak.tail.Position = tail
        streak.head.Position = tail + streak.direction * streak.segmentLength
        streak.beam.Width0 = math.max(0.012, streak.baseWidthTail * widthScale)
        streak.beam.Width1 = math.max(0.006, streak.baseWidthHead * widthScale)
    end
end

return table.freeze(HitSparkBurst)
