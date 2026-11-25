--!strict
-- A side-view, articulated running glyph. Each segment connects two joints;
-- Frame.Rotation alone rotates about the centre and would detach the limbs.
local Runner = {}
Runner.Width = 44
Runner.Height = 42
local SHOULDER = Vector2.new(23, 13)
local HIP = Vector2.new(19, 24)
local TAU = 2 * math.pi
local LEG_SECONDS = 1

-- Independent triangular travel: constant speed, no progress dependency.
function Runner.Travel(elapsed: number): (number, boolean)
    local phase = (elapsed / LEG_SECONDS) % 2
    if phase < 1 then return phase, true end
    return 2 - phase, false
end

local function endpoint(origin: Vector2, length: number, angle: number): Vector2
    local radians = math.rad(angle)
    return origin + Vector2.new(math.sin(radians), math.cos(radians)) * length
end

local function connectSegment(segment: Frame, a: Vector2, b: Vector2)
    local delta = b - a
    local centre = (a + b) * 0.5
    segment.Position = UDim2.fromOffset(centre.X, centre.Y)
    segment.Rotation = math.deg(math.atan2(-delta.X, delta.Y))
end

function Runner.Build(parent: Instance, ink: Color3, layer: number): (Frame, (number) -> ())
    local root = Instance.new("Frame")
    root.Name = "LoadingRunner"
    root.BackgroundTransparency = 1
    root.Size = UDim2.fromOffset(Runner.Width, Runner.Height)
    root.ZIndex = layer
    root.Parent = parent

    local function shape(name: string, width: number, height: number, color: Color3, z: number): Frame
        local item = Instance.new("Frame")
        item.Name = name
        item.AnchorPoint = Vector2.new(0.5, 0.5)
        item.Size = UDim2.fromOffset(width, height)
        item.BackgroundColor3 = color
        item.BorderSizePixel = 0
        item.ZIndex = z
        item.Parent = root
        local corner = Instance.new("UICorner")
        corner.CornerRadius = UDim.new(1, 0)
        corner.Parent = item
        return item
    end
    local facingRight = true
    local function facing(point: Vector2): Vector2
        return if facingRight then point else Vector2.new(Runner.Width - point.X, point.Y)
    end
    local function connect(segment: Frame, a: Vector2, b: Vector2)
        connectSegment(segment, facing(a), facing(b))
    end
    local far = ink:Lerp(Color3.fromRGB(17, 24, 30), 0.32)
    local function pair(name: string, upper: number, lower: number, color: Color3, z: number): (Frame, Frame)
        -- Add the stroke width to each length so adjoining rounded ends overlap.
        return shape(name .. "Upper", 3, upper + 3, color, z), shape(name .. "Lower", 3, lower + 3, color, z)
    end
    local farArm, farForearm = pair("FarArm", 7, 7, far, layer)
    local farThigh, farShin = pair("FarLeg", 9, 9, far, layer)
    local torso = shape("Body", 4, (SHOULDER - HIP).Magnitude + 4, ink, layer + 1)
    local head = shape("Head", 9, 9, ink, layer + 1)
    -- Small forward-facing profile makes direction visible even at icon size.
    local nose = shape("Nose", 3, 3, ink, layer + 1)
    local nearArm, nearForearm = pair("NearArm", 7, 7, ink, layer + 2)
    local nearThigh, nearShin = pair("NearLeg", 9, 9, ink, layer + 2)

    local function side(phase: number, arm: Frame, forearm: Frame, thigh: Frame, shin: Frame)
        local swing = math.sin(phase)
        local armAngle = -42 * swing
        local elbow = endpoint(SHOULDER, 7, armAngle)
        local hand = endpoint(elbow, 7, armAngle + 78)
        connect(arm, SHOULDER, elbow)
        connect(forearm, elbow, hand)
        local thighAngle = 45 * swing
        local knee = endpoint(HIP, 9, thighAngle)
        -- Knee bends backwards during recovery, extending on the support phase.
        local bend = 12 + 56 * (0.5 + 0.5 * math.cos(phase))
        local foot = endpoint(knee, 9, thighAngle - bend)
        connect(thigh, HIP, knee)
        connect(shin, knee, foot)
    end
    local function pose(elapsed: number)
        local _, right = Runner.Travel(elapsed)
        facingRight = right
        connect(torso, SHOULDER, HIP)
        local headPoint = facing(Vector2.new(25, 7))
        head.Position = UDim2.fromOffset(headPoint.X, headPoint.Y)
        local nosePoint = facing(Vector2.new(29, 7))
        nose.Position = UDim2.fromOffset(nosePoint.X, nosePoint.Y)
        local phase = elapsed * TAU * 1.65
        side(phase + math.pi, farArm, farForearm, farThigh, farShin)
        side(phase, nearArm, nearForearm, nearThigh, nearShin)
    end
    pose(0)
    return root, pose
end

return Runner
