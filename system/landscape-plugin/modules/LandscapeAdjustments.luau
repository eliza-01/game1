-- Shared direct-manipulation controls for Landscape Painter. No Workspace ownership.
-- Pointer drag is tracked on UserInputService so it continues outside the track.
local UserInputService = game:GetService("UserInputService")
local Adjustments = {}
local BG = Color3.fromRGB(24, 37, 48)
local TEXT = Color3.fromRGB(224, 237, 237)
local MUTED = Color3.fromRGB(153, 174, 185)
local ACCENT = Color3.fromRGB(62, 205, 175)

local function make(class, props, parent)
    local instance = Instance.new(class)
    for key, value in pairs(props) do instance[key] = value end
    instance.Parent = parent
    return instance
end

local function round(frame, radius)
    make("UICorner", {CornerRadius = UDim.new(0, radius or 7)}, frame)
end

function Adjustments.Slider(parent, options)
    local minimum, maximum = options.min, options.max
    local step = options.step or 0
    local logarithmic = options.logarithmic == true
    assert(maximum > minimum and (not logarithmic or minimum > 0), "invalid slider range")
    local frame = make("Frame", {BackgroundTransparency = 1, Size = UDim2.new(1, 0, 0, 65)}, parent)
    if parent.Name == "LandscapeUI" then frame.LayoutOrder = #parent:GetChildren() end
    local heading = make("TextLabel", {BackgroundTransparency = 1, Text = options.label,
        TextColor3 = MUTED, Font = Enum.Font.Gotham, TextSize = 12,
        TextXAlignment = Enum.TextXAlignment.Left, Size = UDim2.new(1, -78, 0, 25)}, frame)
    local valueButton = make("TextButton", {Text = "", BackgroundColor3 = BG,
        TextColor3 = TEXT, BorderSizePixel = 0, AutoButtonColor = true,
        Font = Enum.Font.Code, TextSize = 13, Size = UDim2.fromOffset(76, 27),
        AnchorPoint = Vector2.new(1, 0), Position = UDim2.fromScale(1, 0)}, frame)
    round(valueButton, 6)
    local exact = make("TextBox", {Visible = false, BackgroundColor3 = BG,
        TextColor3 = ACCENT, BorderSizePixel = 0, ClearTextOnFocus = false,
        Font = Enum.Font.Code, TextSize = 13, Size = UDim2.fromScale(1, 1)}, valueButton)
    local track = make("TextButton", {Text = "", BackgroundColor3 = BG,
        BorderSizePixel = 0, Active = true, AutoButtonColor = false,
        Size = UDim2.new(1, -16, 0, 17), Position = UDim2.fromOffset(8, 39)}, frame)
    round(track, 9)
    local fill = make("Frame", {BackgroundColor3 = ACCENT, BorderSizePixel = 0,
        Size = UDim2.fromScale(0, 1)}, track)
    round(fill, 9)
    local thumb = make("Frame", {BackgroundColor3 = TEXT, BorderSizePixel = 0,
        Size = UDim2.fromOffset(16, 16), AnchorPoint = Vector2.new(0.5, 0.5),
        Position = UDim2.fromScale(0, 0.5), ZIndex = 2}, track)
    round(thumb, 8)
    -- Transparent input layer stays above the handle/fill, so dragging starts
    -- on the thumb too (GUI children do not steal pointer events).
    local hitbox = make("TextButton", {Text = "", BackgroundTransparency = 1,
        AutoButtonColor = false, BorderSizePixel = 0, Active = true,
        ZIndex = 5, Size = UDim2.fromScale(1, 1)}, track)
    local value = options.value or minimum
    local dragging = false
    local activeTouch = nil
    local connections = {}
    local function fraction(number)
        local ratio = if logarithmic then
            math.log(number / minimum) / math.log(maximum / minimum)
            else (number - minimum) / (maximum - minimum)
        return math.clamp(ratio, 0, 1)
    end
    local function fromFraction(ratio)
        local raw = if logarithmic then minimum * (maximum / minimum) ^ ratio
            else minimum + (maximum - minimum) * ratio
        if step > 0 then raw = math.floor(raw / step + 0.5) * step end
        return math.clamp(raw, minimum, maximum)
    end
    local function redraw()
        local ratio = fraction(value)
        fill.Size = UDim2.fromScale(ratio, 1)
        thumb.Position = UDim2.fromScale(ratio, 0.5)
        valueButton.Text = string.format(options.format or "%.2f", value) .. (options.suffix or "")
    end
    local function setValue(nextValue, notify)
        if typeof(nextValue) ~= "number" or nextValue ~= nextValue then return end
        nextValue = math.clamp(nextValue, minimum, maximum)
        if step > 0 then nextValue = math.clamp(math.floor(nextValue / step + 0.5) * step, minimum, maximum) end
        local changed = math.abs(value - nextValue) > 0.000001
        value = nextValue
        redraw()
        if changed and notify then options.changed(value) end
    end
    local function drag(position)
        local width = math.max(1, track.AbsoluteSize.X)
        setValue(fromFraction(math.clamp((position.X - track.AbsolutePosition.X) / width, 0, 1)), true)
    end
    table.insert(connections, hitbox.InputBegan:Connect(function(input)
        if input.UserInputType == Enum.UserInputType.MouseButton1 then
            dragging = true
            drag(input.Position)
        elseif input.UserInputType == Enum.UserInputType.Touch then
            activeTouch = input
            drag(input.Position)
        end
    end))
    table.insert(connections, UserInputService.InputChanged:Connect(function(input)
        if (dragging and input.UserInputType == Enum.UserInputType.MouseMovement) or input == activeTouch then
            drag(input.Position)
        end
    end))
    table.insert(connections, UserInputService.InputEnded:Connect(function(input)
        if input.UserInputType == Enum.UserInputType.MouseButton1 then dragging = false end
        if input == activeTouch then activeTouch = nil end
    end))
    table.insert(connections, valueButton.MouseButton1Click:Connect(function()
        exact.Text = tostring(value)
        exact.Visible = true
        exact:CaptureFocus()
    end))
    table.insert(connections, exact.FocusLost:Connect(function()
        local parsed = tonumber(exact.Text)
        if parsed then setValue(parsed, true) end
        exact.Visible = false
    end))
    table.insert(connections, frame.Destroying:Connect(function()
        for _, connection in ipairs(connections) do connection:Disconnect() end
    end))
    redraw()
    return {frame = frame, Set = function(_, number) setValue(number, false) end,
        Get = function() return value end}
end

-- Compact HSV picker: presets for common work, a hue strip and an SV plane
-- for any other color. Exact hex input is available, but never required.
function Adjustments.Color(parent, options)
    local picker = make("Frame", {BackgroundTransparency = 1, Size = UDim2.new(1, 0, 0, 192)}, parent)
    if parent.Name == "LandscapeUI" then picker.LayoutOrder = #parent:GetChildren() end
    local presets = make("Frame", {BackgroundTransparency = 1, Size = UDim2.new(1, 0, 0, 30)}, picker)
    make("UIListLayout", {FillDirection = Enum.FillDirection.Horizontal,
        Padding = UDim.new(0, 5), SortOrder = Enum.SortOrder.LayoutOrder}, presets)
    local hue, saturation, brightness = options.value:ToHSV()
    local value = options.value
    local swatches = {}
    local redraw
    local function publish()
        local nextValue = Color3.fromHSV(hue, saturation, brightness)
        if nextValue ~= value then
            value = nextValue
            options.changed(value)
        end
    end
    local function setColor(nextValue, notify)
        if typeof(nextValue) ~= "Color3" then return end
        hue, saturation, brightness = nextValue:ToHSV()
        value = nextValue
        if notify then options.changed(value) end
    end
    for index, rgb in ipairs(options.presets or {}) do
        local item = make("TextButton", {Text = "", BackgroundColor3 = rgb,
            BorderSizePixel = 0, AutoButtonColor = true, LayoutOrder = index,
            Size = UDim2.fromOffset(26, 26)}, presets)
        round(item, 6)
        swatches[index] = item
        item.MouseButton1Click:Connect(function() setColor(rgb, true); redraw() end)
    end
    local plane = make("TextButton", {Text = "", BorderSizePixel = 0, Active = true,
        AutoButtonColor = false, Position = UDim2.fromOffset(3, 36),
        Size = UDim2.new(1, -6, 0, 91)}, picker)
    round(plane, 5)
    local white = make("Frame", {Size = UDim2.fromScale(1, 1), BackgroundColor3 = Color3.new(1, 1, 1),
        BorderSizePixel = 0}, plane)
    make("UIGradient", {Transparency = NumberSequence.new({NumberSequenceKeypoint.new(0, 0), NumberSequenceKeypoint.new(1, 1)})}, white)
    local shade = make("Frame", {Size = UDim2.fromScale(1, 1), BackgroundColor3 = Color3.new(0, 0, 0),
        BorderSizePixel = 0}, plane)
    make("UIGradient", {Rotation = 90, Transparency = NumberSequence.new({NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(1, 0)})}, shade)
    local cursor = make("Frame", {Size = UDim2.fromOffset(12, 12),
        AnchorPoint = Vector2.new(0.5, 0.5), BackgroundColor3 = TEXT,
        BorderSizePixel = 0, ZIndex = 4}, plane)
    round(cursor, 6)
    local planeHitbox = make("TextButton", {Text = "", BackgroundTransparency = 1,
        BorderSizePixel = 0, AutoButtonColor = false, Active = true,
        ZIndex = 6, Size = UDim2.fromScale(1, 1)}, plane)
    local hueTrack = make("TextButton", {Text = "", BorderSizePixel = 0,
        AutoButtonColor = false, Active = true, BackgroundColor3 = Color3.new(1, 1, 1),
        Size = UDim2.new(1, -6, 0, 16), Position = UDim2.fromOffset(3, 135)}, picker)
    round(hueTrack, 6)
    make("UIGradient", {Color = ColorSequence.new({
        ColorSequenceKeypoint.new(0, Color3.fromHSV(0, 1, 1)),
        ColorSequenceKeypoint.new(1/6, Color3.fromHSV(1/6, 1, 1)),
        ColorSequenceKeypoint.new(2/6, Color3.fromHSV(2/6, 1, 1)),
        ColorSequenceKeypoint.new(3/6, Color3.fromHSV(3/6, 1, 1)),
        ColorSequenceKeypoint.new(4/6, Color3.fromHSV(4/6, 1, 1)),
        ColorSequenceKeypoint.new(5/6, Color3.fromHSV(5/6, 1, 1)),
        ColorSequenceKeypoint.new(1, Color3.fromHSV(1, 1, 1)),
    })}, hueTrack)
    local hueCursor = make("Frame", {Size = UDim2.fromOffset(9, 22),
        AnchorPoint = Vector2.new(0.5, 0.5), BackgroundColor3 = TEXT,
        BorderSizePixel = 0, ZIndex = 3}, hueTrack)
    round(hueCursor, 5)
    local hueHitbox = make("TextButton", {Text = "", BackgroundTransparency = 1,
        BorderSizePixel = 0, AutoButtonColor = false, Active = true,
        ZIndex = 6, Size = UDim2.fromScale(1, 1)}, hueTrack)
    local hexButton = make("TextButton", {Text = "", TextColor3 = TEXT,
        BackgroundColor3 = BG, BorderSizePixel = 0, Font = Enum.Font.Code,
        TextSize = 13, Size = UDim2.new(1, 0, 0, 30),
        Position = UDim2.fromOffset(0, 158)}, picker)
    round(hexButton, 6)
    local hexExact = make("TextBox", {Visible = false, ClearTextOnFocus = false,
        TextColor3 = TEXT, BackgroundColor3 = BG, BorderSizePixel = 0,
        Font = Enum.Font.Code, TextSize = 13, Size = UDim2.fromScale(1, 1)}, hexButton)
    local dragKind = nil
    local dragTouch = nil
    local connections = {}
    redraw = function()
        plane.BackgroundColor3 = Color3.fromHSV(hue, 1, 1)
        cursor.Position = UDim2.fromScale(saturation, 1 - brightness)
        hueCursor.Position = UDim2.fromScale(hue, 0.5)
        hexButton.Text = "●  #" .. value:ToHex():upper() .. "  ·  нажми для HEX"
    end
    local function applyPointer(kind, position)
        local target = if kind == "hue" then hueTrack else plane
        local x = math.clamp((position.X - target.AbsolutePosition.X) / math.max(1, target.AbsoluteSize.X), 0, 1)
        if kind == "hue" then hue = x % 1 else
            saturation = x
            brightness = 1 - math.clamp((position.Y - target.AbsolutePosition.Y) / math.max(1, target.AbsoluteSize.Y), 0, 1)
        end
        publish()
        redraw()
    end
    for _, pair in ipairs({{planeHitbox, "sv"}, {hueHitbox, "hue"}}) do
        local target, kind = pair[1], pair[2]
        table.insert(connections, target.InputBegan:Connect(function(input)
            if input.UserInputType == Enum.UserInputType.MouseButton1 then
                dragKind = kind
                applyPointer(kind, input.Position)
            elseif input.UserInputType == Enum.UserInputType.Touch then
                dragKind = kind
                dragTouch = input
                applyPointer(kind, input.Position)
            end
        end))
    end
    table.insert(connections, UserInputService.InputChanged:Connect(function(input)
        if dragKind and (input == dragTouch or (not dragTouch and input.UserInputType == Enum.UserInputType.MouseMovement)) then
            applyPointer(dragKind, input.Position)
        end
    end))
    table.insert(connections, UserInputService.InputEnded:Connect(function(input)
        if input == dragTouch or (not dragTouch and input.UserInputType == Enum.UserInputType.MouseButton1) then
            dragKind = nil
            dragTouch = nil
        end
    end))
    table.insert(connections, hexButton.MouseButton1Click:Connect(function()
        hexExact.Text = "#" .. value:ToHex():upper()
        hexExact.Visible = true
        hexExact:CaptureFocus()
    end))
    table.insert(connections, hexExact.FocusLost:Connect(function()
        local text = hexExact.Text
        if text:match("^#?%x%x%x%x%x%x$") then
            setColor(Color3.fromHex(if text:sub(1, 1) == "#" then text else "#" .. text), true)
        end
        hexExact.Visible = false
        redraw()
    end))
    -- Preset buttons share this refresh path with external Set calls.
    table.insert(connections, picker.Destroying:Connect(function()
        for _, connection in ipairs(connections) do connection:Disconnect() end
    end))
    redraw()
    return {frame = picker, Set = function(_, color) setColor(color, false); redraw() end,
        Get = function() return value end}
end

return table.freeze(Adjustments)
