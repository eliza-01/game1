--!strict
-- Published, rig-compatible appearance picker. The shell owns navigation;
-- this view renders only one active category to avoid a giant scrolling form.
local Language = require(script.Parent.Parent:WaitForChild("localization"):WaitForChild("LanguageState"))
local View = {}
local INK = Color3.fromRGB(243, 235, 218)
local GOLD = Color3.fromRGB(215, 179, 115)

local function rounded(object: GuiObject, radius: number)
    local c = Instance.new("UICorner")
    c.CornerRadius = UDim.new(0, radius)
    c.Parent = object
end

local function heading(parent: Instance, name: string, order: number, height: number): TextLabel
    local item = Instance.new("TextLabel")
    item.Name = "CategoryHeading"
    item.BackgroundTransparency = 1
    item.Font = Enum.Font.GothamSemibold
    item.TextColor3 = INK
    item.TextSize = 17
    item.TextXAlignment = Enum.TextXAlignment.Left
    item.Text = name
    item.LayoutOrder = order
    item.Size = UDim2.new(1, 0, 0, height)
    item.Parent = parent
    return item
end

local function lockHeading(parent: Instance, name: string, order: number, height: number,
    locked: boolean, toggle: (() -> ())?)
    local row = Instance.new("Frame")
    row.Name = "ColorHeading"
    row.BackgroundTransparency = 1
    row.LayoutOrder = order
    row.Size = UDim2.new(1, 0, 0, height)
    row.Parent = parent

    local title = Instance.new("TextLabel")
    title.Name = "CategoryHeading"
    title.BackgroundTransparency = 1
    title.Font = Enum.Font.GothamSemibold
    title.TextColor3 = INK
    title.TextSize = 17
    title.TextXAlignment = Enum.TextXAlignment.Left
    title.Text = name
    title.Size = UDim2.new(1, -54, 1, 0)
    title.Parent = row

    local button = Instance.new("TextButton")
    button.Name = "SyncLock"
    button.AnchorPoint = Vector2.new(1, 0.5)
    button.Position = UDim2.new(1, 0, 0.5, 0)
    button.Size = UDim2.fromOffset(40, 34)
    button.BackgroundColor3 = Color3.fromRGB(42, 55, 62)
    button.TextColor3 = if locked then GOLD else INK
    button.Font = Enum.Font.GothamBold
    button.TextSize = 19
    button.Text = if locked then "🔒" else "🔓"
    button.AutoButtonColor = toggle ~= nil
    button.Active = toggle ~= nil
    button.Parent = row
    rounded(button, 9)
    local border = Instance.new("UIStroke")
    border.Color = if locked then GOLD else Color3.fromRGB(105, 118, 119)
    border.Transparency = if locked then 0 else 0.35
    border.Parent = button
    if toggle then button.Activated:Connect(toggle) end
end

local function options(parent: Instance, title: string, values: any, current: string, order: number, pick: (string) -> ())
    heading(parent, title, order, 34)
    local grid = Instance.new("Frame")
    grid.Name = "Variants"
    grid.BackgroundTransparency = 1
    grid.Size = UDim2.new(1, 0, 0, math.ceil(#values / 2) * 62)
    grid.LayoutOrder = order + 1
    grid.Parent = parent
    local layout = Instance.new("UIGridLayout")
    layout.CellSize = UDim2.new(0.5, -6, 0, 54)
    layout.CellPadding = UDim2.new(0, 8, 0, 8)
    layout.SortOrder = Enum.SortOrder.LayoutOrder
    layout.Parent = grid
    for i, option in ipairs(values) do
        local button = Instance.new("TextButton")
        button.Name = option.id
        button.LayoutOrder = i
        button.Font = Enum.Font.GothamSemibold
        button.TextSize = 14
        button.TextColor3 = INK
        local short = option.id:match("_m(%d+)_") or tostring(i)
        button.Text = string.format("%02d  ·  %s", i, short)
        button.BackgroundColor3 = if option.id == current then Color3.fromRGB(75, 107, 96) else Color3.fromRGB(42, 55, 62)
        button.Parent = grid
        rounded(button, 10)
        local border = Instance.new("UIStroke")
        border.Color = if option.id == current then GOLD else Color3.fromRGB(105, 118, 119)
        border.Transparency = if option.id == current then 0 else 0.7
        border.Parent = button
        button.Activated:Connect(function() pick(option.id) end)
    end
end

local function swatch(parent: Instance, hex: string, label: string, order: number, current: string?, pick: () -> ())
    local item = Instance.new("TextButton")
    item.Name = label
    item.LayoutOrder = order
    item.Size = UDim2.fromOffset(44, 46)
    item.BackgroundColor3 = Color3.fromHex(hex)
    item.Text = if current and current:upper() == hex:upper() then "✓" else ""
    item.TextColor3 = if Color3.fromHex(hex).R + Color3.fromHex(hex).G + Color3.fromHex(hex).B > 1.6
        then Color3.fromRGB(22, 27, 30) else INK
    item.Font = Enum.Font.GothamBold
    item.TextSize = 19
    item.Parent = parent
    rounded(item, 10)
    local border = Instance.new("UIStroke")
    border.Color = if item.Text == "✓" then GOLD else Color3.fromRGB(166, 169, 165)
    border.Thickness = if item.Text == "✓" then 3 else 1
    border.Parent = item
    item.Activated:Connect(pick)
end

local function colorPicker(parent: Instance, title: string, current: string?, order: number,
    presets: {string}, pick: (string) -> (), custom: () -> (), eyeLock: boolean?,
    toggleEyeLock: (() -> ())?)
    if eyeLock == nil then heading(parent, title, order, 36)
    else lockHeading(parent, title, order, 36, eyeLock, toggleEyeLock) end
    local holder = Instance.new("Frame")
    holder.Name = "ColorPresets"
    holder.BackgroundTransparency = 1
    holder.LayoutOrder = order + 1
    holder.Size = UDim2.new(1, 0, 0, 58)
    holder.Parent = parent
    local layout = Instance.new("UIListLayout")
    layout.FillDirection = Enum.FillDirection.Horizontal
    layout.Padding = UDim.new(0, 7)
    layout.SortOrder = Enum.SortOrder.LayoutOrder
    layout.Parent = holder
    for index, hex in ipairs(presets) do
        swatch(holder, hex, "Preset" .. tostring(index), index, current, function() pick(hex) end)
    end
    local customButton = Instance.new("TextButton")
    customButton.Name = "CustomColor"
    customButton.Text = Language.Translate("creation.custom_color")
    customButton.Font = Enum.Font.GothamSemibold
    customButton.TextSize = 14
    customButton.TextColor3 = INK
    customButton.BackgroundColor3 = Color3.fromRGB(42, 55, 62)
    customButton.Size = UDim2.fromOffset(112, 46)
    customButton.LayoutOrder = 4
    customButton.Parent = holder
    rounded(customButton, 10)
    customButton.Activated:Connect(custom)
end

local function materialPicker(parent: Instance, title: string, materials: {string},
    current: string, order: number, pick: (string) -> ())
    if #materials <= 1 then return end
    heading(parent, title, order, 34)
    local list = Instance.new("Frame")
    list.Name = "MaterialOptions"
    list.BackgroundTransparency = 1
    list.Size = UDim2.new(1, 0, 0, math.ceil(#materials / 2) * 47)
    list.LayoutOrder = order + 1
    list.Parent = parent
    local grid = Instance.new("UIGridLayout")
    grid.CellSize = UDim2.new(0.5, -5, 0, 40)
    grid.CellPadding = UDim2.fromOffset(8, 7)
    grid.SortOrder = Enum.SortOrder.LayoutOrder
    grid.Parent = list
    for i, material in ipairs(materials) do
        local button = Instance.new("TextButton")
        button.Name = "Material" .. material
        button.LayoutOrder = i
        button.Text = material
        button.TextSize = 13
        button.Font = Enum.Font.GothamSemibold
        button.TextColor3 = INK
        button.BackgroundColor3 = if current == material then Color3.fromRGB(75, 107, 96) else Color3.fromRGB(42, 55, 62)
        button.Parent = list
        rounded(button, 9)
        button.Activated:Connect(function() pick(material) end)
    end
end

function View.Render(root: Frame, catalog: any?, selected: any?,
    onPart: (string, string) -> (), onColor: (string, string, string?) -> (), activeTab: string?,
    settings: any, onMaterial: (string, string) -> (), onCustomColor: (string, string?, string?) -> (),
    eyeColorsLocked: boolean, toggleEyeColorsLocked: (() -> ())?)
    for _, object in ipairs(root:GetChildren()) do
        if object:IsA("GuiObject") then object:Destroy() end
    end
    if not catalog or not selected then
        heading(root, Language.Translate("creation.choose_gender"), 1, 54)
        return
    end
    if not activeTab then return end
    local group = activeTab
    local entries = catalog[group] or {}
    if #entries == 0 then return end
    local order = 1
    if #entries > 1 then
        options(root, Language.Translate("creation." .. group), entries, selected[group] or "", order,
            function(id) onPart(group, id) end)
        order += 3
    end
    local presets = (settings.colorPresets or {})[group] or {}
    if group == "hair" then
        local active = nil
        for _, option in ipairs(entries) do
            if option.id == selected.hair then active = option; break end
        end
        for _, channel in ipairs((active and active.part and active.part.colorChannels) or {}) do
            local current = (selected.colors.hair or {})[channel]
            colorPicker(root, Language.Translate("creation.hair_color") .. " · " .. channel,
                current, order, (settings.colorPresets or {}).hair or {},
                function(hex) onColor("hair", hex, channel) end,
                function() onCustomColor("hair", channel, current) end, nil, nil)
            order += 3
        end
        materialPicker(root, Language.Translate("creation.hair_material"),
            (settings.materialChoices or {}).hair or {"Plastic"}, (selected.materials or {}).hair or "Plastic",
            order, function(value) onMaterial("hair", value) end)
    elseif group == "eyebrows" then
        local current = (selected.colors or {}).eyebrows
        colorPicker(root, Language.Translate("creation.eyebrows_color"), current, order,
            presets, function(hex) onColor(group, hex, nil) end,
            function() onCustomColor(group, nil, current) end, nil, nil)
    elseif group == "eyes" then
        for _, side in ipairs({"l", "r"}) do
            local current = selected.colors.eyes[side]
            colorPicker(root, Language.Translate("creation.eye_" .. side .. "_color"), current, order,
                presets, function(hex) onColor(group, hex, side) end,
                function() onCustomColor(group, side, current) end, eyeColorsLocked,
                toggleEyeColorsLocked)
            order += 3
        end
        materialPicker(root, Language.Translate("creation.eyes_material"),
            (settings.materialChoices or {}).eyes or {"Plastic"},
            (selected.materials or {}).eyes or "Plastic", order,
            function(value) onMaterial("eyes", value) end)
    end
end
return View
