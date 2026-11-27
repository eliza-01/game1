-- Presentation only: combat buttons, reserved skill cells, and passive floating stick.
local Layout = require(script.Parent:WaitForChild("MobileLayout"))
local GuiService = game:GetService("GuiService")
local Theme = require(script.Parent.Parent.Parent:WaitForChild("HudButtonTheme"))
local Icons = require(script.Parent.Parent.Parent:WaitForChild("HudSvgIcons"))
local View = {}
local function resolve()
    local area = GuiService:GetInsetArea(Enum.ScreenInsets.CoreUISafeInsets)
    local size = area.Max - area.Min
    return Layout.Resolve(size.X, size.Y)
end

local PALETTE = {
    background = Color3.fromRGB(0, 0, 0),
    rim = Color3.fromRGB(240, 240, 240),
    thumb = Color3.fromRGB(255, 255, 255),
}

local function circle(parent: Instance, size: number, background: Color3, transparency: number): Frame
    local frame = Instance.new("Frame")
    frame.BackgroundColor3 = background
    frame.BackgroundTransparency = transparency
    frame.BorderSizePixel = 0
    frame.Size = UDim2.fromOffset(size, size)
    frame.Parent = parent
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(1, 0)
    corner.Parent = frame
    return frame
end

local function stroke(frame: GuiObject, color: Color3, transparency: number, thickness: number)
    local outline = Instance.new("UIStroke")
    outline.Color = color
    outline.Transparency = transparency
    outline.Thickness = thickness
    outline.Parent = frame
end

local function makeStick(gui: ScreenGui, name: string)
    local pad = circle(gui, 68, PALETTE.background, 0.34)
    pad.Name = name
    -- Passive discoverable home position; never captures pointer input.
    pad.Active = false
    pad.Visible = true
    pad.AnchorPoint = Vector2.new(0.5, 0.5)
    pad:SetAttribute("WorldInputPassthrough", true)
    stroke(pad, PALETTE.rim, 0.80, 1)

    local inner = circle(pad, 28, PALETTE.thumb, 0.42)
    inner.Name = "Thumb"
    inner.AnchorPoint = Vector2.new(0.5, 0.5)
    inner.Position = UDim2.fromScale(0.5, 0.5)
    inner.Visible = true
    inner.Active = false

    return { pad = pad, thumb = inner }
end

local ACTION_COLORS = {
    Aim = Color3.fromRGB(27, 183, 83),
    Skill = Color3.fromRGB(255, 133, 37),
}
local function makeAction(gui: ScreenGui, name: string): TextButton
    local button = Instance.new("TextButton")
    button.Name = name
    button.AnchorPoint = Vector2.new(1, 1)
    local isSkill = string.sub(name, 1, 5) == "Skill"
    Theme.Apply(button)
    button.AutoButtonColor = true
    button.Text = ""
    button.Active = true
    button.Selectable = false
    button.ZIndex = 3
    button.Parent = gui
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(1, 0)
    corner.Parent = button
    if isSkill then
        stroke(button, ACTION_COLORS.Skill, 0.32, 2)
    else
        Icons.Apply(button, name)
    end
    return button
end


function View.Create(playerGui: PlayerGui)
    local gui = Instance.new("ScreenGui")
    gui.Name = "Game1MobileControls"
    gui.ResetOnSpawn = false
    gui.ScreenInsets = Enum.ScreenInsets.DeviceSafeInsets
    gui.SafeAreaCompatibility = Enum.SafeAreaCompatibility.None
    gui.ClipToDeviceSafeArea = true
    gui.DisplayOrder = 15
    gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
    gui.Enabled = false
    gui.Parent = playerGui
    local left = makeStick(gui, "MoveStick")
    local jump = makeAction(gui, "Jump")
    local attack = makeAction(gui, "Attack")
    local aim = makeAction(gui, "Aim")
    local skills = {}
    for i = 1, 4 do skills[i] = makeAction(gui, "Skill" .. i) end
    local result = {gui = gui, left = left, jump = jump, attack = attack, aim = aim, skills = skills, radius = 50}
    local automatic = false
    local target: Model? = nil
    stroke(aim, ACTION_COLORS.Aim, 0.65, 2)
    local function paintAim()
        local outline = aim:FindFirstChildOfClass("UIStroke")
        if outline then
            outline.Transparency = if automatic then 0 else 0.65
            outline.Thickness = if automatic then 3 else 2
            outline.Color = if target then Color3.fromRGB(255,255,255) else ACTION_COLORS.Aim
        end
    end
    function result.SetAutomatic(enabled: boolean)
        automatic = enabled
        paintAim()
    end
    function result.SetAim(selected: Model?)
        target = selected
        paintAim()
    end
    function result.RestStick()
        local size = left.pad.Size.X.Offset
        local bounds = resolve()
        left.pad.Position = UDim2.new(0, bounds.margin + size/2, 1, -bounds.margin - size/2)
        left.pad.BackgroundTransparency = 0.78
        left.thumb.BackgroundTransparency = 0.76
        left.thumb.Position = UDim2.fromScale(0.5, 0.5)
    end
    function result.BeginStick(position: Vector2)
        local localPoint = position - gui.AbsolutePosition
        local half = left.pad.Size.X.Offset/2
        local size = gui.AbsoluteSize
        local x = math.clamp(localPoint.X, half, math.max(half, size.X-half))
        local y = math.clamp(localPoint.Y, half, math.max(half, size.Y-half))
        left.pad.Position = UDim2.fromOffset(x, y)
        left.pad.BackgroundTransparency = 0.34
        left.thumb.BackgroundTransparency = 0.40
    end
    function result.Layout()
        local bounds = resolve()
        result.radius = bounds.radius
        left.pad.Size = UDim2.fromOffset(bounds.stick, bounds.stick)
        left.thumb.Size = UDim2.fromOffset(math.floor(bounds.stick * 0.42), math.floor(bounds.stick * 0.42))
        for _, entry in {{jump, bounds.jump}, {attack, bounds.attack}, {aim, bounds.aim}} do
            local button, box = entry[1], entry[2]
            button.Size = UDim2.fromOffset(box.size, box.size)
            button.Position = UDim2.new(1, -box.x, 1, -box.y)
        end
        for i, button in ipairs(skills) do
            local box = bounds.skills[i]
            button.Size = UDim2.fromOffset(box.size, box.size)
            button.Position = UDim2.new(1, -box.x, 1, -box.y)
        end
        result.RestStick()
    end
    local connection = GuiService:GetPropertyChangedSignal("TopbarInset"):Connect(result.Layout)
    gui.Destroying:Once(function() connection:Disconnect() end)
    paintAim()
    result.Layout()
    return result
end

return table.freeze(View)
