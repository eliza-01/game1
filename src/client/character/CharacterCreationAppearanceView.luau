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
    item.Font = Enum.Font.GothamBold
    item.TextColor3 = INK
    item.TextSize = 17
    item.TextXAlignment = Enum.TextXAlignment.Left
    item.Text = name
    item.LayoutOrder = order
    item.Size = UDim2.new(1, 0, 0, height)
    item.Parent = parent
    return item
end

local function lockButton(parent: Instance, order: number, locked: boolean, toggle: (() -> ())?)
    local button = Instance.new("TextButton")
    button.Name = "SyncLock"
    button.Size = UDim2.fromOffset(36, 46)
    button.LayoutOrder = order
    button.BackgroundColor3 = Color3.fromRGB(42, 55, 62)
    button.TextColor3 = if locked then GOLD else INK
    button.Font = Enum.Font.GothamBold
    button.TextSize = 19
    button.Text = if locked then "🔒" else "🔓"
    button.AutoButtonColor = toggle ~= nil
    button.Active = toggle ~= nil
    button.Parent = parent
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
    grid.Size = UDim2.new(1, 0, 0, math.ceil(#values / 4) * 54)
    grid.LayoutOrder = order + 1
    grid.Parent = parent
    local layout = Instance.new("UIGridLayout")
    layout.CellSize = UDim2.fromOffset(46, 46)
    layout.FillDirectionMaxCells = 4
    layout.CellPadding = UDim2.new(0, 8, 0, 8)
    layout.SortOrder = Enum.SortOrder.LayoutOrder
    layout.Parent = grid
    for i, option in ipairs(values) do
        local button = Instance.new("TextButton")
        button.Name = option.id
        button.LayoutOrder = i
        button.Font = Enum.Font.GothamBold
        button.TextSize = 14
        button.TextColor3 = INK
        button.Text = tostring(i)
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
    heading(parent, title, order, 36)
    local holder = Instance.new("Frame")
    holder.Name = "ColorPresets"
    holder.BackgroundTransparency = 1
    holder.LayoutOrder = order + 1
    holder.Size = UDim2.new(1, 0, 0, 46)
    holder.Parent = parent
    local presetRow = Instance.new("Frame")
    presetRow.Name = "PresetRow"
    presetRow.BackgroundTransparency = 1
    presetRow.Size = UDim2.fromOffset(math.max(0, #presets * 51 - 7), 46)
    presetRow.Parent = holder
    for index, hex in ipairs(presets) do
        swatch(presetRow, hex, "Preset" .. tostring(index), index, current, function() pick(hex) end)
    end
    local actions = Instance.new("Frame")
    actions.Name = "ColorActions"
    actions.BackgroundTransparency = 1
    local actionWidth = if eyeLock == nil then 112 else 155
    actions.Size = UDim2.fromOffset(actionWidth, 46)
    actions.Parent = holder
    local actionLayout = Instance.new("UIListLayout")
    actionLayout.FillDirection = Enum.FillDirection.Horizontal
    actionLayout.Padding = UDim.new(0, 7)
    actionLayout.SortOrder = Enum.SortOrder.LayoutOrder
    actionLayout.Parent = actions
    local function resize()
        local width = if holder.AbsoluteSize.X > 0 then holder.AbsoluteSize.X
            elseif parent:IsA("GuiObject") then parent.AbsoluteSize.X else 0
        local columns = math.max(1, math.floor((width + 7) / 51))
        local presetWidth = math.max(0, math.min(columns, #presets) * 51 - 7)
        local rows = math.ceil(#presets / columns)
        presetRow.Size = UDim2.fromOffset(presetWidth, math.max(0, rows * 53 - 7))
        local inline = rows <= 1 and presetWidth + (if #presets > 0 then 7 else 0) + actionWidth <= width
        actions.Position = if inline then UDim2.fromOffset(presetWidth + (if #presets > 0 then 7 else 0), 0)
            else UDim2.fromOffset(0, rows * 53)
        holder.Size = UDim2.new(1, 0, 0, if inline then 46 else rows * 53 + 46)
    end
    -- Fixed cells wrap when Options adds more presets; the Custom/lock pair never splits.
    local grid = Instance.new("UIGridLayout")
    grid.CellSize = UDim2.fromOffset(44, 46)
    grid.CellPadding = UDim2.fromOffset(7, 7)
    grid.SortOrder = Enum.SortOrder.LayoutOrder
    grid.Parent = presetRow
    holder:GetPropertyChangedSignal("AbsoluteSize"):Connect(resize)
    resize()
    local customButton = Instance.new("TextButton")
    customButton.Name = "CustomColor"
    customButton.Text = Language.Translate("creation.custom_color")
    customButton.Font = Enum.Font.GothamBold
    customButton.TextSize = 14
    customButton.TextWrapped = true
    customButton.TextColor3 = INK
    customButton.BackgroundColor3 = Color3.fromRGB(42, 55, 62)
    customButton.Size = UDim2.fromOffset(112, 46)
    customButton.LayoutOrder = 1
    customButton.Parent = actions
    rounded(customButton, 10)
    customButton.Activated:Connect(custom)
    if eyeLock ~= nil then lockButton(actions, 2, eyeLock, toggleEyeLock) end
end

local function materialPicker(parent: Instance, title: string, materials: {string},
    current: string, order: number, pick: (string) -> ())
    if #materials <= 1 then return end
    heading(parent, title, order, 34)
    local selectedIndex = table.find(materials, current) or 1
    local selector = Instance.new("Frame")
    selector.Name = "MaterialSelector"
    selector.BackgroundTransparency = 1
    selector.Size = UDim2.new(1, 0, 0, 206)
    selector.LayoutOrder = order + 1
    selector.Parent = parent

    local function button(name: string, label: string, container: Instance): TextButton
        local item = Instance.new("TextButton")
        item.Name = name
        item.Text = label
        item.Font = Enum.Font.GothamBold
        item.TextSize = 15
        item.TextColor3 = INK
        item.BackgroundColor3 = Color3.fromRGB(42, 55, 62)
        item.BorderSizePixel = 0
        item.Parent = container
        rounded(item, 9)
        return item
    end

    local previous = button("PreviousMaterial", "‹", selector)
    previous.Size = UDim2.fromOffset(44, 44)
    previous.TextSize = 28
    local nextButton = button("NextMaterial", "›", selector)
    nextButton.Size = UDim2.fromOffset(44, 44)
    nextButton.Position = UDim2.new(1, -44, 0, 0)
    nextButton.TextSize = 28
    local nameButton = heading(selector, materials[selectedIndex], 0, 44)
    nameButton.Name = "MaterialName"
    nameButton.TextXAlignment = Enum.TextXAlignment.Center
    nameButton.TextSize = 15
    nameButton.BackgroundTransparency = 0
    nameButton.BackgroundColor3 = Color3.fromRGB(42, 55, 62)
    rounded(nameButton, 9)
    nameButton.Position = UDim2.fromOffset(51, 0)
    nameButton.Size = UDim2.new(1, -102, 0, 44)
    nameButton.TextTruncate = Enum.TextTruncate.AtEnd
    local border = Instance.new("UIStroke")
    border.Color = GOLD
    border.Transparency = 0.45
    border.Parent = nameButton

    -- Existing Options order is authoritative for both arrows and numeric cells.
    -- Keep the picker inside the scroll layout rather than over other controls.
    local list = Instance.new("Frame")
    list.Name = "MaterialOptions"
    list.BackgroundTransparency = 1
    list.Position = UDim2.fromOffset(0, 52)
    list.Size = UDim2.new(1, 0, 0, 154)
    list.Visible = true
    list.Parent = selector
    local grid = Instance.new("UIGridLayout")
    grid.CellSize = UDim2.fromOffset(46, 46)
    grid.CellPadding = UDim2.fromOffset(8, 8)
    grid.FillDirectionMaxCells = 3
    grid.HorizontalAlignment = Enum.HorizontalAlignment.Center
    grid.SortOrder = Enum.SortOrder.LayoutOrder
    grid.Parent = list
    for i, material in ipairs(materials) do
        local item = button("Material" .. material, tostring(i), list)
        item.LayoutOrder = i
        if i == selectedIndex then
            item.BackgroundColor3 = Color3.fromRGB(75, 107, 96)
            local selectedBorder = Instance.new("UIStroke")
            selectedBorder.Color = GOLD
            selectedBorder.Parent = item
        end
        item.Activated:Connect(function() pick(material) end)
    end
    local function step(delta: number)
        local index = (selectedIndex - 1 + delta) % #materials + 1
        pick(materials[index])
    end
    previous.Activated:Connect(function() step(-1) end)
    nextButton.Activated:Connect(function() step(1) end)
end

function View.Render(root: Frame, catalog: any?, selected: any?,
    onPart: (string, string) -> (), onColor: (string, string, string?) -> (), activeTab: string?,
    settings: any, onMaterial: (string, string) -> (), onCustomColor: (string, string?, string?) -> (),
    eyeColorsLocked: boolean, toggleEyeColorsLocked: ((string) -> ())?)
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
            local title = Language.Translate("creation.hair_color")
            if channel ~= "primary" then title ..= " · " .. channel end
            colorPicker(root, title,
                current, order, (settings.colorPresets or {}).hair or {},
                function(hex) onColor("hair", hex, channel) end,
                function() onCustomColor("hair", channel, current) end, nil, nil)
            order += 3
        end
    elseif group == "eyebrows" then
        local current = (selected.colors or {}).eyebrows
        colorPicker(root, Language.Translate("creation.eyebrows_color"), current, order,
            presets, function(hex) onColor(group, hex, nil) end,
            function() onCustomColor(group, nil, current) end, nil, nil)
        order += 3
    elseif group == "eyes" then
        for _, side in ipairs({"l", "r"}) do
            local current = selected.colors.eyes[side]
            colorPicker(root, Language.Translate("creation.eye_" .. side .. "_color"), current, order,
                presets, function(hex) onColor(group, hex, side) end,
                function() onCustomColor(group, side, current) end, eyeColorsLocked,
                if toggleEyeColorsLocked then function() toggleEyeColorsLocked(side) end else nil)
            order += 3
        end
    end
    materialPicker(root, Language.Translate("creation." .. group .. "_material"),
        (settings.materialChoices or {})[group] or {"Plastic"},
        (selected.materials or {})[group] or "Plastic", order,
        function(value) onMaterial(group, value) end)
end
return View
