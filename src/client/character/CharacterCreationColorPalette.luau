--!strict
-- Continuous HSV canvas. Preview changes immediately; Apply commits, Cancel restores.
local UserInputService = game:GetService("UserInputService")
local Language = require(script.Parent.Parent:WaitForChild("localization"):WaitForChild("LanguageState"))
local SavedRow = require(script.Parent:WaitForChild("CharacterCreationSavedColorRow"))
local Picker = {}
Picker.__index = Picker

local function hex(color: Color3): string
    return string.format("#%02X%02X%02X", math.round(color.R * 255),
        math.round(color.G * 255), math.round(color.B * 255))
end
local function round(parent: GuiObject, amount: number)
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, amount)
    corner.Parent = parent
end
local function button(parent: Instance, name: string): TextButton
    local result = Instance.new("TextButton")
    result.Name = name
    result.BackgroundColor3 = Color3.fromRGB(57, 76, 79)
    result.TextColor3 = Color3.fromRGB(245, 238, 219)
    result.Font = Enum.Font.GothamBold
    result.TextSize = 15
    result.BorderSizePixel = 0
    result.ZIndex = 36
    result.Parent = parent
    round(result, 9)
    return result
end

function Picker.new(parent: Frame)
    local overlay = Instance.new("ScrollingFrame")
    overlay.Name = "ColorPaletteOverlay"
    overlay.Size = UDim2.fromScale(1, 1)
    overlay.CanvasSize = UDim2.fromOffset(0, 600)
    overlay.ScrollingDirection = Enum.ScrollingDirection.Y
    overlay.ScrollBarThickness = 3
    overlay.BackgroundColor3 = Color3.fromRGB(14, 22, 29)
    overlay.BorderSizePixel = 0
    overlay.Visible = false
    overlay.ZIndex = 30
    overlay.Parent = parent
    round(overlay, 16)
    local title = Instance.new("TextLabel")
    title.Name = "PaletteTitle"
    title.Text = ""
    title.BackgroundTransparency = 1
    title.Position = UDim2.fromOffset(20, 22)
    title.Size = UDim2.new(1, -40, 0, 34)
    title.TextWrapped = true
    title.TextColor3 = Color3.fromRGB(245, 238, 219)
    title.Font = Enum.Font.GothamBold
    title.TextSize = 19
    title.TextXAlignment = Enum.TextXAlignment.Left
    title.ZIndex = 36
    title.Parent = overlay

    local canvas = Instance.new("Frame")
    canvas.Name = "HSVCanvas"
    canvas.Position = UDim2.fromOffset(20, 76)
    canvas.Size = UDim2.new(1, -40, 0, 268)
    canvas.BackgroundColor3 = Color3.new(1, 1, 1)
    canvas.BorderSizePixel = 0
    canvas.ZIndex = 31
    canvas.Parent = overlay
    round(canvas, 9)
    local rainbow = Instance.new("UIGradient")
    rainbow.Color = ColorSequence.new({
        ColorSequenceKeypoint.new(0, Color3.fromHSV(0, 1, 1)),
        ColorSequenceKeypoint.new(1 / 6, Color3.fromHSV(1 / 6, 1, 1)),
        ColorSequenceKeypoint.new(2 / 6, Color3.fromHSV(2 / 6, 1, 1)),
        ColorSequenceKeypoint.new(3 / 6, Color3.fromHSV(3 / 6, 1, 1)),
        ColorSequenceKeypoint.new(4 / 6, Color3.fromHSV(4 / 6, 1, 1)),
        ColorSequenceKeypoint.new(5 / 6, Color3.fromHSV(5 / 6, 1, 1)),
        ColorSequenceKeypoint.new(1, Color3.fromHSV(0, 1, 1)),
    })
    rainbow.Rotation = 0
    rainbow.Parent = canvas
    local whiten = Instance.new("Frame")
    whiten.Name = "SaturationOverlay"
    whiten.BackgroundColor3 = Color3.new(1, 1, 1)
    whiten.BorderSizePixel = 0
    whiten.Size = UDim2.fromScale(1, 1)
    whiten.ZIndex = 32
    whiten.Parent = canvas
    round(whiten, 9)
    local saturationGradient = Instance.new("UIGradient")
    saturationGradient.Rotation = 90
    saturationGradient.Transparency = NumberSequence.new({
        NumberSequenceKeypoint.new(0, 0),
        NumberSequenceKeypoint.new(1, 1),
    })
    saturationGradient.Parent = whiten
    local darken = Instance.new("Frame")
    darken.Name = "BrightnessOverlay"
    darken.BackgroundColor3 = Color3.new(0, 0, 0)
    darken.BorderSizePixel = 0
    darken.Size = UDim2.fromScale(1, 1)
    darken.ZIndex = 33
    darken.BackgroundTransparency = 1
    darken.Parent = canvas
    round(darken, 9)
    local cursor = Instance.new("Frame")
    cursor.Name = "ColorCursor"
    cursor.AnchorPoint = Vector2.new(0.5, 0.5)
    cursor.Size = UDim2.fromOffset(18, 18)
    cursor.BackgroundTransparency = 1
    cursor.ZIndex = 35
    cursor.Parent = canvas
    local outline = Instance.new("UIStroke")
    outline.Color = Color3.new(1, 1, 1)
    outline.Thickness = 3
    outline.Parent = cursor
    round(cursor, 12)
    local hit = button(canvas, "ColorCanvasInput")
    hit.BackgroundTransparency = 1
    hit.Text = ""
    hit.Size = UDim2.fromScale(1, 1)
    hit.ZIndex = 34

    local valueBar = Instance.new("Frame")
    valueBar.Name = "BrightnessBar"
    valueBar.Position = UDim2.fromOffset(20, 362)
    valueBar.Size = UDim2.new(1, -40, 0, 28)
    valueBar.BackgroundColor3 = Color3.new(1, 1, 1)
    valueBar.ZIndex = 31
    valueBar.Parent = overlay
    round(valueBar, 8)
    local valueGradient = Instance.new("UIGradient")
    valueGradient.Color = ColorSequence.new(Color3.new(0, 0, 0), Color3.new(1, 1, 1))
    valueGradient.Parent = valueBar
    -- The handle represents HSV value, independently of the hue/saturation cursor.
    local valueCursor = Instance.new("Frame")
    valueCursor.Name = "BrightnessCursor"
    valueCursor.AnchorPoint = Vector2.new(0.5, 0.5)
    valueCursor.Size = UDim2.fromOffset(18, 34)
    valueCursor.BackgroundColor3 = Color3.fromRGB(245, 238, 219)
    valueCursor.BorderSizePixel = 0
    valueCursor.ZIndex = 36
    valueCursor.Parent = valueBar
    round(valueCursor, 5)
    local valueOutline = Instance.new("UIStroke")
    valueOutline.Color = Color3.fromRGB(25, 34, 40)
    valueOutline.Thickness = 2
    valueOutline.Parent = valueCursor
    local valueHit = button(valueBar, "BrightnessInput")
    valueHit.Text = ""
    valueHit.BackgroundTransparency = 1
    valueHit.Position = UDim2.fromOffset(-9, -3)
    valueHit.Size = UDim2.new(1, 18, 1, 6)
    valueHit.ZIndex = 37
    valueHit.AutoButtonColor = false

    local field = Instance.new("TextBox")
    field.Name = "HexColorInput"
    field.Position = UDim2.fromOffset(20, 408)
    field.Size = UDim2.new(1, -110, 0, 43)
    field.TextColor3 = Color3.fromRGB(248, 241, 221)
    field.BackgroundColor3 = Color3.fromRGB(46, 59, 68)
    field.Font = Enum.Font.GothamBold
    field.TextSize = 18
    field.ClearTextOnFocus = false
    field.PlaceholderText = "#RRGGBB"
    field.ZIndex = 35
    field.Parent = overlay
    round(field, 8)
    local preview = Instance.new("Frame")
    preview.Name = "SelectedColor"
    preview.Position = UDim2.new(1, -77, 0, 408)
    preview.Size = UDim2.fromOffset(57, 43)
    preview.ZIndex = 35
    preview.Parent = overlay
    round(preview, 8)
    local saved = SavedRow.Create(overlay, 35)
    saved.Position = UDim2.fromOffset(20, 460)
    saved.Size = UDim2.new(1, -110, 0, 46)
    local save = button(overlay, "SaveCustomColor")
    save.Position = UDim2.new(1, -77, 0, 460)
    save.Size = UDim2.fromOffset(57, 43)
    save.Text = "💾"
    save.TextSize = 23
    local saveStatus = Instance.new("TextLabel")
    saveStatus.Name = "SavedColorStatus"
    saveStatus.BackgroundTransparency = 1
    saveStatus.Position = UDim2.fromOffset(20, 509)
    saveStatus.Size = UDim2.new(1, -40, 0, 24)
    saveStatus.TextColor3 = Color3.fromRGB(198, 207, 210)
    saveStatus.TextSize = 12
    saveStatus.Font = Enum.Font.GothamBold
    saveStatus.TextWrapped = true
    saveStatus.Text = ""
    saveStatus.ZIndex = 36
    saveStatus.Parent = overlay
    local apply = button(overlay, "ApplyColor")
    apply.Position = UDim2.fromOffset(20, 540)
    apply.Size = UDim2.new(0.5, -25, 0, 46)
    apply.BackgroundColor3 = Color3.fromRGB(76, 120, 100)
    local cancel = button(overlay, "CancelColor")
    cancel.Position = UDim2.new(0.5, 5, 0, 540)
    cancel.Size = UDim2.new(0.5, -25, 0, 46)

    local h, s, v = 0, 0, 1
    local onSave: ((string) -> ())? = nil
    local savedColors: {string} = {}
    local onPreview: ((string) -> ())? = nil
    local onCommit: ((string) -> ())? = nil
    local onCancel: (() -> ())? = nil
    local dragging: string? = nil
    local pointer: InputObject? = nil
    local function releasePointer()
        dragging = nil
        pointer = nil
        overlay.ScrollingEnabled = true
    end
    overlay:GetPropertyChangedSignal("Visible"):Connect(function()
        if not overlay.Visible then releasePointer() end
    end)
    UserInputService.WindowFocusReleased:Connect(releasePointer)
    local function display(emit: boolean)
        local chosen = hex(Color3.fromHSV(h, s, v))
        preview.BackgroundColor3 = Color3.fromHSV(h, s, v)
        field.Text = chosen
        SavedRow.Select(saved, chosen)
        cursor.Position = UDim2.fromScale(h, 1 - s)
        valueCursor.Position = UDim2.fromScale(v, 0.5)
        darken.BackgroundTransparency = v
        if emit and onPreview then onPreview(chosen) end
    end
    local function setHex(value: string, emit: boolean)
        if not string.match(value, "^#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]$") then return false end
        local parsed = Color3.fromHex(value)
        h, s, v = parsed:ToHSV()
        display(emit)
        return true
    end
    local function updateSaved(colors: {string})
        savedColors = colors
        SavedRow.Render(saved, savedColors, hex(Color3.fromHSV(h, s, v)), function(value)
            setHex(value, true)
        end)
    end
    save.Activated:Connect(function()
        if not overlay.Visible or not save.Active or not onSave then return end
        if setHex(field.Text, true) then onSave(hex(Color3.fromHSV(h, s, v))) end
    end)
    local function coordinate(which: string, position: Vector2)
        local object = if which == "canvas" then canvas else valueBar
        local size = object.AbsoluteSize
        if size.X < 1 or size.Y < 1 then return end
        local x = math.clamp((position.X - object.AbsolutePosition.X) / size.X, 0, 1)
        if which == "canvas" then
            h = math.min(x, 0.9999)
            s = 1 - math.clamp((position.Y - object.AbsolutePosition.Y) / size.Y, 0, 1)
        else
            v = x
        end
        display(true)
    end
    local function attach(buttonObject: TextButton, which: string)
        buttonObject.InputBegan:Connect(function(input)
            if overlay.Visible and not pointer and (input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch) then
                pointer = input
                dragging = which
                overlay.ScrollingEnabled = false
                coordinate(which, Vector2.new(input.Position.X, input.Position.Y))
            end
        end)
    end
    attach(hit, "canvas")
    attach(valueHit, "brightness")
    UserInputService.InputChanged:Connect(function(input)
        if overlay.Visible and dragging and pointer and (input == pointer
            or (pointer.UserInputType == Enum.UserInputType.MouseButton1 and input.UserInputType == Enum.UserInputType.MouseMovement)) then
            coordinate(dragging, Vector2.new(input.Position.X, input.Position.Y))
        end
    end)
    UserInputService.InputEnded:Connect(function(input)
        if pointer and (input == pointer or (pointer.UserInputType == Enum.UserInputType.MouseButton1
            and input.UserInputType == Enum.UserInputType.MouseButton1)) then releasePointer() end
    end)
    field.FocusLost:Connect(function()
        if not setHex(field.Text, true) then display(false) end
    end)
    apply.Activated:Connect(function()
        if not overlay.Visible then return end
        setHex(field.Text, true)
        overlay.Visible = false
        if onCommit then onCommit(hex(Color3.fromHSV(h, s, v))) end
        onPreview, onCommit, onCancel, onSave = nil, nil, nil, nil
    end)
    cancel.Activated:Connect(function()
        overlay.Visible = false
        if onCancel then onCancel() end
        onPreview, onCommit, onCancel, onSave = nil, nil, nil, nil
    end)
    return setmetatable({root = overlay, apply = apply, cancel = cancel, title = title,
        save = save, saveStatus = saveStatus, updateSaved = updateSaved,
        setSaveCallback = function(callback) onSave = callback end,
        setHex = setHex, setCallbacks = function(previewCallback, commitCallback, cancelCallback)
            onPreview, onCommit, onCancel = previewCallback, commitCallback, cancelCallback
        end, cancelPreview = function() if onCancel then onCancel() end end}, Picker)
end

function Picker:Open(current: string?, onPreview: (string) -> (), onCommit: (string) -> (), onCancel: () -> (),
    titleText: string, onSave: (string) -> ())
    self.setCallbacks(onPreview, onCommit, onCancel)
    self.setSaveCallback(onSave)
    self.title.Text = titleText
    self.root.CanvasPosition = Vector2.zero
    self.root.Visible = true
    self.setHex(if type(current) == "string" then current else "#765034", false)
    self.apply.Text = Language.Translate("creation.palette_apply")
    self.cancel.Text = Language.Translate("feedback.cancel")
end
function Picker:SetSavedColors(colors: {string})
    self.updateSaved(colors)
end
function Picker:SetSaving(busy: boolean, statusKey: string?)
    self.save.Active = not busy
    self.save.AutoButtonColor = not busy
    self.save.TextTransparency = if busy then 0.5 else 0
    self.saveStatus.Text = if statusKey then Language.Translate(statusKey) else ""
end
function Picker:Close()
    if self.root.Visible then self.cancelPreview() end
    self.root.Visible = false
    self.setCallbacks(nil, nil, nil)
    self.setSaveCallback(nil)
end
return Picker
