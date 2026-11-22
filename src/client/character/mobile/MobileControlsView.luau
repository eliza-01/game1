-- Presentation only: one ScreenGui, three actions and a passive floating stick.
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
    x: number, y: number, rotation: number)
    local line = Instance.new("Frame")
    line.Name = name
    line.AnchorPoint = Vector2.new(0.5, 0.5)
    line.Position = UDim2.fromScale(x, y)
    line.Size = UDim2.fromScale(width, height)
    line.Rotation = rotation
    line.BackgroundColor3 = PALETTE.text
    line.BackgroundTransparency = 0.06
    line.BorderSizePixel = 0
    line.Parent = parent
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, 2)
    corner.Parent = line
end

local function makeAction(gui: ScreenGui, name: string): TextButton
    local button = Instance.new("TextButton")
    button.Name = name
    button.AnchorPoint = Vector2.new(1, 1)
    button.BackgroundColor3 = Color3.new(0, 0, 0)
    button.BackgroundTransparency = if name == "Attack" then 0.26 else 0.48
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
    stroke(button, PALETTE.rim, 0.72, 1)
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
        stroke(ring, PALETTE.text, 0.06, 2)
        iconLine(glyph, "ReticleTop", 0.07, 0.21, 0.5, 0.04, 0)
        iconLine(glyph, "ReticleBottom", 0.07, 0.21, 0.5, 0.96, 0)
        iconLine(glyph, "ReticleLeft", 0.21, 0.07, 0.04, 0.5, 0)
        iconLine(glyph, "ReticleRight", 0.21, 0.07, 0.96, 0.5, 0)
    elseif name == "Attack" then
        -- Weapon-specific icons are constructed once in SetWeapon, on equip only.
    else
        -- Familiar Roblox-style upward jump arrow.
        iconLine(glyph, "Stem", 0.15, 0.69, 0.5, 0.55, 0)
        iconLine(glyph, "LeftArrow", 0.15, 0.43, 0.36, 0.30, 45)
        iconLine(glyph, "RightArrow", 0.15, 0.43, 0.64, 0.30, -45)
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
    local result = {gui = gui, left = left, jump = jump, attack = attack, aim = aim, radius = 50}
    local weapon: string? = nil
    function result.SetWeapon(value: any)
        local kind = string.lower(tostring(value or ""))
        if kind ~= "bow" and kind ~= "" then kind = "melee" end
        if kind == weapon then return end
        weapon = kind
        local glyph = attack:FindFirstChild("AttackIcon")
        if not glyph then return end
        glyph:ClearAllChildren()
        if kind == "bow" then
            iconLine(glyph, "BowUpper", 0.12, 0.43, 0.47, 0.24, -38)
            iconLine(glyph, "BowLower", 0.12, 0.43, 0.47, 0.76, 38)
            iconLine(glyph, "BowGrip", 0.12, 0.30, 0.60, 0.50, 0)
            iconLine(glyph, "String", 0.045, 0.80, 0.33, 0.50, 0)
            iconLine(glyph, "Arrow", 0.83, 0.07, 0.51, 0.50, 0)
            iconLine(glyph, "ArrowheadTop", 0.22, 0.07, 0.83, 0.42, 35)
            iconLine(glyph, "ArrowheadBottom", 0.22, 0.07, 0.83, 0.58, -35)
        elseif kind == "" then
            for i = 1, 4 do
                iconLine(glyph, "Knuckle" .. i, 0.16, 0.29, 0.18 + (i-1)*0.18, 0.32, 0)
            end
            iconLine(glyph, "Palm", 0.70, 0.39, 0.48, 0.61, 0)
            iconLine(glyph, "Thumb", 0.19, 0.36, 0.76, 0.59, -25)
        else
            iconLine(glyph, "Blade", 0.16, 0.66, 0.53, 0.34, 45)
            iconLine(glyph, "Crossguard", 0.43, 0.09, 0.37, 0.58, 45)
            iconLine(glyph, "Grip", 0.10, 0.27, 0.22, 0.79, 45)
            iconLine(glyph, "Pommel", 0.19, 0.10, 0.13, 0.89, 45)
        end
    end
    function result.SetAim(selected: Model?)
        aim.BackgroundColor3 = if selected then Color3.fromRGB(28, 113, 104) else PALETTE.background
        aim.BackgroundTransparency = if selected then 0.08 else 0.48
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
        result.RestStick()
    end
    result.SetWeapon("")
    result.Layout()
    return result
end

return table.freeze(View)
