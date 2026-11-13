-- Overhead HP view: no combat state or damage calculation; style is client-only.
local TweenService = game:GetService("TweenService")
local HealthBarView = {}
local TWEEN = TweenInfo.new(0.23, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)

local function corner(parent: Instance): UICorner
    local item = Instance.new("UICorner")
    item.CornerRadius = UDim.new(1, 0)
    item.Parent = parent
    return item
end

local function color(hex: string): Color3
    if type(hex) ~= "string" or #hex ~= 7 then return Color3.new(1, 1, 1) end
    return Color3.fromRGB(tonumber(hex:sub(2, 3), 16) or 255,
        tonumber(hex:sub(4, 5), 16) or 255, tonumber(hex:sub(6, 7), 16) or 255)
end

local function healthColor(ratio: number, palette: {[string]: string}): Color3
    if ratio <= 0.30 then return color(palette.red) end
    if ratio <= 0.65 then return color(palette.yellow) end
    return color(palette.green)
end

-- Positioned from actual visual geometry, never the hidden RootCollider height.
local function visualTopOffset(model: Model, anchor: BasePart): number
    local top = anchor.Position.Y + anchor.Size.Y * 0.5
    for _, part in ipairs(model:GetDescendants()) do
        if part:IsA("BasePart") and part.Transparency < 1
            and part ~= anchor and part.Name ~= "HumanoidRootPart" then
            local half = part.Size * 0.5
            local frame = part.CFrame
            local extent = math.abs(frame.RightVector.Y) * half.X
                + math.abs(frame.UpVector.Y) * half.Y
                + math.abs(frame.LookVector.Y) * half.Z
            top = math.max(top, frame.Position.Y + extent)
        end
    end
    return math.max(anchor.Size.Y / 2 + 1, top - anchor.Position.Y + 0.7)
end

local function displayName(model: Model, monster: boolean): string
    local text = if monster then tostring(model:GetAttribute("MonsterDisplayName")
        or model:GetAttribute("MonsterSlug") or model.Name):gsub("_", " ")
        else tostring(model:GetAttribute("CharacterDisplayName") or model.Name)
    -- English monster slugs/names are always title-cased, including multiword names.
    if monster then
        return (text:gsub("(%a)([%w']*)", function(first, tail)
            return first:upper() .. tail:lower()
        end))
    end
    return text
end

function HealthBarView.Create(parent: PlayerGui, model: Model, anchor: BasePart, style: {[string]: any}): any
    local monster = model:GetAttribute("Game1MonsterRuntime") == true
        or model:GetAttribute("MonsterSlug") ~= nil
    local layout = if monster then "monster" else "self"
    local nameText = displayName(model, monster)
    local level = if monster then tonumber(model:GetAttribute("Level")) else nil

    local gui = Instance.new("BillboardGui")
    gui.Name = "Game1OverheadHP"
    gui.AlwaysOnTop = true
    gui.LightInfluence = 0
    gui.MaxDistance = 260
    gui.Adornee = anchor
    gui.Enabled = false
    gui.Parent = parent

    local titleLine = Instance.new("Frame")
    titleLine.Name = "TitleLine"
    titleLine.BackgroundTransparency = 1
    titleLine.Parent = gui
    local rowLayout = Instance.new("UIListLayout")
    rowLayout.FillDirection = Enum.FillDirection.Horizontal
    rowLayout.HorizontalAlignment = Enum.HorizontalAlignment.Center
    rowLayout.VerticalAlignment = Enum.VerticalAlignment.Center
    rowLayout.Padding = UDim.new(0, 7)
    rowLayout.Parent = titleLine

    local number = Instance.new("TextLabel")
    number.Name = "Level"
    number.BackgroundTransparency = 1
    number.Font = Enum.Font.GothamBold
    number.Text = if level and level > 0 then tostring(math.floor(level)) else ""
    number.TextColor3 = Color3.fromRGB(255, 177, 49)
    number.TextStrokeTransparency = 0
    number.TextStrokeColor3 = Color3.new(0, 0, 0)
    number.Visible = monster and level ~= nil and level > 0
    number.Parent = titleLine

    local title = Instance.new("TextLabel")
    title.Name = "Caption"
    title.Text = nameText
    title.Font = Enum.Font.GothamBold
    title.TextColor3 = Color3.fromRGB(250, 250, 251)
    title.BackgroundTransparency = 1
    title.TextStrokeColor3 = Color3.new(0, 0, 0)
    title.TextStrokeTransparency = 0
    title.Parent = titleLine

    local plate = Instance.new("Frame")
    plate.Name = "Plate"
    plate.AnchorPoint = Vector2.new(0.5, 0)
    plate.BorderSizePixel = 0
    plate.BackgroundColor3 = Color3.fromRGB(9, 10, 13)
    plate.Parent = gui
    corner(plate)
    local border = Instance.new("UIStroke")
    border.Name = "Outline"
    border.Color = Color3.fromRGB(0, 0, 0)
    border.Parent = plate

    local track = Instance.new("Frame")
    track.Name = "Track"
    track.BackgroundColor3 = Color3.fromRGB(45, 33, 38)
    track.BorderSizePixel = 0
    track.ClipsDescendants = true
    track.Parent = plate
    corner(track)

    local fill = Instance.new("Frame")
    fill.Name = "Fill"
    fill.Size = UDim2.fromScale(1, 1)
    fill.BorderSizePixel = 0
    fill.Parent = track
    corner(fill)
    local gradient = Instance.new("UIGradient")
    gradient.Rotation = 90
    gradient.Color = ColorSequence.new(Color3.fromRGB(255, 255, 255), Color3.fromRGB(222, 222, 222))
    gradient.Parent = fill

    local connections: {RBXScriptConnection} = {}
    local tween: Tween? = nil
    local first = true
    local currentStyle = style
    local baseOffset = visualTopOffset(model, anchor)

    local function update()
        if not gui.Parent then return end
        local maxHP = math.max(0, tonumber(model:GetAttribute("MaxHP")) or 0)
        local hp = math.clamp(tonumber(model:GetAttribute("HP")) or 0, 0, maxHP)
        local ratio = if maxHP > 0 then hp / maxHP else 0
        local goal = {Size = UDim2.fromScale(ratio, 1), BackgroundColor3 = healthColor(ratio, currentStyle.colors)}
        if tween then tween:Cancel(); tween = nil end
        if first then
            fill.Size = goal.Size
            fill.BackgroundColor3 = goal.BackgroundColor3
            first = false
        else
            tween = TweenService:Create(fill, TWEEN, goal)
            tween:Play()
        end
    end

    local view = {}
    function view.ApplyStyle(settings: {[string]: any})
        currentStyle = settings
        local spec = settings[layout]
        local width, height = spec.width, spec.height
        local titleSize = spec.nameSize
        local levelSize = spec.levelSize
        local lineHeight = math.max(titleSize, levelSize) + 5
        local lineWidth = math.max(width + 28, math.min(580,
            #nameText * titleSize * 0.68 + (number.Visible and levelSize * 2.5 or 0) + 20))
        gui.Size = UDim2.fromOffset(lineWidth, lineHeight + height + 13)
        -- A generous camera-distance cap avoids clipping a monster whose root
        -- is within the actual player-centered radius in third-person view.
        if monster then
            gui.MaxDistance = math.max(260, (tonumber(spec.maxDistanceStuds) or 100) + 80)
        end
        gui.StudsOffsetWorldSpace = Vector3.new(0, baseOffset + spec.offsetStuds, 0)
        titleLine.Position = UDim2.fromOffset(0, 0)
        titleLine.Size = UDim2.fromOffset(lineWidth, lineHeight)
        title.TextSize = titleSize
        title.Size = UDim2.fromOffset(math.min(lineWidth - 20, #nameText * titleSize * 0.68 + 12), lineHeight)
        number.TextSize = levelSize
        number.Size = UDim2.fromOffset(levelSize * 1.7, lineHeight)
        plate.Size = UDim2.fromOffset(width, height)
        plate.Position = UDim2.new(0.5, 0, 0, lineHeight + 2)
        border.Thickness = spec.border
        local pad = math.min(3, math.max(1, math.floor(height / 7)))
        track.Position = UDim2.fromOffset(pad, pad)
        track.Size = UDim2.new(1, -pad * 2, 1, -pad * 2)
        update()
    end
    function view.SetVisible(value: boolean)
        gui.Enabled = value and currentStyle[layout].enabled == true
    end
    function view.Destroy()
        for _, connection in ipairs(connections) do connection:Disconnect() end
        table.clear(connections)
        if tween then tween:Cancel() end
        gui:Destroy()
    end
    view.ApplyStyle(style)
    table.insert(connections, model:GetAttributeChangedSignal("HP"):Connect(update))
    table.insert(connections, model:GetAttributeChangedSignal("MaxHP"):Connect(update))
    return view
end

return table.freeze(HealthBarView)
