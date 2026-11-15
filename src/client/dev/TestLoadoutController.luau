local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local PublishedDebugAccess = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared"):WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local MeleeArcGeometry = require(CombatShared:WaitForChild("MeleeArcGeometry"))

local StudioDebugDock = require(script.Parent:WaitForChild("StudioDebugDock"))
local HouseSocketDebugController = require(script.Parent:WaitForChild("HouseSocketDebugController"))

local TestLoadoutController = {}
local started = false
local player = Players.LocalPlayer

local PANEL_WIDTH = 320
local PANEL_EXPANDED_HEIGHT = 574
local PANEL_COLLAPSED_SIZE = 44
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
    -- Extra lines show the two radial sides and the vertical extent of the arc.
    for index = 1, 4 do
        local part = Instance.new("Part")
        part.Name = ("Boundary%02d"):format(index)
        part.Anchored = true
        part.CanCollide = false
        part.CanQuery = false
        part.CanTouch = false
        part.CastShadow = false
        part.Material = Enum.Material.Neon
        part.Color = COLORS.accent
        part.Transparency = 0.27
        part.Parent = folder
        parts[64 + index] = part
    end
    -- A server hitbox Headshot is confirmed only inside the sector; this
    -- thin camera ray shows the independent precision input.
    local ray = Instance.new("Part")
    ray.Name = "HeadshotAimRay"
    ray.Anchored = true
    ray.CanCollide = false
    ray.CanQuery = false
    ray.CanTouch = false
    ray.CastShadow = false
    ray.Material = Enum.Material.Neon
    ray.Color = Color3.fromRGB(255, 205, 108)
    ray.Transparency = 0.25
    ray.Parent = folder
    parts[69] = ray
    return folder, parts
end

local function createTargetHitboxPreview()
    local folder = Instance.new("Folder")
    folder.Name = "Game1TargetHitboxPreview"
    local pool = {}

    local function acquire(index: number, shape: Enum.PartType, color: Color3, transparency: number?): Part
        local part = pool[index]
        if part and part.Shape ~= shape then
            part:Destroy()
            part = nil
        end
        if not part then
            part = Instance.new("Part")
            part.Name = ("TargetHitbox%03d"):format(index)
            part.Anchored = true
            part.CanCollide = false
            part.CanQuery = false
            part.CanTouch = false
            part.CastShadow = false
            part.Material = Enum.Material.Neon
            part.Shape = shape
            part.Parent = folder
            pool[index] = part
        end
        part.Color = color
        part.Transparency = transparency or 0.68
        return part
    end

    local function hideAfter(lastIndex: number)
        for index = lastIndex + 1, #pool do
            local part = pool[index]
            if part then part.Transparency = 1 end
        end
    end

    return {
        folder = folder,
        acquire = acquire,
        hideAfter = hideAfter,
    }
end

local function debugAnchorFrame(anchor: Instance): CFrame?
    if anchor:IsA("Bone") then
        local ok, frame = pcall(function()
            return anchor.TransformedWorldCFrame
        end)
        if ok and typeof(frame) == "CFrame" then
            return frame
        end
        return anchor.WorldCFrame
    elseif anchor:IsA("BasePart") then
        return anchor.CFrame
    end
    return nil
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

    local launcher = button(gui, "TL")
    launcher.Position = StudioDebugDock.ButtonPosition(DEBUG_PANEL_ID)
    launcher.Size = UDim2.fromOffset(PANEL_COLLAPSED_SIZE, PANEL_COLLAPSED_SIZE)
    launcher.Font = Enum.Font.GothamSemibold

    local panel = Instance.new("Frame")
    panel.BackgroundColor3 = COLORS.panel
    panel.BackgroundTransparency = 0.025
    panel.BorderSizePixel = 0
    panel.Position = StudioDebugDock.WindowPosition(DEBUG_PANEL_ID, PANEL_WIDTH)
    panel.Size = UDim2.fromOffset(PANEL_WIDTH, PANEL_EXPANDED_HEIGHT)
    panel.Visible = false
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
    local radiusMinus = button(body, "−")
    radiusMinus.Position = UDim2.fromOffset(0, 212)
    radiusMinus.Size = UDim2.fromOffset(42, 32)
    local radiusBox = numericBox(body, "7")
    radiusBox.Position = UDim2.fromOffset(48, 212)
    radiusBox.Size = UDim2.new(1, -96, 0, 32)
    radiusBox.TextXAlignment = Enum.TextXAlignment.Center
    local radiusPlus = button(body, "+")
    radiusPlus.Position = UDim2.new(1, -42, 0, 212)
    radiusPlus.Size = UDim2.fromOffset(42, 32)
    local radiusReset = button(body, "RESET")
    radiusReset.Position = UDim2.new(1, -52, 0, 194)
    radiusReset.Size = UDim2.fromOffset(52, 16)
    radiusReset.TextSize = 9
    radiusReset.Font = Enum.Font.GothamSemibold

    local radiusToggle = button(body, "ATTACK RADIUS: OFF")
    radiusToggle.Position = UDim2.fromOffset(0, 252)
    radiusToggle.Size = UDim2.new(1, 0, 0, 28)
    radiusToggle.TextSize = 10
    radiusToggle.Font = Enum.Font.GothamSemibold

    local volumeToggle = button(body, "LEGACY VOLUME · DO NOT USE")
    volumeToggle.Position = UDim2.fromOffset(0, 286)
    volumeToggle.Size = UDim2.new(1, 0, 0, 28)
    volumeToggle.TextSize = 10
    volumeToggle.Font = Enum.Font.GothamSemibold
    volumeToggle.Active = false
    volumeToggle.AutoButtonColor = false
    volumeToggle.TextColor3 = COLORS.muted
    volumeToggle.BackgroundColor3 = COLORS.disabled

    local targetHitboxToggle = button(body, "TARGET HITBOXES: OFF")
    targetHitboxToggle.Position = UDim2.fromOffset(0, 320)
    targetHitboxToggle.Size = UDim2.new(1, 0, 0, 28)
    targetHitboxToggle.TextSize = 10
    targetHitboxToggle.Font = Enum.Font.GothamSemibold

    local statusDot = Instance.new("Frame")
    statusDot.BackgroundColor3 = COLORS.muted
    statusDot.BorderSizePixel = 0
    statusDot.Position = UDim2.fromOffset(2, 365)
    statusDot.Size = UDim2.fromOffset(6, 6)
    statusDot.Parent = body
    corner(statusDot, 3)

    local status = textLabel(body, "Loading catalog…", 9, false)
    status.TextColor3 = COLORS.muted
    status.Position = UDim2.fromOffset(14, 358)
    status.Size = UDim2.new(1, -14, 0, 20)

    local apply = button(body, "LOADING…")
    apply.Position = UDim2.fromOffset(0, 384)
    apply.Size = UDim2.new(1, 0, 0, 34)
    apply.BackgroundColor3 = COLORS.disabled
    apply.TextColor3 = COLORS.muted
    apply.Font = Enum.Font.GothamSemibold
    apply.TextSize = 10
    apply.Active = false

    HouseSocketDebugController.AttachLauncher(body, 428)
    local runtimeStats = textLabel(body, "", 10, false)
    runtimeStats.Name = "ActualRuntimeStats"
    runtimeStats.Position = UDim2.fromOffset(1, 470)
    runtimeStats.Size = UDim2.new(1, -2, 0, 28)
    runtimeStats.TextWrapped = true
    runtimeStats.TextYAlignment = Enum.TextYAlignment.Top
    runtimeStats.TextColor3 = COLORS.mutedStrong

    local collapsed = true
    local function setCollapsed(value: boolean)
        collapsed = value
        character.close()
        weapon.close()
        body.Visible = not collapsed
        header.Visible = not collapsed
        subtitle.Visible = not collapsed
        accent.Visible = not collapsed
        collapse.Text = "×"
        collapse.Position = UDim2.fromOffset(PANEL_WIDTH - 42, 7)
        collapse.Size = UDim2.fromOffset(28, 28)
        launcher.BackgroundColor3 = if collapsed then COLORS.control else COLORS.controlSelected
        launcher.TextColor3 = if collapsed then COLORS.text else COLORS.accent
        panel.Visible = not collapsed
    end
    launcher.Activated:Connect(function()
        playerGui:SetAttribute(DEBUG_PANEL_OPEN_ATTRIBUTE, collapsed and DEBUG_PANEL_ID or "")
    end)
    collapse.Activated:Connect(function()
        playerGui:SetAttribute(DEBUG_PANEL_OPEN_ATTRIBUTE, collapsed and DEBUG_PANEL_ID or "")
    end)
    playerGui:GetAttributeChangedSignal(DEBUG_PANEL_OPEN_ATTRIBUTE):Connect(function()
        setCollapsed(playerGui:GetAttribute(DEBUG_PANEL_OPEN_ATTRIBUTE) ~= DEBUG_PANEL_ID)
    end)
    setCollapsed(playerGui:GetAttribute(DEBUG_PANEL_OPEN_ATTRIBUTE) ~= DEBUG_PANEL_ID)

    return gui, character, category, weapon, meta, runtimeStats, radiusBox, radiusMinus, radiusPlus, radiusReset, radiusToggle, volumeToggle, targetHitboxToggle, apply, status, statusDot
end

function TestLoadoutController.Start()
    if started or not PublishedDebugAccess.ClientAllowed() then return end
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

        local gui, characterDropdown, categorySelector, weaponDropdown, meta, runtimeStats, radiusBox, radiusMinus, radiusPlus, radiusReset, radiusToggle, volumeToggle, targetHitboxToggle, applyButton, status, statusDot = createGui()
        local playerGui = player:WaitForChild("PlayerGui")
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
            radiusToggle.Text = ringVisible and "MELEE ARC: ON" or "MELEE ARC: OFF"
            radiusToggle.BackgroundColor3 = ringVisible and COLORS.controlSelected or COLORS.control
            radiusToggle.TextColor3 = ringVisible and COLORS.accent or COLORS.text
            ringFolder.Parent = ringVisible and Workspace or nil
        end

        local function renderAttackRadiusRing()
            if not ringVisible then return end
            local character = player.Character
            local root = character and character:FindFirstChild("RootCollider")
            if not root or not root:IsA("BasePart")
                or string.lower(tostring(character:GetAttribute("EquippedWeaponType") or "")) == "bow" then
                for _, part in ipairs(ringParts) do part.Transparency = 1 end
                return
            end
            local radius = math.max(1, tonumber(character:GetAttribute("AttackRadius")) or 7)
            local arc = math.clamp(tonumber(character:GetAttribute("MeleeArcAngle")) or 108, 1, 360)
            local halfAngle = math.rad(arc) * 0.5
            local forward = Vector3.new(root.CFrame.LookVector.X, 0, root.CFrame.LookVector.Z)
            if forward.Magnitude < 1e-5 then return end
            forward = forward.Unit
            rayParams.FilterDescendantsInstances = {character}
            local ground = Workspace:Raycast(root.Position, Vector3.new(0, -64, 0), rayParams)
            local center = Vector3.new(root.Position.X,
                ground and (ground.Position.Y + 0.06) or (root.Position.Y - root.Size.Y * 0.5), root.Position.Z)
            local count = 64
            local sweep = math.rad(arc) / count
            local chord = 2 * radius * math.sin(sweep * 0.5) + 0.03
            for index = 1, count do
                local angle = -halfAngle + (index - 0.5) * sweep
                local direction = CFrame.fromAxisAngle(Vector3.yAxis, angle):VectorToWorldSpace(forward)
                local position = center + direction * radius
                local part = ringParts[index]
                part.Size = Vector3.new(chord, 0.055, 0.10)
                part.CFrame = CFrame.lookAt(position, position + direction) * CFrame.Angles(0, math.pi / 2, 0)
                part.Transparency = 0.18
            end
            for index, sign in ipairs({-1, 1}) do
                local direction = CFrame.fromAxisAngle(Vector3.yAxis, halfAngle * sign):VectorToWorldSpace(forward)
                local line = ringParts[64 + index]
                line.Size = Vector3.new(0.065, 0.055, radius)
                line.CFrame = CFrame.lookAt(center + direction * radius * 0.5, center + direction * radius)
                line.Transparency = 0.24
                local vertical = ringParts[66 + index]
                local pad = 1.5
                local height = math.max(3, root.Size.Y) + pad * 2
                vertical.Size = Vector3.new(0.08, height, 0.08)
                vertical.CFrame = CFrame.new(root.Position.X + direction.X * radius,
                    root.Position.Y, root.Position.Z + direction.Z * radius)
                vertical.Transparency = 0.35
            end
            local camera = Workspace.CurrentCamera
            local ray = ringParts[69]
            if camera then
                local origin = camera.CFrame.Position
                local direction = camera.CFrame.LookVector
                local relative = root.Position - origin
                local start = origin + direction * math.max(0, relative:Dot(direction))
                local length = math.max(0.01, radius)
                ray.Size = Vector3.new(0.045, 0.045, length)
                ray.CFrame = CFrame.lookAt(start + direction * length * 0.5, start + direction * length)
                ray.Transparency = 0.45
            else ray.Transparency = 1 end
        end
        ringConnection = RunService.RenderStepped:Connect(renderAttackRadiusRing)
        setRingVisible(false)
        radiusToggle.Activated:Connect(function() setRingVisible(not ringVisible) end)

        -- M358: no weapon-volume toggle, renderer or gameplay fallback exists.
        -- The legacy label is deliberately inert for discoverability.

        local targetPreview = createTargetHitboxPreview()
        local targetHitboxesVisible = false
        local targetModels = {}
        local nextTargetScanAt = 0

        local function setTargetHitboxesVisible(value: boolean)
            targetHitboxesVisible = value == true
            targetHitboxToggle.Text = targetHitboxesVisible and "TARGET HITBOXES: ON" or "TARGET HITBOXES: OFF"
            targetHitboxToggle.BackgroundColor3 = targetHitboxesVisible and COLORS.controlSelected or COLORS.control
            targetHitboxToggle.TextColor3 = targetHitboxesVisible and COLORS.accent or COLORS.text
            targetPreview.folder.Parent = targetHitboxesVisible and Workspace or nil
        end

        local function refreshTargetModels()
            table.clear(targetModels)
            local ownCharacter = player.Character
            for _, descendant in ipairs(Workspace:GetDescendants()) do
                if descendant:IsA("Model")
                    and descendant ~= ownCharacter
                    and descendant:GetAttribute("Damageable") == true
                    and (tostring(descendant:GetAttribute("CombatHitboxMode") or "") == "precomputed_bone_boxes"
                        or tostring(descendant:GetAttribute("CombatHitboxMode") or "") == "root_bounds_fallback")
                then
                    table.insert(targetModels, descendant)
                end
            end
        end

        local function renderTargetHitboxes()
            if not targetHitboxesVisible then return end
            local now = os.clock()
            if now >= nextTargetScanAt then
                nextTargetScanAt = now + 0.35
                refreshTargetModels()
            end

            local previewIndex = 0
            for _, model in ipairs(targetModels) do
                if model.Parent and model:GetAttribute("Damageable") == true then
                    local debugFolder = model:FindFirstChild("CombatHitboxDebugData")
                    if debugFolder then
                        for _, record in ipairs(debugFolder:GetChildren()) do
                            local anchorValue = record:FindFirstChild("Anchor")
                            local anchor = if anchorValue and anchorValue:IsA("ObjectValue") then anchorValue.Value else nil
                            local localCFrame = record:GetAttribute("LocalCFrame")
                            local size = record:GetAttribute("Size")
                            local zone = tostring(record:GetAttribute("Zone") or "body")
                            local anchorFrame = anchor and debugAnchorFrame(anchor) or nil
                            if anchorFrame and typeof(localCFrame) == "CFrame" and typeof(size) == "Vector3" then
                                previewIndex += 1
                                local frame = anchorFrame * localCFrame
                                local own = player.Character
                                local root = own and own:FindFirstChild("RootCollider")
                                local inside = false
                                if root and root:IsA("BasePart") then
                                    local reach = tonumber(own:GetAttribute("AttackRadius")) or 7
                                    local angle = tonumber(own:GetAttribute("MeleeArcAngle")) or 108
                                    local pad = 1.5
                                    local halfHeight = math.max(1.5, root.Size.Y * 0.5)
                                    inside = MeleeArcGeometry.Contact(frame, size, root.Position,
                                        root.CFrame.LookVector, reach, angle,
                                        root.Position.Y - halfHeight - pad, root.Position.Y + halfHeight + pad) ~= nil
                                end
                                -- Debug colours: green = sector contact, red = outside,
                                -- amber = in sector but physically blocked by a solid wall.
                                local blocked = false
                                if inside and root and root:IsA("BasePart") then
                                    local origin = root.Position + Vector3.new(0, math.min(1, root.Size.Y * 0.25), 0)
                                    local displacement = frame.Position - origin
                                    if displacement.Magnitude > 1e-4 then
                                        rayParams.FilterDescendantsInstances = {own}
                                        local obstruction = Workspace:Raycast(origin, displacement, rayParams)
                                        blocked = obstruction ~= nil and not obstruction.Instance:IsDescendantOf(model)
                                    end
                                end
                                local color = if not inside then COLORS.error
                                    else if blocked then Color3.fromRGB(255, 187, 86) else COLORS.accent
                                local transparency = if inside then 0.63 else 0.87
                                local hitbox = targetPreview.acquire(previewIndex, Enum.PartType.Block, color, transparency)
                                hitbox.CFrame = frame
                                hitbox.Size = size
                            end
                        end
                    end
                end
            end
            targetPreview.hideAfter(previewIndex)
        end

        RunService.RenderStepped:Connect(renderTargetHitboxes)
        setTargetHitboxesVisible(false)
        targetHitboxToggle.Activated:Connect(function()
            setTargetHitboxesVisible(not targetHitboxesVisible)
        end)

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
        local function changeRadiusBy(delta: number)
            local character = player.Character
            local current = tonumber(radiusBox.Text) or (character and tonumber(character:GetAttribute("AttackRadius"))) or 7
            -- Server remains authoritative and clamps to the supported range.
            applyRadiusValue(current + delta)
        end
        radiusMinus.Activated:Connect(function() changeRadiusBy(-0.5) end)
        radiusPlus.Activated:Connect(function() changeRadiusBy(0.5) end)
        radiusReset.Activated:Connect(function()
            applyRadiusValue("default")
        end)
        local initialCharacter = player.Character
        syncRadiusBox(initialCharacter and initialCharacter:GetAttribute("AttackRadius") or catalog.actualAttackRadiusStuds or 7)

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
        local function syncActualCharacter()
            local actual = player.Character
            if not actual then return end
            local radius = actual:GetAttribute("AttackRadius")
            if radius ~= nil and not radiusBox:IsFocused() then syncRadiusBox(radius) end
            runtimeStats.Text = string.format("ACTUAL  HP %.0f/%.0f  ·  DMG %.0f  ·  DEF %.0f\nASPD %.0f  ·  RUN %.0f  ·  RANGE %s",
                tonumber(actual:GetAttribute("HP")) or 0, tonumber(actual:GetAttribute("MaxHP")) or 0,
                tonumber(actual:GetAttribute("Damage")) or 0, tonumber(actual:GetAttribute("Defense")) or 0,
                tonumber(actual:GetAttribute("AttackSpeed")) or 0, tonumber(actual:GetAttribute("RunSpeed")) or 0,
                formatStuds(radius or 0))
        end
        local function syncActualLoadout(force: boolean?)
            local actual = player.Character
            if not actual then return end
            -- Do not silently replace a pending selection while the editor is open.
            if not applying and (force == true or playerGui:GetAttribute(DEBUG_PANEL_OPEN_ATTRIBUTE) ~= DEBUG_PANEL_ID) then
                local slug = tostring(actual:GetAttribute("EquippedWeaponSlug") or "")
                local archetype = tostring(actual:GetAttribute("CharacterArchetype") or "")
                if archetype ~= "" then
                    appliedArchetype = archetype
                    characterDropdown.setValue(archetype, false)
                end
                appliedWeaponSlug = slug
                local category = categoryForSlug(slug)
                categorySelector.setValue(category, false)
                rebuildWeapons(category, slug)
                updateMeta()
            end
        end
        local characterConnections = {}
        local function watchActualCharacter(character: Model?)
            for _, connection in ipairs(characterConnections) do connection:Disconnect() end
            table.clear(characterConnections)
            if character then
                for _, attr in ipairs({"HP", "MaxHP", "Damage", "Defense", "AttackSpeed", "RunSpeed", "AttackRadius"}) do
                    table.insert(characterConnections, character:GetAttributeChangedSignal(attr):Connect(syncActualCharacter))
                end
                table.insert(characterConnections, character:GetAttributeChangedSignal("EquippedWeaponSlug"):Connect(syncActualLoadout))
            end
            syncActualCharacter()
            syncActualLoadout()
        end
        local characterAddedConnection = player.CharacterAdded:Connect(watchActualCharacter)
        watchActualCharacter(player.Character)
        local panelOpenedConnection = playerGui:GetAttributeChangedSignal(DEBUG_PANEL_OPEN_ATTRIBUTE):Connect(function()
            if playerGui:GetAttribute(DEBUG_PANEL_OPEN_ATTRIBUTE) == DEBUG_PANEL_ID then
                syncActualLoadout(true)
                syncActualCharacter()
            end
        end)
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
            characterAddedConnection:Disconnect()
            panelOpenedConnection:Disconnect()
            for _, connection in ipairs(characterConnections) do connection:Disconnect() end
            if ringConnection then ringConnection:Disconnect() end
            ringFolder:Destroy()
        end)
    end)
end

return TestLoadoutController
