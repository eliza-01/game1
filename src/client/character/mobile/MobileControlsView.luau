-- Presentation only: combat buttons, reserved skill cells, and passive floating stick.
local Layout = require(script.Parent:WaitForChild("MobileLayout"))
local View = {}

local PALETTE = {
    background = Color3.fromRGB(0, 0, 0),
    rim = Color3.fromRGB(240, 240, 240),
    thumb = Color3.fromRGB(255, 255, 255),
    text = Color3.fromRGB(244, 251, 249),
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

-- Icons are vector-like Roblox UI primitives, not asset IDs or text glyphs.
-- Their images therefore work on a fresh device without uploading textures.
local function iconLine(parent: Instance, name: string, width: number, height: number,
    x: number, y: number, rotation: number, color: Color3?)
    local line = Instance.new("Frame")
    line.Name = name
    line.AnchorPoint = Vector2.new(0.5, 0.5)
    line.Position = UDim2.fromScale(x, y)
    line.Size = UDim2.fromScale(width, height)
    line.Rotation = rotation
    line.BackgroundColor3 = color or PALETTE.text
    line.BackgroundTransparency = 0.06
    line.BorderSizePixel = 0
    line.Parent = parent
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, 2)
    corner.Parent = line
end

local ACTION_COLORS = {
    Attack = Color3.fromRGB(255, 255, 255),
    Jump = Color3.fromRGB(0, 166, 222),
    Aim = Color3.fromRGB(27, 183, 83),
    Skill = Color3.fromRGB(255, 133, 37),
}
local function makeAction(gui: ScreenGui, name: string): TextButton
    local button = Instance.new("TextButton")
    button.Name = name
    button.AnchorPoint = Vector2.new(1, 1)
    local isSkill = string.sub(name, 1, 5) == "Skill"
    button.BackgroundColor3 = Color3.new(1, 1, 1)
    button.BackgroundTransparency = if isSkill then 0.35 else 0.06
    button.BorderSizePixel = 0
    button.AutoButtonColor = true
    button.Text = ""
    button.Active = true
    button.Selectable = false
    button.ZIndex = 3
    button.Parent = gui
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(1, 0)
    corner.Parent = button
    stroke(button, if isSkill then ACTION_COLORS.Skill elseif name == "Attack" then Color3.new(0,0,0) else ACTION_COLORS[name], 0, 3)
    local glyph = Instance.new("Frame")
    glyph.Name = name .. "Icon"
    glyph.AnchorPoint = Vector2.new(0.5, 0.5)
    glyph.Position = UDim2.fromScale(0.5, 0.5)
    glyph.Size = UDim2.fromScale(0.6, 0.6)
    glyph.BackgroundTransparency = 1
    glyph.Parent = button
    if name == "Aim" then
        -- Reticle glyph, distinct from attack and jump.
        local ring = Instance.new("Frame")
        ring.Name = "ReticleRing"
        ring.AnchorPoint = Vector2.new(0.5, 0.5)
        ring.Position = UDim2.fromScale(0.5, 0.5)
        ring.Size = UDim2.fromScale(0.65, 0.65)
        ring.BackgroundTransparency = 1
        ring.Parent = glyph
        local round = Instance.new("UICorner")
        round.CornerRadius = UDim.new(1, 0)
        round.Parent = ring
        stroke(ring, ACTION_COLORS.Aim, 0.06, 2)
        iconLine(glyph, "ReticleTop", 0.07, 0.21, 0.5, 0.04, 0, ACTION_COLORS.Aim)
        iconLine(glyph, "ReticleBottom", 0.07, 0.21, 0.5, 0.96, 0, ACTION_COLORS.Aim)
        iconLine(glyph, "ReticleLeft", 0.21, 0.07, 0.04, 0.5, 0, ACTION_COLORS.Aim)
        iconLine(glyph, "ReticleRight", 0.21, 0.07, 0.96, 0.5, 0, ACTION_COLORS.Aim)
    elseif name == "Attack" then
        iconLine(glyph, "AttackSlash", 0.12, 0.80, 0.5, 0.5, 45, Color3.fromRGB(221, 31, 39))
    elseif name == "Jump" then
        -- Familiar Roblox-style upward jump arrow.
        iconLine(glyph, "Stem", 0.15, 0.69, 0.5, 0.55, 0, ACTION_COLORS.Jump)
        iconLine(glyph, "LeftArrow", 0.15, 0.43, 0.36, 0.30, 45, ACTION_COLORS.Jump)
        iconLine(glyph, "RightArrow", 0.15, 0.43, 0.64, 0.30, -45, ACTION_COLORS.Jump)
    end
    return button
end


function View.Create(playerGui: PlayerGui)
    local gui = Instance.new("ScreenGui")
    gui.Name = "Game1MobileControls"
    gui.ResetOnSpawn = false
    gui.ScreenInsets = Enum.ScreenInsets.CoreUISafeInsets
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
    local function paintAim()
        aim.BackgroundColor3 = if automatic then ACTION_COLORS.Aim else Color3.new(1,1,1)
        aim.BackgroundTransparency = 0.06
        local glyph = aim:FindFirstChild("AimIcon")
        if glyph then
            local color = if automatic then Color3.new(1,1,1) else ACTION_COLORS.Aim
            for _, item in glyph:GetDescendants() do
                if item:IsA("UIStroke") then item.Color = color
                elseif item:IsA("Frame") and item.Name ~= "ReticleRing" then item.BackgroundColor3 = color end
            end
        end
        local outline = aim:FindFirstChildOfClass("UIStroke")
        if outline then
            outline.Transparency = 0
            outline.Thickness = 3
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
        local bounds = Layout.Resolve(gui.AbsoluteSize.X, gui.AbsoluteSize.Y)
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
        local bounds = Layout.Resolve(gui.AbsoluteSize.X, gui.AbsoluteSize.Y)
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
    paintAim()
    result.Layout()
    return result
end

return table.freeze(View)
