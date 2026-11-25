--!strict
-- Presentation shell: responsive right-hand character editor with a fixed header,
-- gender switch, category navigation and sticky actions. Only the active category
-- scrolls; this module has no knowledge of assets, spawning or game state.
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Language = require(script.Parent.Parent:WaitForChild("localization"):WaitForChild("LanguageState"))
local Panel = {}
local INK = Color3.fromRGB(241, 234, 218)
local MUTED = Color3.fromRGB(179, 189, 193)
local GOLD = Color3.fromRGB(215, 179, 115)
local DARK = Color3.fromRGB(17, 24, 30)
local NORMAL = Color3.fromRGB(39, 51, 58)
local ACTIVE = Color3.fromRGB(81, 107, 98)
local TABS = table.freeze({"hair", "eyebrows", "eyes"})
Panel.Categories = TABS

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
    button.Font = Enum.Font.GothamBold
    button.TextSize = 15
    button.TextWrapped = true
    button.AutoButtonColor = true
    button.Parent = parent
    rounded(button, 10)
    stroke(button, if primary then GOLD else Color3.fromRGB(88, 102, 109), if primary then 0.45 else 0.72)
    return button
end

local function buildStickman(parent: Instance): Frame
    local runner = Instance.new("Frame")
    runner.Name = "LoadingRunner"
    runner.BackgroundTransparency = 1
    runner.Size = UDim2.fromOffset(28, 38)
    runner.Parent = parent

    local head = Instance.new("Frame")
    head.Name = "Head"
    head.Size = UDim2.fromOffset(10, 10)
    head.Position = UDim2.fromOffset(9, 0)
    head.BackgroundColor3 = INK
    head.BorderSizePixel = 0
    head.Parent = runner
    rounded(head, 10)

    local function limb(name: string, size: Vector2, pos: Vector2, rotation: number, color: Color3)
        local item = Instance.new("Frame")
        item.Name = name
        item.Size = UDim2.fromOffset(size.X, size.Y)
        item.Position = UDim2.fromOffset(pos.X, pos.Y)
        item.BackgroundColor3 = color
        item.BorderSizePixel = 0
        item.Rotation = rotation
        item.Parent = runner
        rounded(item, math.min(size.X, size.Y))
        return item
    end

    limb("Body", Vector2.new(3, 14), Vector2.new(12, 10), 0, INK)
    limb("LeftArm", Vector2.new(3, 12), Vector2.new(6, 13), 55, INK)
    limb("RightArm", Vector2.new(3, 12), Vector2.new(16, 12), -42, INK)
    limb("LeftLeg", Vector2.new(3, 12), Vector2.new(8, 22), 45, INK)
    limb("RightLeg", Vector2.new(3, 12), Vector2.new(15, 22), -55, INK)
    return runner
end

local function uiParent(parent: Instance, settings: any, overlayParent: ScreenGui)
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
    local header = Instance.new("Frame")
    header.Name = "Header"
    header.BackgroundTransparency = 1
    header.Position = UDim2.fromOffset(22, 16)
    header.Size = UDim2.new(1, -44, 0, 70)
    header.Parent = root
    local heading = text(header, "CreationTitle", 25, Enum.Font.GothamBold, INK)
    heading.Position = UDim2.fromOffset(0, 0)
    heading.Size = UDim2.new(1, -58, 0, 34)
    local tagline = text(header, "CreationSubtitle", 12, Enum.Font.GothamBold, MUTED)
    tagline.TextWrapped = true
    tagline.TextTruncate = Enum.TextTruncate.None
    tagline.Position = UDim2.fromOffset(0, 34)
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
        local button = action(tabs, "Tab" .. key, UDim2.new(1 / #TABS, -6, 1, 0), UDim2.new((i - 1) / #TABS, 3, 0, 0), false)
        button.Font = Enum.Font.GothamBold
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
    selectionCaption.Text = "1/5"
    local selectionName = text(selectionCard, "SelectionName", 24, Enum.Font.GothamBold, INK)
    selectionName.Position = UDim2.fromOffset(18, 34)
    selectionName.Size = UDim2.new(1, -36, 0, 34)
    selectionName.TextScaled = true
    local nameLimit = Instance.new("UITextSizeConstraint")
    nameLimit.MaxTextSize = 24
    nameLimit.Parent = selectionName
    local selectionLevel = text(selectionCard, "SelectionLevel", 15, Enum.Font.GothamBold, MUTED)
    selectionLevel.Position = UDim2.fromOffset(18, 70)
    selectionLevel.Size = UDim2.new(1, -36, 0, 24)

    local content = Instance.new("ScrollingFrame")
    content.Name = "AppearanceContent"
    content.BackgroundTransparency = 1
    content.BorderSizePixel = 0
    content.ScrollBarThickness = 4
    content.ScrollBarImageColor3 = GOLD
    content.ScrollingDirection = Enum.ScrollingDirection.Y
    content.AutomaticCanvasSize = Enum.AutomaticSize.None
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
    local canvasDirty = true
    local function invalidateCanvas() canvasDirty = true end
    vertical:GetPropertyChangedSignal("AbsoluteContentSize"):Connect(invalidateCanvas)
    content:GetPropertyChangedSignal("AbsoluteWindowSize"):Connect(invalidateCanvas)
    -- Keep the old canvas while Render replaces all controls. Only commit a
    -- settled layout, never the transient empty/zero-height editor.
    local canvasConnection = RunService.PreRender:Connect(function()
        if not canvasDirty or not content.Visible then return end
        canvasDirty = false
        local position = content.CanvasPosition
        -- The editor's top-level rows have explicit pixel heights. Measuring
        -- them directly avoids stale AbsoluteContentSize during a rebuild.
        local height, rows = 12, 0
        for _, child in editor:GetChildren() do
            if child:IsA("GuiObject") and child.Visible then
                height += child.Size.Y.Offset
                rows += 1
            end
        end
        height += math.max(0, rows - 1) * vertical.Padding.Offset
        content.CanvasSize = UDim2.fromOffset(0, height)
        content.CanvasPosition = Vector2.new(0, math.clamp(position.Y, 0,
            math.max(0, height - content.AbsoluteWindowSize.Y)))
    end)
    root.Destroying:Connect(function() canvasConnection:Disconnect() end)
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
    -- The current profile store has one occupied slot. Reserve the action visually
    -- without allowing a second character to overwrite it. A future multi-slot
    -- lifecycle can enable this button once it has an authoritative free slot.
    local newCharacter = action(footer, "NewCharacter", UDim2.new(1, 0, 0, 44), UDim2.fromOffset(0, 4), false)
    newCharacter.Visible = false
    newCharacter.Active = false
    newCharacter.Interactable = false
    newCharacter.Selectable = false
    newCharacter.AutoButtonColor = false
    newCharacter.TextColor3 = MUTED
    newCharacter.BackgroundColor3 = Color3.fromRGB(45, 55, 60)
    local enter = action(footer, "EnterWorld", UDim2.new(1, 0, 0, 48), UDim2.fromOffset(0, 4), true)
    local status = text(footer, "CreationStatus", 12, Enum.Font.GothamBold, Color3.fromRGB(238, 187, 154))
    status.TextWrapped = true
    status.TextTruncate = Enum.TextTruncate.None
    status.Position = UDim2.fromOffset(0, 109)
    status.Size = UDim2.new(1, 0, 0, 22)
    status.Text = ""
    local overlay = Instance.new("TextButton")
    overlay.Name = "CreationSubmittingOverlay"
    overlay.Size = UDim2.fromScale(1, 1)
    overlay.BackgroundColor3 = DARK
    overlay.BackgroundTransparency = 0
    overlay.BorderSizePixel = 0
    overlay.Text = ""
    overlay.AutoButtonColor = false
    overlay.Modal = false
    overlay.Active = true
    overlay.ZIndex = 100
    overlay.Visible = false
    overlay.Parent = overlayParent
    local overlayCard = Instance.new("Frame")
    overlayCard.Name = "LoadingCard"
    overlayCard.AnchorPoint = Vector2.new(0.5, 0.5)
    overlayCard.Position = UDim2.fromScale(0.5, 0.5)
    overlayCard.Size = UDim2.fromOffset(460, 190)
    overlayCard.BackgroundColor3 = Color3.fromRGB(24, 34, 39)
    overlayCard.BorderSizePixel = 0
    overlayCard.ZIndex = 101
    overlayCard.Parent = overlay
    rounded(overlayCard, 16)
    stroke(overlayCard, Color3.fromRGB(144, 143, 119), 0.47)
    local overlayLabel = text(overlayCard, "Message", 22, Enum.Font.GothamBold, GOLD)
    overlayLabel.AnchorPoint = Vector2.new(0.5, 0)
    overlayLabel.Position = UDim2.fromScale(0.5, 0)
    overlayLabel.Size = UDim2.new(0.88, 0, 0, 60)
    overlayLabel.TextXAlignment = Enum.TextXAlignment.Center
    overlayLabel.TextYAlignment = Enum.TextYAlignment.Bottom
    overlayLabel.TextWrapped = true
    overlayLabel.ZIndex = 102
    local runnerLane = Instance.new("Frame")
    runnerLane.Name = "RunnerLane"
    runnerLane.AnchorPoint = Vector2.new(0.5, 0)
    runnerLane.Position = UDim2.new(0.5, 0, 0, 74)
    runnerLane.Size = UDim2.new(0.82, 0, 0, 42)
    runnerLane.BackgroundTransparency = 1
    runnerLane.ZIndex = 102
    runnerLane.Parent = overlayCard
    local runner = buildStickman(runnerLane)
    runner.AnchorPoint = Vector2.new(0.5, 0)
    runner.Position = UDim2.new(0, 14, 0, 2)
    runner.ZIndex = 103
    for _, child in ipairs(runner:GetDescendants()) do if child:IsA("GuiObject") then child.ZIndex = 103 end end
    local progressTrack = Instance.new("Frame")
    progressTrack.Name = "ProgressTrack"
    progressTrack.AnchorPoint = Vector2.new(0.5, 0)
    progressTrack.Position = UDim2.new(0.5, 0, 0, 126)
    progressTrack.Size = UDim2.new(0.82, 0, 0, 16)
    progressTrack.BackgroundColor3 = Color3.fromRGB(42, 55, 62)
    progressTrack.BorderSizePixel = 0
    progressTrack.ClipsDescendants = true
    progressTrack.ZIndex = 102
    progressTrack.Parent = overlayCard
    rounded(progressTrack, 12)
    local progressFill = Instance.new("Frame")
    progressFill.Name = "Fill"
    progressFill.Size = UDim2.new(0, 0, 1, 0)
    progressFill.BackgroundColor3 = GOLD
    progressFill.BorderSizePixel = 0
    progressFill.ZIndex = 103
    progressFill.Parent = progressTrack
    rounded(progressFill, 12)
    local progressValue = text(overlayCard, "ProgressValue", 14, Enum.Font.GothamBold, INK)
    progressValue.AnchorPoint = Vector2.new(0.5, 0)
    progressValue.Position = UDim2.new(0.5, 0, 0, 148)
    progressValue.Size = UDim2.new(0.82, 0, 0, 24)
    progressValue.TextXAlignment = Enum.TextXAlignment.Center
    progressValue.ZIndex = 102
    progressValue.Text = ""
    local recovery = action(overlayCard, "ReturnToSelection", UDim2.new(0.82, 0, 0, 44), UDim2.new(0.09, 0, 0, 125), false)
    recovery.ZIndex = 105
    recovery.Visible = false
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
        local availableHeight = if portrait and editing then math.max(math.floor(viewport.Y * 0.70), math.min(420, viewport.Y - 24)) else viewport.Y - 24
        local height = math.max(1, math.min(if editing then 850 elseif selection then 300 else 180, availableHeight))
        root.Size = UDim2.fromOffset(width, height)
        root.AnchorPoint = if portrait then Vector2.new(0.5, 1) else Vector2.new(1, 0.5)
        root.Position = if portrait then UDim2.new(0.5, 0, 1, -8)
            else UDim2.new(1, if mobile then -10 else -16, 0.5, 0)
        header.Position = UDim2.fromOffset(16, if compact then 8 else 16)
        header.Size = UDim2.new(1, -32, 0, if compact then 50 else 82)
        heading.Position = UDim2.fromOffset(0, 0)
        heading.Size = UDim2.new(1, 0, 0, 31)
        heading.TextSize = if compact then 19 else 25
        tagline.Visible = editing and not compact or mode == "storage_unavailable"
        tagline.Position = UDim2.fromOffset(0, 34)
        tagline.Size = UDim2.new(1, 0, 0, 40)
        genders.Position = UDim2.fromOffset(16, if compact then 42 else 86)
        genders.Size = UDim2.new(1, -32, 0, if compact then 40 else 46)
        local visibleCount = 0
        for _, button in pairs(tabButtons) do if button.Visible then visibleCount += 1 end end
        local rows = 1 -- Three compact tabs always fit one row.
        local tabY = if compact then 88 else 141
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
        local enterHeight = if compact then 38 else 44
        local newActionSpace = if selection then enterHeight + 6 else 0
        local footerHeight = (if compact then 64 else 84) + newActionSpace
        local bottom = if compact then 8 else 16
        separator.Position = UDim2.fromOffset(16, contentY - 7)
        separator.Size = UDim2.new(1, -32, 0, 1)
        content.Position = UDim2.fromOffset(16, contentY)
        content.Size = UDim2.new(1, -32, 0, math.max(1, height - contentY - footerHeight - bottom))
        footer.Position = UDim2.new(0, 16, 1, -bottom)
        footer.Size = UDim2.new(1, -32, 0, footerHeight)
        newCharacter.Position = UDim2.fromOffset(0, 4)
        newCharacter.Size = UDim2.new(1, 0, 0, enterHeight)
        local enterY = 4 + newActionSpace
        enter.Position = UDim2.fromOffset(0, enterY)
        enter.Size = UDim2.new(1, 0, 0, enterHeight)
        status.Position = UDim2.fromOffset(0, enterY + enterHeight + 3)
        status.Size = UDim2.new(1, 0, 0, math.max(18, footerHeight - enterY - enterHeight - 3))
        selectionCard.Position = UDim2.fromOffset(16, 48)
        local cardHeight = math.max(1, height - 48 - footerHeight - bottom)
        selectionCard.Size = UDim2.new(1, -32, 0, cardHeight)
        selectionCaption.Position = UDim2.fromOffset(18, 6)
        selectionCaption.Size = UDim2.new(1, -36, 0.23, 0)
        selectionName.Position = UDim2.new(0, 18, 0.27, 0)
        selectionName.Size = UDim2.new(1, -36, 0.36, 0)
        selectionLevel.Position = UDim2.new(0, 18, 0.66, 0)
        selectionLevel.Size = UDim2.new(1, -36, 0.26, 0)
        overlayCard.Size = UDim2.fromOffset(math.max(1, math.min(viewport.X - 32, 460)), 190)
    end
    if parent:IsA("ScreenGui") then parent:GetPropertyChangedSignal("AbsoluteSize"):Connect(resize) end
    resize()
    return {panel = root, title = heading, subtitle = tagline,
        male = male, female = female, enter = enter, newCharacter = newCharacter,
        overlay = overlay, overlayCard = overlayCard, overlayLabel = overlayLabel, recovery = recovery,
        overlayRunner = runner, overlayTrack = progressTrack, overlayFill = progressFill, overlayValue = progressValue,
        status = status, tabs = tabButtons, content = content, editor = editor, invalidateCanvas = invalidateCanvas,
        selectionCard = selectionCard, selectionName = selectionName, selectionLevel = selectionLevel, selectionCaption = selectionCaption,
        genders = genders, tabBar = tabs, separator = separator, layout = resize}
end

function Panel.Create(parent: Instance, settings: any, overlayParent: ScreenGui): any
    return uiParent(parent, settings, overlayParent)
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
    views.newCharacter.Visible = ready
    views.newCharacter.Text = Language.Translate("creation.new_character")
    views.enter.Visible = editing or ready
    views.layout()
end

function Panel.SetSelection(views: any, archetype: string?)
    views.selectionCaption.Visible = archetype ~= nil
    views.selectionLevel.Visible = archetype ~= nil
    views.selectionName.Text = if not archetype then Language.Translate("creation.loading_profile")
        else Language.Translate(if archetype == "human_male" then "creation.human_male" else "creation.human_female")
    views.selectionLevel.Text = Language.Translate("creation.selection_level", {level = 0})
end

-- Animate by elapsed time, not by percent updates; no idle RenderStepped work.
local function setRunnerPose(runner: Frame, time: number)
    local stride = math.sin(time * math.pi * 5)
    local leftArm = runner:FindFirstChild("LeftArm") :: Frame
    local rightArm = runner:FindFirstChild("RightArm") :: Frame
    local leftLeg = runner:FindFirstChild("LeftLeg") :: Frame
    local rightLeg = runner:FindFirstChild("RightLeg") :: Frame
    leftArm.Rotation = 15 + 55 * stride
    rightArm.Rotation = -15 - 55 * stride
    leftLeg.Rotation = 48 * stride
    rightLeg.Rotation = -48 * stride
end

local function setOverlay(views: any, busy: boolean, message: string, progress: number?)
    views.recovery.Visible = false
    views.overlayTrack.Visible = true
    views.overlayRunner.Visible = true
    views.overlayValue.Visible = true
    views.overlayLabel.Text = message
    views.overlay.Visible = busy
    views.overlay.Modal = busy
    views.overlayProgress = if progress ~= nil then math.clamp(progress, 0, 1) else nil
    if not busy then
        if views.runnerConnection then views.runnerConnection:Disconnect(); views.runnerConnection = nil end
        return
    end
    local function render()
        local elapsed = os.clock() - views.runnerStart
        local value = views.overlayProgress
        local position = if value ~= nil then value else (math.sin(elapsed * 2.6) + 1) * 0.5
        views.overlayFill.Size = UDim2.new(if value ~= nil then value else 0.22, 0, 1, 0)
        views.overlayFill.Position = UDim2.new(if value ~= nil then 0 else position * 0.78, 0, 0, 0)
        views.overlayValue.Text = if value ~= nil then string.format("%d%%", math.floor(value * 100 + 0.5)) else ""
        views.overlayRunner.Position = UDim2.new(position, 14 - 28 * position, 0, 2 - 2 * math.abs(math.sin(elapsed * math.pi * 5)))
        setRunnerPose(views.overlayRunner, elapsed)
    end
    if not views.runnerConnection then
        views.runnerStart = os.clock()
        views.runnerConnection = RunService.RenderStepped:Connect(render)
        if not views.runnerCleanupBound then
            views.runnerCleanupBound = true
            views.overlay.Destroying:Once(function()
                if views.runnerConnection then views.runnerConnection:Disconnect(); views.runnerConnection = nil end
            end)
        end
    end
    render()
end

function Panel.SetLoading(views: any, busy: boolean, message: string, progress: number)
    setOverlay(views, busy, message, progress)
end

function Panel.SetSubmitting(views: any, busy: boolean, message: string, progress: number?)
    setOverlay(views, busy, message, progress)
end

function Panel.SetRecovery(views: any, message: string)
    setOverlay(views, true, message, nil)
    if views.runnerConnection then views.runnerConnection:Disconnect(); views.runnerConnection = nil end
    views.overlayTrack.Visible = false
    views.overlayRunner.Visible = false
    views.overlayValue.Visible = false
    views.recovery.Text = Language.Translate("settings.change_character")
    views.recovery.Visible = true
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
