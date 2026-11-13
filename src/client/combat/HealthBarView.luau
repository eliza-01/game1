-- Pure local presentation of one model's authoritative HP attributes.
-- Reuses its BillboardGui and tweens the fill; no health writes or remotes.
local TweenService = game:GetService("TweenService")
local HealthBarView = {}
local TWEEN = TweenInfo.new(0.23, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
local GREEN = Color3.fromRGB(69, 219, 139)
local YELLOW = Color3.fromRGB(255, 198, 75)
local RED = Color3.fromRGB(255, 91, 93)

local function round(parent: Instance, radius: number)
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, radius)
    corner.Parent = parent
end

local function colorFor(ratio: number): Color3
    if ratio <= 0.30 then return RED end
    if ratio <= 0.65 then return YELLOW end
    return GREEN
end

function HealthBarView.Create(parent: PlayerGui, model: Model, anchor: BasePart): any
    local gui = Instance.new("BillboardGui")
    gui.Name = "Game1OverheadHP"
    gui.AlwaysOnTop = true
    gui.LightInfluence = 0
    gui.MaxDistance = 260
    gui.Size = UDim2.fromOffset(138, 32)
    gui.StudsOffsetWorldSpace = Vector3.new(0, anchor.Size.Y * 0.5 + 1.25, 0)
    gui.Adornee = anchor
    gui.Enabled = false
    gui.Parent = parent

    local plate = Instance.new("Frame")
    plate.Name = "Plate"
    plate.AnchorPoint = Vector2.new(0.5, 1)
    plate.Position = UDim2.fromScale(0.5, 1)
    plate.Size = UDim2.fromOffset(128, 16)
    plate.BackgroundColor3 = Color3.fromRGB(14, 22, 29)
    plate.BackgroundTransparency = 0.08
    plate.BorderSizePixel = 0
    plate.Parent = gui
    round(plate, 9)
    local border = Instance.new("UIStroke")
    border.Color = Color3.fromRGB(103, 122, 133)
    border.Transparency = 0.46
    border.Thickness = 1
    border.Parent = plate

    local track = Instance.new("Frame")
    track.Name = "Track"
    track.BackgroundColor3 = Color3.fromRGB(31, 39, 45)
    track.BorderSizePixel = 0
    track.Position = UDim2.fromOffset(4, 4)
    track.Size = UDim2.new(1, -8, 0, 8)
    track.ClipsDescendants = true
    track.Parent = plate
    round(track, 5)

    local fill = Instance.new("Frame")
    fill.Name = "Fill"
    fill.BorderSizePixel = 0
    fill.Size = UDim2.fromScale(1, 1)
    fill.BackgroundColor3 = GREEN
    fill.Parent = track
    round(fill, 5)
    local gradient = Instance.new("UIGradient")
    gradient.Rotation = 90
    gradient.Color = ColorSequence.new(Color3.fromRGB(255, 255, 255), Color3.fromRGB(188, 204, 200))
    gradient.Parent = fill

    local name = Instance.new("TextLabel")
    name.Name = "Caption"
    name.BackgroundTransparency = 1
    local monsterSlug = tostring(model:GetAttribute("MonsterSlug") or "")
    name.Text = if monsterSlug ~= "" then string.upper(monsterSlug:gsub("_", " "))
        else tostring(model:GetAttribute("CharacterDisplayName") or model.Name)
    name.TextColor3 = Color3.fromRGB(232, 241, 244)
    name.TextStrokeColor3 = Color3.fromRGB(10, 12, 18)
    name.TextStrokeTransparency = 0.55
    name.Font = Enum.Font.GothamSemibold
    name.TextSize = 10
    name.Size = UDim2.fromOffset(138, 14)
    name.Position = UDim2.fromOffset(0, 0)
    name.Parent = gui

    local connections: {RBXScriptConnection} = {}
    local tween: Tween? = nil
    local first = true
    local function update()
        if not gui.Parent then return end
        local maximum = math.max(0, tonumber(model:GetAttribute("MaxHP")) or 0)
        local hp = math.clamp(tonumber(model:GetAttribute("HP")) or 0, 0, maximum)
        local ratio = if maximum > 0 then hp / maximum else 0
        local goal = { Size = UDim2.fromScale(ratio, 1), BackgroundColor3 = colorFor(ratio) }
        if tween then tween:Cancel() end
        if first then
            fill.Size = goal.Size
            fill.BackgroundColor3 = goal.BackgroundColor3
            first = false
        else
            tween = TweenService:Create(fill, TWEEN, goal)
            tween:Play()
        end
    end
    update()
    table.insert(connections, model:GetAttributeChangedSignal("HP"):Connect(update))
    table.insert(connections, model:GetAttributeChangedSignal("MaxHP"):Connect(update))
    local view = {}
    function view.SetVisible(value: boolean)
        gui.Enabled = value
    end
    function view.Destroy()
        for _, connection in ipairs(connections) do connection:Disconnect() end
        table.clear(connections)
        if tween then tween:Cancel() end
        gui:Destroy()
    end
    return view
end

return table.freeze(HealthBarView)
