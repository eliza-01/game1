local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")

local MovementDebugController = {}
local started = false
local player = Players.LocalPlayer

local PANEL_WIDTH = 336
local PANEL_EXPANDED_HEIGHT = 486
local PANEL_COLLAPSED_SIZE = 44
local PANEL_X = 16
local PANEL_Y = 202
local CONTENT_WIDTH = PANEL_WIDTH - 32
local DEBUG_PANEL_OPEN_ATTRIBUTE = "Game1DebugPanelOpen"
local DEBUG_PANEL_ID = "MV"
local CATALOG_POLL_SECONDS = 0.75
local DEFAULT_RUN_SPEED_UNITS_PER_STUD = 10

local COLORS = {
    panel = Color3.fromRGB(15, 20, 27),
    panelRaised = Color3.fromRGB(20, 27, 36),
    control = Color3.fromRGB(28, 37, 48),
    controlSelected = Color3.fromRGB(31, 76, 70),
    accent = Color3.fromRGB(72, 214, 180),
    text = Color3.fromRGB(239, 244, 248),
    muted = Color3.fromRGB(139, 157, 173),
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

local function numericBox(parent: Instance, y: number, placeholder: string): TextBox
    local box = Instance.new("TextBox")
    box.BackgroundColor3 = COLORS.control
    box.BorderSizePixel = 0
    box.Position = UDim2.fromOffset(0, y)
    box.Size = UDim2.new(1, 0, 0, 34)
    box.ClearTextOnFocus = false
    box.Font = Enum.Font.GothamSemibold
    box.TextColor3 = COLORS.text
    box.PlaceholderColor3 = COLORS.muted
    box.PlaceholderText = placeholder
    box.TextSize = 12
    box.TextXAlignment = Enum.TextXAlignment.Left
    box.Parent = parent
    corner(box, 7)
    stroke(box, 0.35)
    local padding = Instance.new("UIPadding")
    padding.PaddingLeft = UDim.new(0, 11)
    padding.PaddingRight = UDim.new(0, 11)
    padding.Parent = box
    return box
end

local function createDropdown(gui: ScreenGui, parent: Instance, y: number, labelText: string)
    sectionCaption(parent, labelText, y)

    local control = button(parent, "—")
    control.Position = UDim2.fromOffset(0, y + 18)
    control.Size = UDim2.new(1, 0, 0, 34)
    control.TextSize = 11
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

    local state = { value = "", options = {}, onChanged = nil, buttons = {} }

    local function renderControl()
        local found = "—"
        for _, option in ipairs(state.options) do
            if option.value == state.value then
                found = option.label
                break
            end
        end
        control.Text = found .. (popup.Visible and "   ▴" or "   ▾")
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
        renderOptions()
        if fire and state.onChanged then
            state.onChanged(value)
        end
    end

    local function refresh(options, preferredValue: string?)
        state.options = options or {}
        state.buttons = {}
        for _, child in ipairs(popup:GetChildren()) do
            if child:IsA("TextButton") then
                child:Destroy()
            end
        end
        for index, option in ipairs(state.options) do
            local optionButton = button(popup, option.label)
            optionButton.Size = UDim2.new(1, 0, 0, 30)
            optionButton.LayoutOrder = index
            optionButton.ZIndex = 51
            optionButton.TextSize = 10
            optionButton.TextXAlignment = Enum.TextXAlignment.Left
            optionButton.TextTruncate = Enum.TextTruncate.AtEnd
            local optionPadding = Instance.new("UIPadding")
            optionPadding.PaddingLeft = UDim.new(0, 9)
            optionPadding.PaddingRight = UDim.new(0, 9)
            optionPadding.Parent = optionButton
            state.buttons[index] = optionButton
            optionButton.Activated:Connect(function()
                setValue(option.value, true)
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
        if #state.options == 0 then
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
    }
end

local function formatNumber(value: number): string
    local rendered = string.format("%.2f", value)
    rendered = rendered:gsub("0+$", ""):gsub("%.$", "")
    return rendered
end

local function travelTime(distance: number, speed: number): string
    if speed <= 0.0001 then
        return "∞"
    end
    return formatNumber(distance / speed) .. " s"
end

local function createGui()
    local playerGui = player:WaitForChild("PlayerGui")
    local previous = playerGui:FindFirstChild("Game1MovementDebugGui")
    if previous then previous:Destroy() end

    local gui = Instance.new("ScreenGui")
    gui.Name = "Game1MovementDebugGui"
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

    local header = textLabel(panel, "MOVEMENT DEBUG", 11, true)
    header.Position = UDim2.fromOffset(16, 6)
    header.Size = UDim2.fromOffset(210, 16)
    local subtitle = textLabel(panel, "game speed + world distance + animation", 9, false)
    subtitle.TextColor3 = COLORS.muted
    subtitle.Position = UDim2.fromOffset(16, 22)
    subtitle.Size = UDim2.fromOffset(230, 14)

    local collapse = button(panel, "MV")
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

    local unit = createDropdown(gui, body, 0, "Runtime unit")

    sectionCaption(body, "Run speed · game parameter", 61)
    local runSpeed = numericBox(body, 79, "50")

    local walkHint = textLabel(body, "Walk is always RunSpeed / 2", 9, false)
    walkHint.TextColor3 = COLORS.muted
    walkHint.Position = UDim2.fromOffset(1, 115)
    walkHint.Size = UDim2.new(1, -2, 0, 16)

    sectionCaption(body, "World distance / 1 second · studs", 139)
    local distance = numericBox(body, 157, "5")

    sectionCaption(body, "Animation playback · runtime override %", 201)
    local animationSpeed = numericBox(body, 219, "100")

    local timing = Instance.new("Frame")
    timing.BackgroundColor3 = COLORS.panelRaised
    timing.BorderSizePixel = 0
    timing.Position = UDim2.fromOffset(0, 263)
    timing.Size = UDim2.new(1, 0, 0, 78)
    timing.Parent = body
    corner(timing, 7)
    stroke(timing, 0.45)

    local runTiming = textLabel(timing, "Run —", 10, true)
    runTiming.Position = UDim2.fromOffset(10, 4)
    runTiming.Size = UDim2.new(1, -20, 0, 20)
    local walkTiming = textLabel(timing, "Walk —", 10, false)
    walkTiming.TextColor3 = COLORS.muted
    walkTiming.Position = UDim2.fromOffset(10, 25)
    walkTiming.Size = UDim2.new(1, -20, 0, 20)
    local measuredTiming = textLabel(timing, "MEASURED · last 1.0 s —", 9, false)
    measuredTiming.TextColor3 = COLORS.accent
    measuredTiming.Position = UDim2.fromOffset(10, 49)
    measuredTiming.Size = UDim2.new(1, -20, 0, 18)

    local monsterMode = button(body, "MONSTER BASE: WALK")
    monsterMode.Position = UDim2.fromOffset(0, 353)
    monsterMode.Size = UDim2.new(1, 0, 0, 30)
    monsterMode.Font = Enum.Font.GothamSemibold
    monsterMode.TextSize = 10

    local live = textLabel(body, "Waiting for runtime units…", 9, false)
    live.TextColor3 = COLORS.muted
    live.TextTruncate = Enum.TextTruncate.AtEnd
    live.Position = UDim2.fromOffset(1, 392)
    live.Size = UDim2.new(1, -2, 0, 16)

    local collapsed = true
    local function setCollapsed(value: boolean)
        collapsed = value
        unit.close()
        body.Visible = not collapsed
        header.Visible = not collapsed
        subtitle.Visible = not collapsed
        accent.Visible = not collapsed
        if collapsed then
            collapse.Text = "MV"
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

    return gui, unit, runSpeed, distance, animationSpeed, runTiming, walkTiming, measuredTiming, walkHint, monsterMode, live
end

function MovementDebugController.Start()
    if started or not RunService:IsStudio() then
        return
    end
    started = true

    task.spawn(function()
        local remotes = ReplicatedStorage:WaitForChild("Game1Remotes", 10)
        if not remotes then
            warn("[game1][movement-debug] Game1Remotes is missing")
            return
        end
        local catalogRemote = remotes:WaitForChild("GetMovementDebugCatalog", 10)
        local applyRemote = remotes:WaitForChild("ApplyMovementDebug", 10)
        local monsterModeRemote = remotes:WaitForChild("SetMovementDebugMonsterMode", 10)
        if not catalogRemote or not applyRemote or not monsterModeRemote then
            warn("[game1][movement-debug] remotes are missing")
            return
        end

        local _, unitDropdown, runSpeedBox, distanceBox, animationSpeedBox, runTiming, walkTiming, measuredTiming, walkHint, monsterModeButton, live = createGui()
        local unitRows = {}
        local unitById = {}
        local unitCatalogSignature = ""
        local monsterMode = "Walk"
        local suppressSpeedText = false
        local speedTextRevision = 0
        local draftSpeed = 0
        local pendingSpeedById = {}
        local runSpeedUnitsPerStud = DEFAULT_RUN_SPEED_UNITS_PER_STUD
        local suppressAnimationText = false
        local animationTextRevision = 0
        local draftAnimationPercent = 100
        local pendingAnimationById = {}

        local trackedModel: Model? = nil
        local lastTrackedPosition: Vector3? = nil
        local cumulativeDistance = 0
        local distanceSamples = {}
        local measuredDistance = 0
        local measuredAge = 0

        local function selectedRow()
            return unitById[unitDropdown.getValue()]
        end

        local function modelPosition(model: Model?): Vector3?
            if not model or not model.Parent then
                return nil
            end
            local navigationRoot = model:FindFirstChild("NavigationRoot")
            if navigationRoot and navigationRoot:IsA("BasePart") then
                return navigationRoot.Position
            end
            local humanoidRoot = model:FindFirstChild("HumanoidRootPart")
            if humanoidRoot and humanoidRoot:IsA("BasePart") then
                return humanoidRoot.Position
            end
            if model.PrimaryPart then
                return model.PrimaryPart.Position
            end
            local anyPart = model:FindFirstChildWhichIsA("BasePart", true)
            return anyPart and anyPart.Position or nil
        end

        local function resetMeasurement()
            local row = selectedRow()
            trackedModel = row and row.model or nil
            lastTrackedPosition = modelPosition(trackedModel)
            cumulativeDistance = 0
            distanceSamples = {}
            measuredDistance = 0
            measuredAge = 0
            measuredTiming.Text = "MEASURED · last 1.0 s —"
        end

        local function renderMeasurement()
            if not trackedModel or not trackedModel.Parent or measuredAge <= 0 then
                measuredTiming.Text = "MEASURED · last 1.0 s —"
                return
            end
            measuredTiming.Text = string.format(
                "MEASURED · %.2f studs / %.2f s  ≈  %.2f studs/s",
                measuredDistance,
                math.min(1, measuredAge),
                measuredDistance / math.max(0.001, math.min(1, measuredAge))
            )
        end

        local function syncSpeedBoxes(runSpeedValue: number, source: TextBox?)
            local runRendered = formatNumber(runSpeedValue)
            local distanceRendered = formatNumber(runSpeedValue / math.max(0.001, runSpeedUnitsPerStud))
            suppressSpeedText = true
            if source ~= runSpeedBox then
                runSpeedBox.Text = runRendered
            end
            if source ~= distanceBox then
                distanceBox.Text = distanceRendered
            end
            suppressSpeedText = false
        end

        local function syncAnimationBox(value: number)
            suppressAnimationText = true
            animationSpeedBox.Text = formatNumber(value)
            suppressAnimationText = false
        end

        local function renderTiming()
            local runGame = math.max(0, draftSpeed)
            local walkGame = runGame * 0.5
            local runWorld = runGame / math.max(0.001, runSpeedUnitsPerStud)
            local walkWorld = walkGame / math.max(0.001, runSpeedUnitsPerStud)
            runTiming.Text = string.format("RUN  game %s  ·  world %s studs/s", formatNumber(runGame), formatNumber(runWorld))
            walkTiming.Text = string.format("WALK  game %s  ·  world %s studs/s", formatNumber(walkGame), formatNumber(walkWorld))
            walkHint.Text = string.format("Walk = RunSpeed / 2  ·  %s game speed = 1 stud/s", formatNumber(runSpeedUnitsPerStud))
            renderMeasurement()
        end

        local function setMonsterModeVisual(mode: string)
            monsterMode = string.lower(mode) == "run" and "Run" or "Walk"
            monsterModeButton.Text = "MONSTER BASE: " .. string.upper(monsterMode)
            monsterModeButton.BackgroundColor3 = monsterMode == "Run" and COLORS.controlSelected or COLORS.control
            monsterModeButton.TextColor3 = monsterMode == "Run" and COLORS.accent or COLORS.text
        end

        local function renderSelected(forceText: boolean?)
            local row = selectedRow()
            if not row then
                live.Text = "No movable runtime unit is available"
                runSpeedBox.TextEditable = false
                distanceBox.TextEditable = false
                animationSpeedBox.TextEditable = false
                runSpeedBox.BackgroundColor3 = COLORS.disabled
                distanceBox.BackgroundColor3 = COLORS.disabled
                animationSpeedBox.BackgroundColor3 = COLORS.disabled
                draftSpeed = 0
                draftAnimationPercent = 100
                syncSpeedBoxes(0, nil)
                syncAnimationBox(100)
                resetMeasurement()
                renderTiming()
                return
            end

            runSpeedBox.TextEditable = true
            distanceBox.TextEditable = true
            animationSpeedBox.TextEditable = true
            runSpeedBox.BackgroundColor3 = COLORS.control
            distanceBox.BackgroundColor3 = COLORS.control
            animationSpeedBox.BackgroundColor3 = COLORS.control

            local selectedId = unitDropdown.getValue()
            local focused = UserInputService:GetFocusedTextBox()
            local pending = pendingSpeedById[selectedId]
            if pending ~= nil then
                draftSpeed = pending
            elseif forceText or (focused ~= runSpeedBox and focused ~= distanceBox) then
                draftSpeed = math.max(0, tonumber(row.runSpeed) or 0)
                syncSpeedBoxes(draftSpeed, nil)
            end

            local pendingAnimation = pendingAnimationById[selectedId]
            if pendingAnimation ~= nil then
                draftAnimationPercent = pendingAnimation
            elseif forceText or focused ~= animationSpeedBox then
                draftAnimationPercent = math.max(1, tonumber(row.animationSpeedPercent) or 100)
                syncAnimationBox(draftAnimationPercent)
            end

            live.TextColor3 = COLORS.muted
            local animationLabel = tostring(row.animationSlot or "")
            if animationLabel == "" then animationLabel = "—" end
            live.Text = string.format("LIVE · %s · %s · %s · anim %s @ %s%%", string.upper(tostring(row.kind or "unit")), tostring(row.lifeState or "Alive"), tostring(row.movementState or "idle"), animationLabel, formatNumber(draftAnimationPercent))
            renderTiming()
        end

        local function rebuildCatalog(catalog: any, preserveSelection: boolean)
            unitRows = catalog.units or {}
            unitById = {}
            local options = {}
            local signatureParts = {}
            for _, row in ipairs(unitRows) do
                local id = tostring(row.id or "")
                local label = tostring(row.label or id)
                unitById[id] = row
                table.insert(options, { value = id, label = label })
                table.insert(signatureParts, id .. "=" .. label)
            end
            local signature = table.concat(signatureParts, "|")
            local previousSelection = unitDropdown.getValue()
            local preferred = preserveSelection and previousSelection or tostring(catalog.selectedId or "")
            if signature ~= unitCatalogSignature then
                unitCatalogSignature = signature
                unitDropdown.refresh(options, preferred)
            elseif preferred ~= "" and unitById[preferred] and unitDropdown.getValue() ~= preferred then
                unitDropdown.setValue(preferred, false)
            end
            runSpeedUnitsPerStud = math.max(0.001, tonumber(catalog.runSpeedUnitsPerStud) or DEFAULT_RUN_SPEED_UNITS_PER_STUD)
            setMonsterModeVisual(tostring(catalog.monsterMode or monsterMode))
            if previousSelection ~= unitDropdown.getValue() then
                resetMeasurement()
            end
            renderSelected(false)
        end

        local function fetchCatalog(preserveSelection: boolean)
            local ok, catalog = pcall(function()
                return catalogRemote:InvokeServer()
            end)
            if ok and type(catalog) == "table" then
                rebuildCatalog(catalog, preserveSelection)
            else
                live.Text = "Movement debug catalog unavailable"
                live.TextColor3 = COLORS.error
            end
        end

        local function applyRunSpeed(value: number)
            local targetId = unitDropdown.getValue()
            if targetId == "" then
                return
            end
            value = math.clamp(value, 0, 500)
            draftSpeed = value
            pendingSpeedById[targetId] = value
            syncSpeedBoxes(value, nil)
            renderTiming()

            task.spawn(function()
                local ok, result = pcall(function()
                    return applyRemote:InvokeServer(targetId, { runSpeed = value })
                end)
                if pendingSpeedById[targetId] == value then
                    pendingSpeedById[targetId] = nil
                end
                if not ok or type(result) ~= "table" or result.ok ~= true then
                    live.Text = "RunSpeed update failed"
                    live.TextColor3 = COLORS.error
                    return
                end
                live.TextColor3 = COLORS.muted
                local row = result.unit
                if type(row) == "table" then
                    unitById[targetId] = row
                    if targetId == unitDropdown.getValue() then
                        draftSpeed = math.max(0, tonumber(row.runSpeed) or value)
                        syncSpeedBoxes(draftSpeed, nil)
                    end
                end
                renderSelected(false)
            end)
        end

        local function stageSpeedText(source: TextBox)
            if suppressSpeedText then
                return
            end
            local typed = tonumber(source.Text)
            if typed == nil or typed < 0 then
                return
            end
            local value = if source == distanceBox then typed * runSpeedUnitsPerStud else typed
            if value > 500 then
                return
            end
            draftSpeed = value
            syncSpeedBoxes(value, source)
            renderTiming()
            speedTextRevision += 1
            local revision = speedTextRevision
            task.delay(0.08, function()
                if revision == speedTextRevision and math.abs(draftSpeed - value) <= 0.0001 then
                    applyRunSpeed(value)
                end
            end)
        end

        local function commitSpeedBox(source: TextBox)
            local typed = tonumber(source.Text)
            local value = if source == distanceBox
                then (typed or (draftSpeed / runSpeedUnitsPerStud)) * runSpeedUnitsPerStud
                else (typed or draftSpeed)
            value = math.clamp(value, 0, 500)
            speedTextRevision += 1
            draftSpeed = value
            syncSpeedBoxes(value, nil)
            applyRunSpeed(value)
        end

        local function applyAnimationSpeed(value: number)
            local targetId = unitDropdown.getValue()
            if targetId == "" then
                return
            end
            value = math.clamp(value, 1, 400)
            draftAnimationPercent = value
            pendingAnimationById[targetId] = value
            syncAnimationBox(value)
            task.spawn(function()
                local ok, result = pcall(function()
                    return applyRemote:InvokeServer(targetId, { animationSpeedPercent = value })
                end)
                if pendingAnimationById[targetId] == value then
                    pendingAnimationById[targetId] = nil
                end
                if not ok or type(result) ~= "table" or result.ok ~= true then
                    live.Text = "Animation speed update failed"
                    live.TextColor3 = COLORS.error
                    return
                end
                local row = result.unit
                if type(row) == "table" then
                    unitById[targetId] = row
                    if targetId == unitDropdown.getValue() then
                        draftAnimationPercent = math.max(1, tonumber(row.animationSpeedPercent) or value)
                        syncAnimationBox(draftAnimationPercent)
                    end
                end
                renderSelected(false)
            end)
        end

        local function stageAnimationText()
            if suppressAnimationText then
                return
            end
            local value = tonumber(animationSpeedBox.Text)
            if value == nil or value < 1 or value > 400 then
                return
            end
            draftAnimationPercent = value
            animationTextRevision += 1
            local revision = animationTextRevision
            task.delay(0.08, function()
                if revision == animationTextRevision and math.abs(draftAnimationPercent - value) <= 0.0001 then
                    applyAnimationSpeed(value)
                end
            end)
        end

        local function commitAnimationBox()
            local value = math.clamp(tonumber(animationSpeedBox.Text) or draftAnimationPercent, 1, 400)
            animationTextRevision += 1
            draftAnimationPercent = value
            syncAnimationBox(value)
            applyAnimationSpeed(value)
        end

        unitDropdown.setOnChanged(function()
            resetMeasurement()
            renderSelected(true)
        end)

        runSpeedBox:GetPropertyChangedSignal("Text"):Connect(function()
            stageSpeedText(runSpeedBox)
        end)
        distanceBox:GetPropertyChangedSignal("Text"):Connect(function()
            stageSpeedText(distanceBox)
        end)
        runSpeedBox.FocusLost:Connect(function()
            commitSpeedBox(runSpeedBox)
        end)
        distanceBox.FocusLost:Connect(function()
            commitSpeedBox(distanceBox)
        end)
        animationSpeedBox:GetPropertyChangedSignal("Text"):Connect(stageAnimationText)
        animationSpeedBox.FocusLost:Connect(commitAnimationBox)

        monsterModeButton.Activated:Connect(function()
            local requested = monsterMode == "Run" and "Walk" or "Run"
            task.spawn(function()
                local ok, result = pcall(function()
                    return monsterModeRemote:InvokeServer(requested)
                end)
                if ok and type(result) == "table" and result.ok == true then
                    setMonsterModeVisual(tostring(result.monsterMode or requested))
                    fetchCatalog(true)
                else
                    live.Text = "Monster locomotion update failed"
                    live.TextColor3 = COLORS.error
                end
            end)
        end)

        RunService.Heartbeat:Connect(function()
            local row = selectedRow()
            local model = row and row.model or nil
            if model ~= trackedModel then
                resetMeasurement()
                return
            end
            local position = modelPosition(model)
            if not position then
                lastTrackedPosition = nil
                measuredDistance = 0
                measuredAge = 0
                renderMeasurement()
                return
            end

            local flat = Vector3.new(position.X, 0, position.Z)
            local previous = lastTrackedPosition and Vector3.new(lastTrackedPosition.X, 0, lastTrackedPosition.Z) or nil
            lastTrackedPosition = position
            local now = os.clock()
            if previous then
                local delta = (flat - previous).Magnitude
                local expectedWorldSpeed = draftSpeed / math.max(0.001, runSpeedUnitsPerStud)
                local teleportGuard = math.max(8, math.max(1, expectedWorldSpeed) * 0.75)
                if delta <= teleportGuard then
                    cumulativeDistance += delta
                end
            end
            table.insert(distanceSamples, { time = now, distance = cumulativeDistance })
            local cutoff = now - 1
            while #distanceSamples > 2 and distanceSamples[2].time <= cutoff do
                table.remove(distanceSamples, 1)
            end
            local oldest = distanceSamples[1]
            measuredAge = oldest and math.min(1, math.max(0, now - oldest.time)) or 0
            measuredDistance = oldest and math.max(0, cumulativeDistance - oldest.distance) or 0
            renderMeasurement()
        end)

        fetchCatalog(false)
        while true do
            task.wait(CATALOG_POLL_SECONDS)
            fetchCatalog(true)
        end
    end)
end

return MovementDebugController
