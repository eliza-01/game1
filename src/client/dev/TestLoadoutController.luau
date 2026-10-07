local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local TestLoadoutController = {}
local started = false
local player = Players.LocalPlayer

local PANEL_WIDTH = 320
local PANEL_EXPANDED_HEIGHT = 410
local PANEL_COLLAPSED_SIZE = 44
local PANEL_X = 16
local PANEL_Y = 150
local CONTENT_WIDTH = PANEL_WIDTH - 32
local DEBUG_PANEL_OPEN_ATTRIBUTE = "Game1DebugPanelOpen"
local DEBUG_PANEL_ID = "TL"
local STUDIO_PREFERENCES_FOLDER = "Game1StudioPreferences"
local STUDIO_PREFERENCES_READY_ATTRIBUTE = "ClientPreferencesReady"

local COLORS = {
    panel = Color3.fromRGB(15, 20, 27),
    panelRaised = Color3.fromRGB(20, 27, 36),
    control = Color3.fromRGB(28, 37, 48),
    controlHover = Color3.fromRGB(36, 48, 62),
    controlSelected = Color3.fromRGB(31, 76, 70),
    accent = Color3.fromRGB(72, 214, 180),
    accentHover = Color3.fromRGB(91, 229, 195),
    text = Color3.fromRGB(239, 244, 248),
    muted = Color3.fromRGB(139, 157, 173),
    mutedStrong = Color3.fromRGB(172, 187, 200),
    line = Color3.fromRGB(55, 69, 83),
    error = Color3.fromRGB(239, 116, 116),
    disabled = Color3.fromRGB(24, 31, 40),
}

local function corner(parent: Instance, radius: number)
    local item = Instance.new("UICorner")
    item.CornerRadius = UDim.new(0, radius)
    item.Parent = parent
end

local function stroke(parent: Instance, transparency: number?)
    local item = Instance.new("UIStroke")
    item.Color = COLORS.line
    item.Transparency = transparency or 0.15
    item.Thickness = 1
    item.Parent = parent
end

local function textLabel(parent: Instance, text: string, size: number, bold: boolean?): TextLabel
    local label = Instance.new("TextLabel")
    label.BackgroundTransparency = 1
    label.Text = text
    label.TextColor3 = COLORS.text
    label.TextSize = size
    label.Font = bold and Enum.Font.GothamSemibold or Enum.Font.Gotham
    label.TextXAlignment = Enum.TextXAlignment.Left
    label.TextYAlignment = Enum.TextYAlignment.Center
    label.Parent = parent
    return label
end

local function sectionCaption(parent: Instance, text: string, y: number)
    local label = textLabel(parent, string.upper(text), 9, true)
    label.TextColor3 = COLORS.muted
    label.Position = UDim2.fromOffset(0, y)
    label.Size = UDim2.new(1, 0, 0, 14)
end

local function button(parent: Instance, text: string): TextButton
    local item = Instance.new("TextButton")
    item.AutoButtonColor = false
    item.BackgroundColor3 = COLORS.control
    item.TextColor3 = COLORS.text
    item.Text = text
    item.TextSize = 11
    item.Font = Enum.Font.Gotham
    item.Parent = parent
    corner(item, 7)
    stroke(item, 0.35)
    return item
end

local function numericBox(parent: Instance, placeholder: string): TextBox
    local box = Instance.new("TextBox")
    box.BackgroundColor3 = COLORS.control
    box.BorderSizePixel = 0
    box.TextColor3 = COLORS.text
    box.PlaceholderColor3 = COLORS.muted
    box.PlaceholderText = placeholder
    box.ClearTextOnFocus = false
    box.Text = ""
    box.TextSize = 11
    box.Font = Enum.Font.GothamSemibold
    box.TextXAlignment = Enum.TextXAlignment.Left
    box.Parent = parent
    local padding = Instance.new("UIPadding")
    padding.PaddingLeft = UDim.new(0, 10)
    padding.PaddingRight = UDim.new(0, 10)
    padding.Parent = box
    corner(box, 7)
    stroke(box, 0.35)
    return box
end

local function createDropdown(gui: ScreenGui, parent: Instance, y: number, labelText: string)
    sectionCaption(parent, labelText, y)

    local control = button(parent, "—")
    control.Position = UDim2.fromOffset(0, y + 18)
    control.Size = UDim2.new(1, 0, 0, 34)
    control.TextSize = 12
    control.Font = Enum.Font.GothamSemibold
    control.TextXAlignment = Enum.TextXAlignment.Left
    control.TextTruncate = Enum.TextTruncate.AtEnd
    local padding = Instance.new("UIPadding")
    padding.PaddingLeft = UDim.new(0, 11)
    padding.PaddingRight = UDim.new(0, 11)
    padding.Parent = control

    local popup = Instance.new("ScrollingFrame")
    popup.Visible = false
    popup.BackgroundColor3 = COLORS.panelRaised
    popup.BorderSizePixel = 0
    popup.ScrollBarThickness = 3
    popup.ScrollBarImageColor3 = COLORS.muted
    popup.AutomaticCanvasSize = Enum.AutomaticSize.Y
    popup.CanvasSize = UDim2.new()
    popup.ZIndex = 50
    popup.Parent = gui
    corner(popup, 8)
    stroke(popup, 0.05)

    local layout = Instance.new("UIListLayout")
    layout.Padding = UDim.new(0, 3)
    layout.SortOrder = Enum.SortOrder.LayoutOrder
    layout.Parent = popup
    local popupPadding = Instance.new("UIPadding")
    popupPadding.PaddingTop = UDim.new(0, 5)
    popupPadding.PaddingBottom = UDim.new(0, 5)
    popupPadding.PaddingLeft = UDim.new(0, 5)
    popupPadding.PaddingRight = UDim.new(0, 5)
    popupPadding.Parent = popup

    local state = { value = "", options = {}, onChanged = nil, enabled = true, buttons = {} }

    local function renderControl()
        local found = "—"
        for _, option in ipairs(state.options) do
            if option.value == state.value then
                found = option.label
                break
            end
        end
        control.Text = found .. (popup.Visible and "   ▴" or "   ▾")
        control.BackgroundColor3 = state.enabled and COLORS.control or COLORS.disabled
        control.TextColor3 = state.enabled and COLORS.text or COLORS.muted
    end

    local function renderOptions()
        for index, optionButton in pairs(state.buttons) do
            local option = state.options[index]
            local selected = option and option.value == state.value
            optionButton.BackgroundColor3 = selected and COLORS.controlSelected or COLORS.control
            optionButton.TextColor3 = selected and COLORS.accent or COLORS.text
        end
    end

    local function close()
        popup.Visible = false
        renderControl()
    end

    local function setValue(value: string, fire: boolean?)
        state.value = value
        close()
        renderControl()
        renderOptions()
        if fire and state.onChanged then
            state.onChanged(value)
        end
    end

    local function refresh(options, preferredValue: string?)
        state.options = options or {}
        state.buttons = {}
        for _, child in popup:GetChildren() do
            if child:IsA("TextButton") then
                child:Destroy()
            end
        end
        for index, option in ipairs(state.options) do
            local optionButton = button(popup, option.label)
            optionButton.Size = UDim2.new(1, 0, 0, 30)
            optionButton.LayoutOrder = index
            optionButton.ZIndex = 51
            optionButton.TextSize = 11
            optionButton.TextXAlignment = Enum.TextXAlignment.Left
            optionButton.TextTruncate = Enum.TextTruncate.AtEnd
            local optionPadding = Instance.new("UIPadding")
            optionPadding.PaddingLeft = UDim.new(0, 9)
            optionPadding.PaddingRight = UDim.new(0, 9)
            optionPadding.Parent = optionButton
            state.buttons[index] = optionButton
            optionButton.Activated:Connect(function()
                if state.enabled then
                    setValue(option.value, true)
                end
            end)
        end
        local nextValue = preferredValue or state.value
        local valid = false
        for _, option in ipairs(state.options) do
            if option.value == nextValue then
                valid = true
                break
            end
        end
        if not valid then
            nextValue = state.options[1] and state.options[1].value or ""
        end
        setValue(nextValue, false)
    end

    control.Activated:Connect(function()
        if not state.enabled or #state.options == 0 then
            return
        end
        if popup.Visible then
            close()
            return
        end
        popup.Position = UDim2.fromOffset(control.AbsolutePosition.X, control.AbsolutePosition.Y + control.AbsoluteSize.Y + 4)
        popup.Size = UDim2.fromOffset(control.AbsoluteSize.X, math.min(214, 10 + (#state.options * 33)))
        popup.Visible = true
        renderControl()
    end)

    return {
        refresh = refresh,
        setValue = setValue,
        getValue = function() return state.value end,
        close = close,
        setOnChanged = function(callback) state.onChanged = callback end,
        setEnabled = function(enabled: boolean)
            state.enabled = enabled
            control.Active = enabled
            if not enabled then close() end
            renderControl()
        end,
    }
end

local function createCategorySelector(parent: Instance, y: number)
    sectionCaption(parent, "Weapon type", y)
    local scroller = Instance.new("ScrollingFrame")
    scroller.BackgroundTransparency = 1
    scroller.BorderSizePixel = 0
    scroller.Position = UDim2.fromOffset(0, y + 18)
    scroller.Size = UDim2.new(1, 0, 0, 32)
    scroller.ScrollBarThickness = 0
    scroller.ScrollingDirection = Enum.ScrollingDirection.X
    scroller.AutomaticCanvasSize = Enum.AutomaticSize.X
    scroller.CanvasSize = UDim2.new()
    scroller.Parent = parent
    local layout = Instance.new("UIListLayout")
    layout.FillDirection = Enum.FillDirection.Horizontal
    layout.SortOrder = Enum.SortOrder.LayoutOrder
    layout.Padding = UDim.new(0, 6)
    layout.VerticalAlignment = Enum.VerticalAlignment.Center
    layout.Parent = scroller

    local state = { value = "", options = {}, buttons = {}, onChanged = nil, enabled = true }
    local function render()
        for index, chip in pairs(state.buttons) do
            local option = state.options[index]
            local selected = option and option.value == state.value
            chip.BackgroundColor3 = selected and COLORS.controlSelected or (state.enabled and COLORS.control or COLORS.disabled)
            chip.TextColor3 = selected and COLORS.accent or (state.enabled and COLORS.mutedStrong or COLORS.muted)
            chip.Active = state.enabled
        end
    end
    local function setValue(value: string, fire: boolean?)
        state.value = value
        render()
        if fire and state.onChanged then state.onChanged(value) end
    end
    local function refresh(options, preferredValue: string?)
        state.options = options or {}
        state.buttons = {}
        for _, child in scroller:GetChildren() do
            if child:IsA("TextButton") then child:Destroy() end
        end
        for index, option in ipairs(state.options) do
            local chip = button(scroller, option.label)
            chip.AutomaticSize = Enum.AutomaticSize.X
            chip.Size = UDim2.fromOffset(0, 30)
            chip.LayoutOrder = index
            chip.TextSize = 10
            chip.Font = Enum.Font.GothamSemibold
            local pad = Instance.new("UIPadding")
            pad.PaddingLeft = UDim.new(0, 11)
            pad.PaddingRight = UDim.new(0, 11)
            pad.Parent = chip
            state.buttons[index] = chip
            chip.Activated:Connect(function()
                if state.enabled then setValue(option.value, true) end
            end)
        end
        local nextValue = preferredValue or state.value
        local valid = false
        for _, option in ipairs(state.options) do
            if option.value == nextValue then valid = true break end
        end
        if not valid then nextValue = state.options[1] and state.options[1].value or "" end
        setValue(nextValue, false)
    end
    return {
        refresh = refresh,
        setValue = setValue,
        getValue = function() return state.value end,
        setOnChanged = function(callback) state.onChanged = callback end,
        setEnabled = function(enabled: boolean) state.enabled = enabled render() end,
    }
end

local function findPreferences(): Folder?
    local value = ReplicatedStorage:FindFirstChild(STUDIO_PREFERENCES_FOLDER)
    return if value and value:IsA("Folder") then value else nil
end

local function waitForPreferences(): Folder?
    local folder = findPreferences()
    if not folder then
        local found = ReplicatedStorage:WaitForChild(STUDIO_PREFERENCES_FOLDER, 5)
        folder = if found and found:IsA("Folder") then found else nil
    end
    if not folder then return nil end
    while folder.Parent and folder:GetAttribute(STUDIO_PREFERENCES_READY_ATTRIBUTE) ~= true do
        task.wait(0.05)
    end
    return if folder.Parent then folder else nil
end


local function formatStuds(value: any): string
    local numeric = tonumber(value) or 0
    if math.abs(numeric - math.round(numeric)) < 0.001 then
        return tostring(math.round(numeric))
    end
    return string.format("%.2f", numeric):gsub("0+$", ""):gsub("%.$", "")
end

local function createAttackRadiusRing()
    local folder = Instance.new("Folder")
    folder.Name = "Game1AttackRadiusPreview"
    local parts = {}
    for index = 1, 64 do
        local part = Instance.new("Part")
        part.Name = ("Segment%02d"):format(index)
        part.Anchored = true
        part.CanCollide = false
        part.CanQuery = false
        part.CanTouch = false
        part.CastShadow = false
        part.Material = Enum.Material.Neon
        part.Color = COLORS.accent
        part.Transparency = 0.18
        part.Parent = folder
        parts[index] = part
    end
    return folder, parts
end

local function createGui()
    local playerGui = player:WaitForChild("PlayerGui")
    local previous = playerGui:FindFirstChild("Game1TestLoadoutGui")
    if previous then previous:Destroy() end

    local gui = Instance.new("ScreenGui")
    gui.Name = "Game1TestLoadoutGui"
    gui.ResetOnSpawn = false
    gui.DisplayOrder = 20
    gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
    gui.Parent = playerGui

    local panel = Instance.new("Frame")
    panel.BackgroundColor3 = COLORS.panel
    panel.BackgroundTransparency = 0.025
    panel.BorderSizePixel = 0
    panel.Position = UDim2.fromOffset(PANEL_X, PANEL_Y)
    panel.Size = UDim2.fromOffset(PANEL_COLLAPSED_SIZE, PANEL_COLLAPSED_SIZE)
    panel.Parent = gui
    corner(panel, 10)
    stroke(panel, 0.12)

    local accent = Instance.new("Frame")
    accent.BackgroundColor3 = COLORS.accent
    accent.BorderSizePixel = 0
    accent.Position = UDim2.fromOffset(0, 0)
    accent.Size = UDim2.fromOffset(3, PANEL_COLLAPSED_SIZE)
    accent.Parent = panel
    corner(accent, 2)

    local header = textLabel(panel, "TEST LOADOUT", 11, true)
    header.Position = UDim2.fromOffset(16, 6)
    header.Size = UDim2.fromOffset(190, 16)
    local subtitle = textLabel(panel, "character + weapon sandbox", 9, false)
    subtitle.TextColor3 = COLORS.muted
    subtitle.Position = UDim2.fromOffset(16, 22)
    subtitle.Size = UDim2.fromOffset(220, 14)

    local collapse = button(panel, "TL")
    collapse.Position = UDim2.fromOffset(0, 0)
    collapse.Size = UDim2.fromOffset(PANEL_COLLAPSED_SIZE, PANEL_COLLAPSED_SIZE)
    collapse.Font = Enum.Font.GothamSemibold
    collapse.TextSize = 11

    local body = Instance.new("Frame")
    body.BackgroundTransparency = 1
    body.Position = UDim2.fromOffset(16, 48)
    body.Size = UDim2.fromOffset(CONTENT_WIDTH, PANEL_EXPANDED_HEIGHT - 58)
    body.Visible = false
    body.Parent = panel

    local character = createDropdown(gui, body, 0, "Character")
    local category = createCategorySelector(body, 61)
    local weapon = createDropdown(gui, body, 118, "Weapon")

    local meta = textLabel(body, "", 9, false)
    meta.TextColor3 = COLORS.muted
    meta.TextTruncate = Enum.TextTruncate.AtEnd
    meta.Position = UDim2.fromOffset(1, 172)
    meta.Size = UDim2.new(1, -2, 0, 16)

    sectionCaption(body, "Test attack radius · studs", 194)
    local radiusBox = numericBox(body, "7")
    radiusBox.Position = UDim2.fromOffset(0, 212)
    radiusBox.Size = UDim2.new(1, -82, 0, 32)
    local radiusReset = button(body, "RESET")
    radiusReset.Position = UDim2.new(1, -74, 0, 212)
    radiusReset.Size = UDim2.fromOffset(74, 32)
    radiusReset.TextSize = 9
    radiusReset.Font = Enum.Font.GothamSemibold

    local radiusToggle = button(body, "ATTACK RADIUS: OFF")
    radiusToggle.Position = UDim2.fromOffset(0, 252)
    radiusToggle.Size = UDim2.new(1, 0, 0, 28)
    radiusToggle.TextSize = 10
    radiusToggle.Font = Enum.Font.GothamSemibold

    local statusDot = Instance.new("Frame")
    statusDot.BackgroundColor3 = COLORS.muted
    statusDot.BorderSizePixel = 0
    statusDot.Position = UDim2.fromOffset(2, 297)
    statusDot.Size = UDim2.fromOffset(6, 6)
    statusDot.Parent = body
    corner(statusDot, 3)

    local status = textLabel(body, "Loading catalog…", 9, false)
    status.TextColor3 = COLORS.muted
    status.Position = UDim2.fromOffset(14, 290)
    status.Size = UDim2.new(1, -14, 0, 20)

    local apply = button(body, "LOADING…")
    apply.Position = UDim2.fromOffset(0, 316)
    apply.Size = UDim2.new(1, 0, 0, 34)
    apply.BackgroundColor3 = COLORS.disabled
    apply.TextColor3 = COLORS.muted
    apply.Font = Enum.Font.GothamSemibold
    apply.TextSize = 10
    apply.Active = false

    local collapsed = true
    local function setCollapsed(value: boolean)
        collapsed = value
        character.close()
        weapon.close()
        body.Visible = not collapsed
        header.Visible = not collapsed
        subtitle.Visible = not collapsed
        accent.Visible = not collapsed
        if collapsed then
            collapse.Text = "TL"
            collapse.Position = UDim2.fromOffset(0, 0)
            collapse.Size = UDim2.fromOffset(PANEL_COLLAPSED_SIZE, PANEL_COLLAPSED_SIZE)
        else
            collapse.Text = "–"
            collapse.Position = UDim2.fromOffset(PANEL_WIDTH - 42, 7)
            collapse.Size = UDim2.fromOffset(28, 28)
        end
        TweenService:Create(panel, TweenInfo.new(0.14, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
            Size = UDim2.fromOffset(collapsed and PANEL_COLLAPSED_SIZE or PANEL_WIDTH, collapsed and PANEL_COLLAPSED_SIZE or PANEL_EXPANDED_HEIGHT),
        }):Play()
    end
    collapse.Activated:Connect(function()
        playerGui:SetAttribute(DEBUG_PANEL_OPEN_ATTRIBUTE, collapsed and DEBUG_PANEL_ID or "")
    end)
    playerGui:GetAttributeChangedSignal(DEBUG_PANEL_OPEN_ATTRIBUTE):Connect(function()
        setCollapsed(playerGui:GetAttribute(DEBUG_PANEL_OPEN_ATTRIBUTE) ~= DEBUG_PANEL_ID)
    end)
    setCollapsed(playerGui:GetAttribute(DEBUG_PANEL_OPEN_ATTRIBUTE) ~= DEBUG_PANEL_ID)

    return gui, character, category, weapon, meta, radiusBox, radiusReset, radiusToggle, apply, status, statusDot
end

function TestLoadoutController.Start()
    if started or not RunService:IsStudio() then return end
    started = true

    task.spawn(function()
        local remotes = ReplicatedStorage:WaitForChild("Game1Remotes", 10)
        if not remotes then
            warn("[game1][test-loadout] Game1Remotes is missing")
            return
        end
        local catalogRemote = remotes:WaitForChild("GetTestLoadoutCatalog", 10)
        local applyRemote = remotes:WaitForChild("ApplyTestLoadout", 10)
        local radiusRemote = remotes:WaitForChild("SetTestAttackRadius", 10)
        if not catalogRemote or not applyRemote or not radiusRemote then
            warn("[game1][test-loadout] remotes are missing")
            return
        end

        local gui, characterDropdown, categorySelector, weaponDropdown, meta, radiusBox, radiusReset, radiusToggle, applyButton, status, statusDot = createGui()
        local catalog = catalogRemote:InvokeServer()
        local weaponRows = catalog.weapons or {}
        local weaponBySlug = {}
        for _, row in ipairs(weaponRows) do weaponBySlug[tostring(row.slug or "")] = row end

        local characterOptions = {}
        for _, row in ipairs(catalog.characters or {}) do
            table.insert(characterOptions, { value = tostring(row.id or ""), label = tostring(row.label or row.id or "") })
        end
        characterDropdown.refresh(characterOptions, tostring(catalog.selectedArchetype or ""))

        local categoryOptions = {}
        for _, value in ipairs(catalog.categories or {}) do
            local label = catalog.categoryLabels and catalog.categoryLabels[value] or value
            table.insert(categoryOptions, { value = tostring(value), label = tostring(label) })
        end
        categorySelector.refresh(categoryOptions, nil)

        local function categoryForSlug(slug: string): string
            local row = weaponBySlug[slug]
            return row and tostring(row.weaponType or "hands") or "hands"
        end

        local function rebuildWeapons(category: string, preferred: string?)
            local options = {}
            for _, row in ipairs(weaponRows) do
                if tostring(row.weaponType or "hands") == category then
                    table.insert(options, { value = tostring(row.slug or ""), label = tostring(row.label or row.slug or "") })
                end
            end
            weaponDropdown.refresh(options, preferred)
        end

        local initialWeapon = tostring(catalog.selectedWeaponSlug or "")
        local initialCategory = categoryForSlug(initialWeapon)
        categorySelector.setValue(initialCategory, false)
        rebuildWeapons(initialCategory, initialWeapon)

        local appliedArchetype = tostring(catalog.selectedArchetype or "")
        local appliedWeaponSlug = initialWeapon
        local applying = false

        local ringFolder, ringParts = createAttackRadiusRing()
        local ringVisible = false
        local ringConnection: RBXScriptConnection? = nil
        local rayParams = RaycastParams.new()
        rayParams.FilterType = Enum.RaycastFilterType.Exclude
        rayParams.IgnoreWater = false
        rayParams.RespectCanCollide = true

        local function setRingVisible(value: boolean)
            ringVisible = value == true
            radiusToggle.Text = ringVisible and "ATTACK RADIUS: ON" or "ATTACK RADIUS: OFF"
            radiusToggle.BackgroundColor3 = ringVisible and COLORS.controlSelected or COLORS.control
            radiusToggle.TextColor3 = ringVisible and COLORS.accent or COLORS.text
            ringFolder.Parent = ringVisible and Workspace or nil
        end

        local function renderAttackRadiusRing()
            if not ringVisible then return end
            local currentCharacter = player.Character
            local root = currentCharacter and currentCharacter:FindFirstChild("RootCollider")
            if not root or not root:IsA("BasePart") then
                for _, part in ipairs(ringParts) do part.Transparency = 1 end
                return
            end
            local radius = math.max(1, tonumber(currentCharacter:GetAttribute("AttackRadius")) or 7)
            rayParams.FilterDescendantsInstances = { currentCharacter }
            local ground = Workspace:Raycast(root.Position, Vector3.new(0, -64, 0), rayParams)
            local center = Vector3.new(root.Position.X, ground and (ground.Position.Y + 0.06) or (root.Position.Y - root.Size.Y * 0.5), root.Position.Z)
            local chord = 2 * radius * math.sin(math.pi / #ringParts) + 0.04
            for index, part in ipairs(ringParts) do
                local angle = ((index - 0.5) / #ringParts) * math.pi * 2
                local position = center + Vector3.new(math.cos(angle) * radius, 0, math.sin(angle) * radius)
                part.Size = Vector3.new(chord, 0.055, 0.10)
                part.CFrame = CFrame.new(position) * CFrame.Angles(0, -angle - math.pi * 0.5, 0)
                part.Transparency = 0.18
            end
        end
        ringConnection = RunService.RenderStepped:Connect(renderAttackRadiusRing)
        setRingVisible(false)
        radiusToggle.Activated:Connect(function() setRingVisible(not ringVisible) end)

        local function setStatus(message: string, color: Color3?)
            status.Text = message
            status.TextColor3 = color or COLORS.muted
            statusDot.BackgroundColor3 = color or COLORS.muted
        end

        local function syncRadiusBox(value: any)
            local numeric = math.max(1, tonumber(value) or 7)
            radiusBox.Text = string.format("%.2f", numeric):gsub("0+$", ""):gsub("%.$", "")
        end
        local function applyRadiusValue(value: any)
            local ok, result = pcall(function()
                return radiusRemote:InvokeServer(value)
            end)
            if not ok or type(result) ~= "table" or result.ok ~= true then
                setStatus("Radius error · " .. tostring(type(result) == "table" and result.error or result), COLORS.error)
                return
            end
            syncRadiusBox(result.attackRadiusStuds)
            setStatus(result.overridden and "Runtime radius override active" or "Radius reset to weapon default", COLORS.accent)
        end
        radiusBox.FocusLost:Connect(function()
            local value = tonumber(radiusBox.Text)
            if value then
                applyRadiusValue(value)
            else
                local currentCharacter = player.Character
                syncRadiusBox(currentCharacter and currentCharacter:GetAttribute("AttackRadius") or 7)
            end
        end)
        radiusReset.Activated:Connect(function()
            applyRadiusValue("default")
        end)
        local initialCharacter = player.Character
        syncRadiusBox(initialCharacter and initialCharacter:GetAttribute("AttackRadius") or 7)

        local function renderApply()
            local changed = characterDropdown.getValue() ~= appliedArchetype or weaponDropdown.getValue() ~= appliedWeaponSlug
            applyButton.Active = not applying and characterDropdown.getValue() ~= ""
            if applying then
                applyButton.Text = "APPLYING…"
                applyButton.BackgroundColor3 = COLORS.disabled
                applyButton.TextColor3 = COLORS.muted
            elseif changed then
                applyButton.Text = "ACCEPT LOADOUT"
                applyButton.BackgroundColor3 = COLORS.accent
                applyButton.TextColor3 = COLORS.panel
            else
                applyButton.Text = "LOADOUT ACTIVE"
                applyButton.BackgroundColor3 = COLORS.controlSelected
                applyButton.TextColor3 = COLORS.accent
            end
        end

        local function updateMeta()
            local row = weaponBySlug[weaponDropdown.getValue()]
            if not row or tostring(row.slug or "") == "" then
                meta.Text = string.format("hands · unarmed · radius %s studs", formatStuds(row and row.attackRadiusStuds or 7))
            else
                meta.Text = string.format("%s · %s · radius %s studs", tostring(row.weaponType or ""), tostring(row.rarity or ""), formatStuds(row.attackRadiusStuds or 7))
            end
            renderApply()
        end

        local preferences = nil
        local function persistSelection()
            if not preferences then return end
            preferences:SetAttribute("LastLoadoutArchetype", characterDropdown.getValue())
            preferences:SetAttribute("LastLoadoutWeaponSlug", weaponDropdown.getValue())
        end

        categorySelector.setOnChanged(function(value)
            rebuildWeapons(value, nil)
            updateMeta()
            persistSelection()
            setStatus("Loadout changed · accept when ready")
        end)
        characterDropdown.setOnChanged(function()
            persistSelection()
            renderApply()
            setStatus("Loadout changed · accept when ready")
        end)
        weaponDropdown.setOnChanged(function()
            persistSelection()
            updateMeta()
            setStatus("Loadout changed · accept when ready")
        end)

        local function applyCurrentSelection(silent: boolean?)
            if applying or characterDropdown.getValue() == "" then return end
            applying = true
            renderApply()
            local ok, result = pcall(function()
                return applyRemote:InvokeServer(characterDropdown.getValue(), weaponDropdown.getValue())
            end)
            applying = false
            if not ok or type(result) ~= "table" or result.ok ~= true then
                local message = if ok and type(result) == "table" then tostring(result.error or "loadout failed") else tostring(result)
                setStatus(message, COLORS.error)
                renderApply()
                return
            end
            appliedArchetype = tostring(result.archetype or characterDropdown.getValue())
            appliedWeaponSlug = tostring(result.weaponSlug or weaponDropdown.getValue())
            syncRadiusBox(result.attackRadiusStuds)
            persistSelection()
            setStatus("Loadout active", COLORS.accent)
            renderApply()
            if not silent then
                print(("[game1][test-loadout] %s · %s"):format(appliedArchetype, appliedWeaponSlug ~= "" and appliedWeaponSlug or "unarmed"))
            end
        end

        applyButton.Activated:Connect(function() applyCurrentSelection(false) end)
        updateMeta()
        setStatus("Studio-only loadout ready", COLORS.accent)
        renderApply()

        task.spawn(function()
            preferences = waitForPreferences()
            if not preferences then return end
            local storedArchetype = preferences:GetAttribute("LastLoadoutArchetype")
            if type(storedArchetype) == "string" and storedArchetype ~= "" then
                characterDropdown.setValue(storedArchetype, false)
            end
            local storedWeapon = preferences:GetAttribute("LastLoadoutWeaponSlug")
            if type(storedWeapon) == "string" then
                local category = categoryForSlug(storedWeapon)
                categorySelector.setValue(category, false)
                rebuildWeapons(category, storedWeapon)
            end
            updateMeta()
            persistSelection()
            applyCurrentSelection(true)
        end)

        gui.Destroying:Connect(function()
            preferences = nil
            if ringConnection then ringConnection:Disconnect() end
            ringFolder:Destroy()
        end)
    end)
end

return TestLoadoutController
