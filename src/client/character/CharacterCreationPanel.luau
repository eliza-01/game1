--!strict
-- Presentation shell: responsive right-hand character editor with a fixed header,
-- gender switch, category navigation and sticky actions. Only the active category
-- scrolls; this module has no knowledge of assets, spawning or game state.
local UserInputService = game:GetService("UserInputService")
local Language = require(script.Parent.Parent:WaitForChild("localization"):WaitForChild("LanguageState"))
local Panel = {}
local INK = Color3.fromRGB(241, 234, 218)
local MUTED = Color3.fromRGB(179, 189, 193)
local GOLD = Color3.fromRGB(215, 179, 115)
local DARK = Color3.fromRGB(17, 24, 30)
local NORMAL = Color3.fromRGB(39, 51, 58)
local ACTIVE = Color3.fromRGB(81, 107, 98)
local TABS = {"hair", "eyebrows", "eyes", "head"}

local function rounded(parent: Instance, radius: number)
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, radius)
    corner.Parent = parent
end

local function stroke(parent: GuiObject, color: Color3, transparency: number)
    local border = Instance.new("UIStroke")
    border.Color = color
    border.Transparency = transparency
    border.Thickness = 1
    border.ApplyStrokeMode = Enum.ApplyStrokeMode.Border
    border.Parent = parent
end

local function text(parent: Instance, name: string, size: number, font: Enum.Font, color: Color3): TextLabel
    local label = Instance.new("TextLabel")
    label.Name = name
    label.BackgroundTransparency = 1
    label.Font = font
    label.TextSize = size
    label.TextColor3 = color
    label.TextXAlignment = Enum.TextXAlignment.Left
    label.TextYAlignment = Enum.TextYAlignment.Center
    label.TextTruncate = Enum.TextTruncate.AtEnd
    label.Parent = parent
    return label
end

local function action(parent: Instance, name: string, size: UDim2, position: UDim2, primary: boolean): TextButton
    local button = Instance.new("TextButton")
    button.Name = name
    button.Size = size
    button.Position = position
    button.BackgroundColor3 = if primary then GOLD else NORMAL
    button.TextColor3 = if primary then DARK else INK
    button.Font = Enum.Font.GothamSemibold
    button.TextSize = 15
    button.TextWrapped = true
    button.AutoButtonColor = true
    button.Parent = parent
    rounded(button, 10)
    stroke(button, if primary then GOLD else Color3.fromRGB(88, 102, 109), if primary then 0.45 else 0.72)
    return button
end

local function uiParent(parent: Instance, settings: any)
    local root = Instance.new("Frame")
    root.Name = "CharacterCreationPanel"
    root.AnchorPoint = Vector2.new(1, 0.5)
    root.Position = UDim2.new(1, -16, 0.5, 0)
    root.Size = UDim2.fromOffset(460, 720)
    root.BackgroundColor3 = DARK
    root.BackgroundTransparency = 0.035
    root.BorderSizePixel = 0
    root.ClipsDescendants = true
    root.Parent = parent
    rounded(root, 18)
    stroke(root, Color3.fromRGB(144, 143, 119), 0.47)
    local gradient = Instance.new("UIGradient")
    gradient.Rotation = 90
    gradient.Color = ColorSequence.new(Color3.fromRGB(33, 44, 50), DARK)
    gradient.Parent = root
    local goldLine = Instance.new("Frame")
    goldLine.Name = "GoldAccent"
    goldLine.BackgroundColor3 = GOLD
    goldLine.BorderSizePixel = 0
    goldLine.Size = UDim2.new(1, 0, 0, 3)
    goldLine.Parent = root
    local header = Instance.new("Frame")
    header.Name = "Header"
    header.BackgroundTransparency = 1
    header.Position = UDim2.fromOffset(22, 16)
    header.Size = UDim2.new(1, -44, 0, 70)
    header.Parent = root
    local eyebrow = text(header, "GameBrand", 11, Enum.Font.GothamBold, GOLD)
    eyebrow.Text = "GAME1  /  CHARACTER"
    eyebrow.Position = UDim2.fromOffset(0, 0)
    eyebrow.Size = UDim2.new(1, 0, 0, 19)
    local heading = text(header, "CreationTitle", 25, Enum.Font.GothamBold, INK)
    heading.Position = UDim2.fromOffset(0, 20)
    heading.Size = UDim2.new(1, -58, 0, 34)
    local tagline = text(header, "CreationSubtitle", 12, Enum.Font.Gotham, MUTED)
    tagline.TextWrapped = true
    tagline.TextTruncate = Enum.TextTruncate.None
    tagline.Position = UDim2.fromOffset(0, 53)
    tagline.Size = UDim2.new(1, -58, 0, 40)
    local genders = Instance.new("Frame")
    genders.Name = "GenderSelection"
    genders.Position = UDim2.fromOffset(22, 100)
    genders.Size = UDim2.new(1, -44, 0, 50)
    genders.BackgroundTransparency = 1
    genders.Parent = root
    local male = action(genders, "SelectMale", UDim2.new(0.5, -5, 1, 0), UDim2.fromOffset(0, 0), false)
    local female = action(genders, "SelectFemale", UDim2.new(0.5, -5, 1, 0), UDim2.new(0.5, 5, 0, 0), false)
    local tabs = Instance.new("Frame")
    tabs.Name = "AppearanceTabs"
    tabs.BackgroundTransparency = 1
    tabs.Position = UDim2.fromOffset(22, 164)
    tabs.Size = UDim2.new(1, -44, 0, 43)
    tabs.Parent = root
    local tabButtons: {[string]: TextButton} = {}
    for i, key in ipairs(TABS) do
        local button = action(tabs, "Tab" .. key, UDim2.new(0.25, -6, 1, 0), UDim2.new((i - 1) * 0.25, 3, 0, 0), false)
        button.Font = Enum.Font.GothamMedium
        button.TextSize = 13
        tabButtons[key] = button
    end
    local separator = Instance.new("Frame")
    separator.Name = "ContentSeparator"
    separator.BackgroundColor3 = Color3.fromRGB(95, 103, 102)
    separator.BackgroundTransparency = 0.5
    separator.BorderSizePixel = 0
    separator.Position = UDim2.fromOffset(22, 216)
    separator.Size = UDim2.new(1, -44, 0, 1)
    separator.Parent = root
    local selectionCard = Instance.new("Frame")
    selectionCard.Name = "CharacterSelectionCard"
    selectionCard.Position = UDim2.fromOffset(22, 125)
    selectionCard.Size = UDim2.new(1, -44, 0, 136)
    selectionCard.BackgroundColor3 = Color3.fromRGB(38, 54, 61)
    selectionCard.BorderSizePixel = 0
    selectionCard.Visible = false
    selectionCard.Parent = root
    rounded(selectionCard, 12)
    stroke(selectionCard, Color3.fromRGB(142, 125, 91), 0.53)
    local selectionCaption = text(selectionCard, "SelectionCaption", 12, Enum.Font.GothamBold, GOLD)
    selectionCaption.Position = UDim2.fromOffset(18, 14)
    selectionCaption.Size = UDim2.new(1, -36, 0, 24)
    selectionCaption.Text = "GAME1  /  CHARACTER SLOT 01"
    local selectionName = text(selectionCard, "SelectionName", 24, Enum.Font.GothamBold, INK)
    selectionName.Position = UDim2.fromOffset(18, 45)
    selectionName.Size = UDim2.new(1, -36, 0, 43)
    local selectionHint = text(selectionCard, "SelectionHint", 13, Enum.Font.Gotham, MUTED)
    selectionHint.TextWrapped = true
    selectionHint.TextTruncate = Enum.TextTruncate.None
    selectionHint.Position = UDim2.fromOffset(18, 99)
    selectionHint.Size = UDim2.new(1, -36, 0, 36)

    local content = Instance.new("ScrollingFrame")
    content.Name = "AppearanceContent"
    content.BackgroundTransparency = 1
    content.BorderSizePixel = 0
    content.ScrollBarThickness = 4
    content.ScrollBarImageColor3 = GOLD
    content.ScrollingDirection = Enum.ScrollingDirection.Y
    content.AutomaticCanvasSize = Enum.AutomaticSize.Y
    content.CanvasSize = UDim2.fromOffset(0, 0)
    content.Position = UDim2.fromOffset(22, 230)
    content.Size = UDim2.new(1, -44, 1, -376)
    content.Parent = root
    local inside = Instance.new("UIPadding")
    inside.PaddingRight = UDim.new(0, 8)
    inside.PaddingBottom = UDim.new(0, 12)
    inside.Parent = content
    local editor = Instance.new("Frame")
    editor.Name = "AppearanceEditor"
    editor.BackgroundTransparency = 1
    editor.AutomaticSize = Enum.AutomaticSize.Y
    editor.Size = UDim2.new(1, -5, 0, 0)
    editor.Parent = content
    local vertical = Instance.new("UIListLayout")
    vertical.Padding = UDim.new(0, 12)
    vertical.SortOrder = Enum.SortOrder.LayoutOrder
    vertical.Parent = editor
    local footer = Instance.new("Frame")
    footer.Name = "CreationActions"
    footer.AnchorPoint = Vector2.new(0, 1)
    footer.Position = UDim2.new(0, 22, 1, -17)
    footer.Size = UDim2.new(1, -44, 0, 132)
    footer.BackgroundTransparency = 1
    footer.Parent = root
    local footLine = Instance.new("Frame")
    footLine.Name = "FooterSeparator"
    footLine.BackgroundColor3 = Color3.fromRGB(95, 103, 102)
    footLine.BackgroundTransparency = 0.5
    footLine.BorderSizePixel = 0
    footLine.Size = UDim2.new(1, 0, 0, 1)
    footLine.Parent = footer
    local enter = action(footer, "EnterWorld", UDim2.new(1, 0, 0, 48), UDim2.fromOffset(0, 4), true)
    local status = text(footer, "CreationStatus", 12, Enum.Font.GothamMedium, Color3.fromRGB(238, 187, 154))
    status.TextWrapped = true
    status.TextTruncate = Enum.TextTruncate.None
    status.Position = UDim2.fromOffset(0, 109)
    status.Size = UDim2.new(1, 0, 0, 22)
    status.Text = ""
    local overlay = Instance.new("TextButton")
    overlay.Name = "CreationSubmittingOverlay"
    overlay.Size = UDim2.fromScale(1, 1)
    overlay.BackgroundColor3 = DARK
    overlay.BackgroundTransparency = 0.12
    overlay.BorderSizePixel = 0
    overlay.Text = ""
    overlay.AutoButtonColor = false
    overlay.Modal = false
    overlay.Active = true
    overlay.ZIndex = 100
    overlay.Visible = false
    overlay.Parent = parent
    local overlayLabel = text(overlay, "Message", 22, Enum.Font.GothamSemibold, GOLD)
    overlayLabel.AnchorPoint = Vector2.new(0.5, 0.5)
    overlayLabel.Position = UDim2.fromScale(0.5, 0.5)
    overlayLabel.Size = UDim2.new(0.9, 0, 0, 80)
    overlayLabel.TextXAlignment = Enum.TextXAlignment.Center
    overlayLabel.TextWrapped = true
    overlayLabel.ZIndex = 101
    -- Safe-area dimensions also handle camera replacement, rotation and resize.
    local function resize()
        local viewport = if parent:IsA("ScreenGui") then parent.AbsoluteSize else Vector2.new(1280, 720)
        local mobile = viewport.X < 840 or (UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled)
        local portrait = mobile and viewport.X < viewport.Y
        local compact = viewport.Y < 570 or portrait
        local mode = root:GetAttribute("PresentationMode")
        local editing = mode == "creation"
        local selection = mode == "selection"
        local requested = tonumber(if mobile then settings.mobilePanelWidthPx else settings.desktopPanelWidthPx) or 460
        local width = math.max(1, math.min(math.max(if mobile then 300 else 410, requested), viewport.X - 20))
        local availableHeight = if portrait then math.floor(viewport.Y * 0.56) else viewport.Y - 24
        local height = math.max(1, math.min(if editing then 850 elseif selection then 420 else 180, availableHeight))
        root.Size = UDim2.fromOffset(width, height)
        root.AnchorPoint = if portrait then Vector2.new(0.5, 1) else Vector2.new(1, 0.5)
        root.Position = if portrait then UDim2.new(0.5, 0, 1, -8)
            else UDim2.new(1, if mobile then -10 else -16, 0.5, 0)
        header.Position = UDim2.fromOffset(16, if compact then 8 else 16)
        header.Size = UDim2.new(1, -32, 0, if compact then 50 else 82)
        heading.Position = UDim2.fromOffset(0, if compact then 14 else 20)
        heading.Size = UDim2.new(1, 0, 0, 31)
        heading.TextSize = if compact then 19 else 25
        tagline.Visible = not compact or not editing
        tagline.Position = UDim2.fromOffset(0, if compact then 43 else 53)
        tagline.Size = UDim2.new(1, 0, 0, 40)
        genders.Position = UDim2.fromOffset(16, if compact then 58 else 105)
        genders.Size = UDim2.new(1, -32, 0, if compact then 40 else 46)
        local visibleCount = 0
        for _, button in pairs(tabButtons) do if button.Visible then visibleCount += 1 end end
        local rows = if mobile and not compact and visibleCount > 2 then 2 else 1
        local tabY = if compact then 104 else 160
        local tabHeight = if visibleCount == 0 then 0 elseif rows == 2 then 86 else 40
        tabs.Position = UDim2.fromOffset(16, tabY)
        tabs.Size = UDim2.new(1, -32, 0, tabHeight)
        local showing = {}
        for _, key in ipairs(TABS) do
            if tabButtons[key].Visible then table.insert(showing, tabButtons[key]) end
        end
        local columns = if rows == 2 then 2 else math.max(1, #showing)
        for i, button in ipairs(showing) do
            button.Size = UDim2.new(1 / columns, -4, 0, 40)
            button.Position = UDim2.new(((i - 1) % columns) / columns, 2, 0, math.floor((i - 1) / columns) * 44)
            button.TextSize = if compact then 11 else 13
            button.TextWrapped = true
        end
        local contentY = tabY + tabHeight + 12
        local footerHeight = 84
        local bottom = if compact then 8 else 16
        separator.Position = UDim2.fromOffset(16, contentY - 7)
        separator.Size = UDim2.new(1, -32, 0, 1)
        content.Position = UDim2.fromOffset(16, contentY)
        content.Size = UDim2.new(1, -32, 0, math.max(1, height - contentY - footerHeight - bottom))
        footer.Position = UDim2.new(0, 16, 1, -bottom)
        footer.Size = UDim2.new(1, -32, 0, footerHeight)
        local enterY = 4
        local enterHeight = if compact then 38 else 44
        enter.Position = UDim2.fromOffset(0, enterY)
        enter.Size = UDim2.new(1, 0, 0, enterHeight)
        status.Position = UDim2.fromOffset(0, enterY + enterHeight + 3)
        status.Size = UDim2.new(1, 0, 0, math.max(18, footerHeight - enterY - enterHeight - 3))
        selectionCard.Position = UDim2.fromOffset(16, if compact then 92 else 112)
        selectionCard.Size = UDim2.new(1, -32, 0, if compact then 100 else 150)
        selectionHint.Visible = not compact
    end
    if parent:IsA("ScreenGui") then parent:GetPropertyChangedSignal("AbsoluteSize"):Connect(resize) end
    resize()
    return {panel = root, title = heading, subtitle = tagline,
        male = male, female = female, enter = enter,
        overlay = overlay, overlayLabel = overlayLabel,
        status = status, tabs = tabButtons, content = content, editor = editor,
        selectionCard = selectionCard, selectionName = selectionName, selectionHint = selectionHint,
        genders = genders, tabBar = tabs, separator = separator, layout = resize}
end

function Panel.Create(parent: Instance, settings: any): any
    return uiParent(parent, settings)
end

-- Selection is deliberately a separate UI mode, not a continuation of the editor.
function Panel.SetMode(views: any, stage: string)
    local editing = stage == "creation"
    local ready = stage == "selection"
    views.panel:SetAttribute("PresentationMode", stage)
    views.selectionCard.Visible = ready
    views.male.Visible = editing
    views.female.Visible = editing
    views.content.Visible = editing
    for _, tab in pairs(views.tabs) do tab.Visible = editing and tab.Visible end
    views.genders.Visible = editing
    views.tabBar.Visible = editing
    views.separator.Visible = editing
    views.enter.Visible = editing or ready
    views.layout()
end

function Panel.SetSelection(views: any, archetype: string?)
    views.selectionName.Text = if not archetype then "—" else Language.Translate(if archetype == "human_male" then "creation.male" else "creation.female")
    views.selectionHint.Text = Language.Translate(if archetype then "creation.selection_subtitle" else "creation.loading_profile")
end

function Panel.SetSubmitting(views: any, busy: boolean, message: string)
    views.overlayLabel.Text = message
    views.overlay.Visible = busy
    views.overlay.Modal = busy
end

function Panel.UpdateTabs(views: any, selected: boolean, active: string?, visible: {[string]: boolean})
    for key, button in pairs(views.tabs) do
        button.Visible = visible[key] == true
        button.Text = Language.Translate("creation." .. key)
        button.Active = selected and button.Visible
        button.AutoButtonColor = button.Active
        button.BackgroundColor3 = if selected and key == active then ACTIVE else NORMAL
        button.TextColor3 = if selected and key == active then INK else MUTED
        button.BackgroundTransparency = if selected then 0 else 0.45
    end
    views.layout()
end

return Panel
