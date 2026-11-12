-- Catalog/pivot/profile controls for the independent Landscape Painter dock.
-- Widgets emit actions; they never mutate Workspace or the asset registry.
local Adjustments = require(script.Parent.LandscapeAdjustments)
local AssetsWidget = {}
AssetsWidget.__index = AssetsWidget
local PANEL = Color3.fromRGB(24, 37, 48)
local TEXT = Color3.fromRGB(224, 237, 237)
local MUTED = Color3.fromRGB(153, 174, 185)
local ACCENT = Color3.fromRGB(62, 205, 175)

local function add(kind, props, parent)
    local object = Instance.new(kind)
    for key, value in pairs(props) do object[key] = value end
    if parent and parent.Name == "LandscapeUI" and object:IsA("GuiObject") then
        object.LayoutOrder = #parent:GetChildren() + 1
    end
    object.Parent = parent
    return object
end
local function label(parent, message, height, color)
    return add("TextLabel", {BackgroundTransparency = 1, Text = message,
        TextColor3 = color or MUTED, TextWrapped = true,
        TextXAlignment = Enum.TextXAlignment.Left, Font = Enum.Font.Gotham,
        TextSize = 12, Size = UDim2.new(1, 0, 0, height or 24)}, parent)
end
local function button(parent, title, height)
    local control = add("TextButton", {Text = title, TextColor3 = TEXT,
        BackgroundColor3 = PANEL, Font = Enum.Font.GothamBold,
        TextSize = 13, BorderSizePixel = 0, AutoButtonColor = true,
        Size = UDim2.new(1, 0, 0, height or 36)}, parent)
    add("UICorner", {CornerRadius = UDim.new(0, 7)}, control)
    return control
end
local function field(parent, value)
    local control = add("TextBox", {Text = value, TextColor3 = TEXT,
        BackgroundColor3 = PANEL, BorderSizePixel = 0,
        TextSize = 13, Font = Enum.Font.Code, ClearTextOnFocus = false,
        Size = UDim2.new(1, 0, 0, 34)}, parent)
    add("UICorner", {CornerRadius = UDim.new(0, 7)}, control)
    return control
end
local function section(parent, title)
    local header = label(parent, title, 27, ACCENT)
    header.Font = Enum.Font.GothamBold
    return header
end
local function scrollList(parent, height)
    local frame = add("ScrollingFrame", {BackgroundTransparency = 1,
        BorderSizePixel = 0, ScrollBarThickness = 4,
        Size = UDim2.new(1, 0, 0, height),
        AutomaticCanvasSize = Enum.AutomaticSize.Y,
        ScrollingDirection = Enum.ScrollingDirection.Y,
        CanvasSize = UDim2.fromOffset(0, 0)}, parent)
    add("UIListLayout", {SortOrder = Enum.SortOrder.LayoutOrder,
        Padding = UDim.new(0, 5)}, frame)
    return frame
end
local function clearChildren(frame)
    for _, child in ipairs(frame:GetChildren()) do
        if child:IsA("GuiObject") then child:Destroy() end
    end
end

function AssetsWidget.new(parent, actions)
    local self = setmetatable({}, AssetsWidget)
    self.actions = actions
    self.rows = {}
    self.profiles = {}
    self.selectedSlug = nil
    self.selectedProfile = nil
    self.activeId = nil
    self.active = false
    self.targetMode = "auto"
    self.config = {yaw = 0, pitch = 0, roll = 0,
        tetherEnabled = false, swayEnabled = false, length = 2, thickness = 0.02,
        color = "#343B38"}

    section(parent, "02 · Ассеты · прицел / Pivot")
    self.mode = button(parent, "Начать · Размещение ассета", 41)
    self.mode.MouseButton1Click:Connect(actions.toggleAsset)
    self.modeStatus = label(parent, "Выбери ассет, затем нажми «Начать»", 54, MUTED)
    self.target = button(parent, "Прицел: Авто · стебель / поверхность", 35)
    self.target.MouseButton1Click:Connect(function()
        self.targetMode = if self.targetMode == "auto" then "stem"
            elseif self.targetMode == "stem" then "surface" else "auto"
        actions.targetModeChanged(self.targetMode)
        self:Refresh()
    end)
    label(parent, "Авто находит Stem_XX даже у старых веток без CanQuery. Стебель — только ветки; Поверхность — стены/земля.", 50)
    label(parent, "Опубликованные Location Assets — тот же каталог, что у DecoManager", 37)
    local reload = button(parent, "Обновить каталог", 33)
    reload.MouseButton1Click:Connect(actions.refreshCatalog)
    self.search = field(parent, "")
    self.search.PlaceholderText = "Поиск по названию ассета"
    self.catalogList = scrollList(parent, 133)
    self.search:GetPropertyChangedSignal("Text"):Connect(function() self:RenderCatalog() end)
    self.chosen = label(parent, "Ассет не выбран", 27, TEXT)

    section(parent, "03 · Поворот ассета")
    label(parent, "Без подвеса Pivot стоит в точке крепления. С подвесом он ниже на длину нити.", 42)
    self.axes = {}
    for _, definition in ipairs({
        {key = "yaw", name = "Yaw · по нормали"},
        {key = "pitch", name = "Pitch · наклон"},
        {key = "roll", name = "Roll · крен"},
    }) do
        local key = definition.key
        self.axes[key] = Adjustments.Slider(parent, {
            label = definition.name, min = -180, max = 180,
            step = 1, value = self.config[key], suffix = "°", format = "%.0f",
            changed = function(value)
                self.config[key] = value
                self:Changed()
            end,
        })
    end
    local presets = add("Frame", {BackgroundTransparency = 1,
        Size = UDim2.new(1, 0, 0, 35)}, parent)
    add("UIListLayout", {FillDirection = Enum.FillDirection.Horizontal,
        SortOrder = Enum.SortOrder.LayoutOrder, Padding = UDim.new(0, 5)}, presets)
    for _, item in ipairs({
        {label = "Сброс", angle = 0, all = true},
        {label = "↶ 90°", angle = -90},
        {label = "↷ 90°", angle = 90},
        {label = "180°", angle = 180},
    }) do
        local action = button(presets, item.label, 33)
        action.Size = UDim2.new(0.24, 0, 0, 33)
        action.MouseButton1Click:Connect(function()
            if item.all then
                self.config.yaw, self.config.pitch, self.config.roll = 0, 0, 0
            else
                self.config.yaw = item.angle
            end
            self:Changed()
        end)
    end

    section(parent, "04 · Подвес · реакция на события")
    self.tether = button(parent, "○ Подвес выключен")
    self.tether.MouseButton1Click:Connect(function()
        self.config.tetherEnabled = not self.config.tetherEnabled
        if not self.config.tetherEnabled then self.config.swayEnabled = false end
        self:Changed()
    end)
    self.sway = button(parent, "☐ Покачивание от ударов / ветра", 37)
    self.sway.MouseButton1Click:Connect(function()
        self.config.swayEnabled = not self.config.swayEnabled
        if self.config.swayEnabled then self.config.tetherEnabled = true end
        self:Changed()
    end)
    label(parent, "С галочкой: визуальное качание от удара, стрелы или ветра. Объект Anchored; верёвка декоративная.", 50)
    self.length = Adjustments.Slider(parent, {
        label = "Длина подвеса · studs", min = 0.05, max = 100,
        logarithmic = true, step = 0.05, value = self.config.length,
        format = "%.2f", changed = function(value)
            self.config.length = value
            self:Changed()
        end,
    })
    self.thickness = Adjustments.Slider(parent, {
        label = "Толщина нити · studs", min = 0.02, max = 4,
        logarithmic = true, step = 0.01, value = self.config.thickness,
        format = "%.2f", changed = function(value)
            self.config.thickness = value
            self:Changed()
        end,
    })
    label(parent, "Цвет подвеса", 20)
    self.color = Adjustments.Color(parent, {
        value = Color3.fromHex(self.config.color),
        presets = {
            Color3.fromRGB(52, 59, 56), Color3.fromRGB(97, 74, 50),
            Color3.fromRGB(163, 144, 109), Color3.fromRGB(227, 222, 198),
            Color3.fromRGB(78, 120, 85), Color3.fromRGB(62, 62, 72),
        },
        changed = function(value)
            self.config.color = "#" .. value:ToHex():upper()
            self:Changed()
        end,
    })

    section(parent, "05 · Профили размещения")
    label(parent, "Use: для каждого нового размещения. Apply: изменить выделенную модель, без нового ассета.", 43)
    self.name = field(parent, "")
    self.name.PlaceholderText = "Название нового профиля"
    local save = button(parent, "Сохранить новый профиль")
    save.MouseButton1Click:Connect(function()
        actions.saveProfile(self.name.Text, self.config)
    end)
    self.profileList = scrollList(parent, 124)
    self.profileStatus = label(parent, "Профиль не выбран", 30, TEXT)
    self.use = button(parent, "Use · включить для новых размещений")
    self.use.MouseButton1Click:Connect(function()
        if not self.selectedProfile then actions.status("Выбери профиль"); return end
        actions.useProfile(self.selectedProfile, self.activeId ~= self.selectedProfile)
    end)
    local apply = button(parent, "Apply · к выделенной Model")
    apply.MouseButton1Click:Connect(function()
        if not self.selectedProfile then actions.status("Выбери профиль"); return end
        actions.applyProfile(self.selectedProfile)
    end)
    local delete = button(parent, "Удалить выбранный профиль")
    delete.MouseButton1Click:Connect(function()
        if self.selectedProfile then actions.removeProfile(self.selectedProfile) end
    end)
    self:Refresh()
    return self
end

function AssetsWidget:Changed()
    -- A Use profile previously overrode the visible checkbox silently.
    -- Once the user edits any manual control, the UI becomes authoritative.
    if self.activeId then
        self.actions.useProfile(self.activeId, false)
    end
    self:Refresh()
    self.actions.configChanged(table.clone(self.config))
end

function AssetsWidget:SetConfig(config)
    for _, key in ipairs({"yaw", "pitch", "roll", "length", "thickness", "color", "tetherEnabled", "swayEnabled"}) do
        -- Equivalent rotations share one readable slider range (-180..180).
        self.config[key] = if key == "yaw" or key == "pitch" or key == "roll"
            then (config[key] + 180) % 360 - 180 else config[key]
    end
    -- Selecting/restoring a saved profile is not a manual edit.
    self:Refresh()
    self.actions.configChanged(table.clone(self.config))
end

function AssetsWidget:SetStatus(message)
    self.modeStatus.Text = tostring(message)
end

function AssetsWidget:SetActive(active)
    self.active = active
    self:Refresh()
end

function AssetsWidget:Refresh()
    for axis, slider in pairs(self.axes) do slider:Set(self.config[axis]) end
    self.length:Set(self.config.length)
    self.thickness:Set(self.config.thickness)
    self.color:Set(Color3.fromHex(self.config.color))
    self.tether.Text = if self.config.tetherEnabled then "● Подвес включён" else "○ Подвес выключен"
    self.sway.Text = if self.config.swayEnabled then "☑ Покачивание · Play" else "☐ Покачивание от ударов / ветра"
    self.mode.Text = if self.active then "● Прицел активен · Enter завершить" else "Начать · Размещение ассета"
    self.target.Text = if self.targetMode == "auto" then "Прицел: Авто · стебель / поверхность"
        elseif self.targetMode == "stem" then "Прицел: Только стебель"
        else "Прицел: Только поверхность"
    self.use.Text = if self.selectedProfile and self.activeId == self.selectedProfile
        then "● Use · активно (нажми, чтобы снять)" else "○ Use · для новых размещений"
    if self.activeId then
        self.profileStatus.Text = "Use активен · параметры ниже соответствуют профилю. Любая ручная правка автоматически выключит Use."
        self.profileStatus.Size = UDim2.new(1, 0, 0, 52)
    else
        self.profileStatus.Size = UDim2.new(1, 0, 0, 30)
        if not self.selectedProfile then self.profileStatus.Text = "Профиль не выбран" end
    end
end

function AssetsWidget:SetCatalog(rows)
    self.rows = rows
    self:RenderCatalog()
end

function AssetsWidget:RenderCatalog()
    clearChildren(self.catalogList)
    local query = self.search.Text:lower()
    local count = 0
    for _, row in ipairs(self.rows) do
        if count >= 80 then break end
        if row.slug:lower():find(query, 1, true) then
            count += 1
            local prefix = if row.slug == self.selectedSlug then "● " else "   "
            local item = button(self.catalogList,
                prefix .. tostring(row.name_en or row.slug) .. " · " .. row.slug, 30)
            item.LayoutOrder = count
            item.MouseButton1Click:Connect(function()
                self.actions.selectAsset(row)
            end)
        end
    end
    if count == 0 then label(self.catalogList, "Нет совпадений · обнови каталог", 28) end
end

function AssetsWidget:SelectAsset(row)
    self.selectedSlug = row.slug
    self.chosen.Text = "Выбрано: " .. row.slug .. " · Model " .. tostring(row.model_asset_id)
    self:RenderCatalog()
end

function AssetsWidget:SelectProfile(id)
    for _, item in ipairs(self.profiles) do
        if item.id == id then
            if self.activeId and self.activeId ~= id then
                self.actions.useProfile(self.activeId, false)
            end
            self.selectedProfile = id
            self.profileStatus.Text = "Профиль: " .. item.name
            self:SetConfig(item)
            return
        end
    end
end

function AssetsWidget:SetProfiles(rows, activeId)
    self.profiles = rows
    self.activeId = activeId
    if self.selectedProfile then
        local found = false
        for _, item in ipairs(rows) do
            if item.id == self.selectedProfile then found = true end
        end
        if not found then
            self.selectedProfile = nil
            self.profileStatus.Text = "Профиль не выбран"
        end
    end
    clearChildren(self.profileList)
    for index, item in ipairs(rows) do
        local title = (if item.id == activeId then "● " else "○ ") .. item.name
        local control = button(self.profileList, title, 31)
        control.LayoutOrder = index
        control.MouseButton1Click:Connect(function()
            if self.activeId and self.activeId ~= item.id then
                self.actions.useProfile(self.activeId, false)
            end
            self.selectedProfile = item.id
            self.profileStatus.Text = "Профиль: " .. item.name
            self:SetConfig(item)
            self:Refresh()
        end)
    end
    if activeId then
        for _, item in ipairs(rows) do
            if item.id == activeId then
                self:SetConfig(item)
                return
            end
        end
    end
    self:Refresh()
end

return AssetsWidget
