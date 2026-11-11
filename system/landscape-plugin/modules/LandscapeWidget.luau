-- Small self-contained Studio dock. The authoring tool owns all scene changes.
local Adjustments = require(script.Parent.LandscapeAdjustments)
local LandscapeWidget = {}
LandscapeWidget.__index = LandscapeWidget

local BACKGROUND = Color3.fromRGB(14, 22, 30)
local PANEL = Color3.fromRGB(24, 37, 48)
local OUTLINE = Color3.fromRGB(44, 66, 78)
local TEXT = Color3.fromRGB(224, 237, 237)
local MUTED = Color3.fromRGB(153, 174, 185)
local ACCENT = Color3.fromRGB(62, 205, 175)

local function create(class, props, parent)
    local object = Instance.new(class)
    for key, value in pairs(props) do object[key] = value end
    if parent and parent.Name == "LandscapeUI" and object:IsA("GuiObject") then
        object.LayoutOrder = #parent:GetChildren() + 1
    end
    object.Parent = parent
    return object
end

local function rounded(object, radius)
    create("UICorner", {CornerRadius = UDim.new(0, radius or 8)}, object)
end

local function caption(parent, text, height, color)
    return create("TextLabel", {
        BackgroundTransparency = 1,
        Text = text,
        TextColor3 = color or MUTED,
        Font = Enum.Font.Gotham,
        TextSize = 13,
        TextXAlignment = Enum.TextXAlignment.Left,
        TextWrapped = true,
        Size = UDim2.new(1, 0, 0, height or 21),
    }, parent)
end

local function button(parent, text, color, height)
    local control = create("TextButton", {
        BackgroundColor3 = color or PANEL,
        BorderSizePixel = 0,
        AutoButtonColor = true,
        Text = text,
        TextColor3 = if color == ACCENT then BACKGROUND else TEXT,
        Font = Enum.Font.GothamBold,
        TextSize = 13,
        Size = UDim2.new(1, 0, 0, height or 38),
    }, parent)
    rounded(control)
    return control
end

function LandscapeWidget.new(widget, actions)
    local self = setmetatable({}, LandscapeWidget)
    self.actions = actions
    self.thickness = 0.24
    self.level = 0
    self.color = Color3.fromRGB(89, 123, 60)
    self.active = false

    local scroll = create("ScrollingFrame", {
        Name = "LandscapeUI", BackgroundColor3 = BACKGROUND,
        BorderSizePixel = 0, Size = UDim2.fromScale(1, 1),
        ScrollBarThickness = 5, CanvasSize = UDim2.new(0, 0, 0, 0),
        AutomaticCanvasSize = Enum.AutomaticSize.Y,
        ScrollingDirection = Enum.ScrollingDirection.Y,
    }, widget)
    self.content = scroll
    create("UIListLayout", {Padding = UDim.new(0, 10), SortOrder = Enum.SortOrder.LayoutOrder}, scroll)
    create("UIPadding", {
        PaddingTop = UDim.new(0, 13), PaddingBottom = UDim.new(0, 13),
        PaddingLeft = UDim.new(0, 15), PaddingRight = UDim.new(0, 15),
    }, scroll)

    local headline = caption(scroll, "GAME1  /  LANDSCAPE", 22, ACCENT)
    headline.Font = Enum.Font.GothamBold
    headline.TextSize = 13
    local title = caption(scroll, "Декорирование поверхности", 31, TEXT)
    title.Font = Enum.Font.GothamBold
    title.TextSize = 17
    caption(scroll, "01 · Ветка / лиана", 24, MUTED)

    local mode = button(scroll, "Начать · Ветка", ACCENT, 42)
    self.modeButton = mode
    mode.MouseButton1Click:Connect(function()
        actions.toggleMode()
    end)

    local example = create("Frame", {BackgroundColor3 = PANEL, BorderSizePixel = 0,
        Size = UDim2.new(1, 0, 0, 56)}, scroll)
    rounded(example)
    local line = create("Frame", {Name = "BranchSample", BackgroundColor3 = self.color,
        BorderSizePixel = 0, AnchorPoint = Vector2.new(0.5, 0.5),
        Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.new(0.7, 0, 0, 5)}, example)
    rounded(line, 5)
    self.line = line

    self.thicknessSlider = Adjustments.Slider(scroll, {
        label = "Толщина стебля · studs", min = 0.04, max = 4,
        value = self.thickness, step = 0.01, logarithmic = true,
        format = "%.2f", changed = function(value)
            self.thickness = value
            actions.settingsChanged(self.thickness, self.level, self.color)
            self:Refresh()
        end,
    })

    caption(scroll, "Цвет стебля · палитра / выбор оттенка", 20)
    self.colorPicker = Adjustments.Color(scroll, {
        value = self.color,
        presets = {
            Color3.fromRGB(89, 123, 60), Color3.fromRGB(51, 93, 64),
            Color3.fromRGB(128, 95, 58), Color3.fromRGB(87, 65, 49),
            Color3.fromRGB(186, 168, 124), Color3.fromRGB(219, 213, 190),
        },
        changed = function(value)
            self.color = value
            actions.settingsChanged(self.thickness, self.level, self.color)
            self:Refresh()
        end,
    })

    caption(scroll, "Повторение поверхности", 20)
    local levelBar = create("Frame", {BackgroundTransparency = 1, Size = UDim2.new(1, 0, 0, 38)}, scroll)
    local minus = create("TextButton", {Text = "−", BackgroundColor3 = PANEL, TextColor3 = TEXT,
        Font = Enum.Font.GothamBold, TextSize = 22, BorderSizePixel = 0,
        Size = UDim2.new(0, 44, 0, 36)}, levelBar)
    rounded(minus)
    local plus = create("TextButton", {Text = "+", BackgroundColor3 = PANEL, TextColor3 = TEXT,
        Font = Enum.Font.GothamBold, TextSize = 22, BorderSizePixel = 0,
        AnchorPoint = Vector2.new(1, 0), Position = UDim2.fromScale(1, 0),
        Size = UDim2.new(0, 44, 0, 36)}, levelBar)
    rounded(plus)
    local value = create("TextLabel", {BackgroundTransparency = 1, Text = "0",
        TextColor3 = ACCENT, Font = Enum.Font.GothamBold, TextSize = 20,
        Size = UDim2.new(1, -96, 0, 36), Position = UDim2.new(0, 48, 0, 0)}, levelBar)
    self.levelLabel = value
    local explanation = caption(scroll, "0 = прямо · 1 = 2 сегмента · 2 = 4 · 3 = 8 · 4 = 16", 34)
    explanation.TextWrapped = true
    local function changeLevel(delta)
        self.level = math.clamp(self.level + delta, 0, 4)
        actions.settingsChanged(self.thickness, self.level, self.color)
        self:Refresh()
    end
    minus.MouseButton1Click:Connect(function() changeLevel(-1) end)
    plus.MouseButton1Click:Connect(function() changeLevel(1) end)

    local stop = button(scroll, "Завершить · Enter", PANEL, 38)
    stop.MouseButton1Click:Connect(actions.finish)
    self.statusLabel = caption(scroll, "Выбери «Ветка» для размещения", 58, MUTED)
    self.statusLabel.TextWrapped = true
    caption(scroll, "ЛКМ — следующая точка · Enter — закончить · Esc — отменить текущую линию", 52)
    caption(scroll, "Геометрия сохраняется в Workspace / Game1LandscapeDecor / Branches. Ctrl+Z отменяет размещение.", 58)
    self:Refresh()
    return self
end

function LandscapeWidget:Refresh()
    self.colorPicker:Set(self.color)
    self.thicknessSlider:Set(self.thickness)
    self.levelLabel.Text = tostring(self.level)
    self.line.BackgroundColor3 = self.color
    self.line.Size = UDim2.new(0.70, 0, 0, math.clamp(math.floor(self.thickness * 16), 3, 28))
    self.modeButton.Text = if self.active then "● Ветка · размещение активно" else "Начать · Ветка"
    self.modeButton.BackgroundColor3 = if self.active then PANEL else ACCENT
    self.modeButton.TextColor3 = if self.active then ACCENT else BACKGROUND
end

function LandscapeWidget:SetActive(active)
    self.active = active
    self:Refresh()
end

function LandscapeWidget:SetStatus(message)
    self.statusLabel.Text = message
end

return LandscapeWidget
