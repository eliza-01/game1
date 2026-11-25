--!strict
-- One first-run language picker and an always-available change-language control.
-- UI selection is local and immediate; server persists a validated preference.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local State = require(script.Parent:WaitForChild("LanguageState"))
local FullScreenLayer = require(script.Parent.Parent:WaitForChild("FullScreenLayer"))
local Catalog = require(ReplicatedStorage:WaitForChild("Game1Shared")
    :WaitForChild("localization"):WaitForChild("GameTextCatalog"))
local Controller = {}
local started = false

local ORDER = {"ru-ru", "en-us", "de-de", "zh-cn", "it-it", "es-es",
    "fr-fr", "pt-br", "ja-jp", "ko-kr"}
local FLAGS = table.freeze({["ru-ru"] = "🇷🇺", ["en-us"] = "🇺🇸", ["de-de"] = "🇩🇪",
    ["zh-cn"] = "🇨🇳", ["it-it"] = "🇮🇹", ["es-es"] = "🇪🇸", ["fr-fr"] = "🇫🇷",
    ["pt-br"] = "🇧🇷", ["ja-jp"] = "🇯🇵", ["ko-kr"] = "🇰🇷"})

local function corner(parent: Instance, radius: number)
    local value = Instance.new("UICorner")
    value.CornerRadius = UDim.new(0, radius)
    value.Parent = parent
end

local function label(parent: Instance, name: string, text: string, size: number, height: number): TextLabel
    local result = Instance.new("TextLabel")
    result.Name = name
    result.BackgroundTransparency = 1
    result.Font = Enum.Font.GothamBold
    result.Text = text
    result.TextSize = size
    result.TextColor3 = Color3.fromRGB(235, 241, 248)
    result.TextWrapped = true
    result.Size = UDim2.new(1, 0, 0, height)
    result.Parent = parent
    return result
end

function Controller.Start()
    if started then return end
    started = true
    local player = Players.LocalPlayer
    local gui = Instance.new("ScreenGui")
    gui.Name = "Game1LanguageMenu"
    gui.DisplayOrder = 301
    gui.ResetOnSpawn = false
    gui.IgnoreGuiInset = false
    gui.Parent = player:WaitForChild("PlayerGui")

    local launcher = Instance.new("TextButton")
    launcher.Name = "ChangeLanguage"
    launcher.AnchorPoint = Vector2.new(1, 0)
    launcher.Position = UDim2.new(1, -12, 0, 8)
    launcher.Size = UDim2.fromOffset(44, 44)
    launcher.Font = Enum.Font.GothamBold
    launcher.TextSize = 27
    launcher.BackgroundColor3 = Color3.fromRGB(25, 40, 52)
    launcher.TextColor3 = Color3.fromRGB(247, 249, 250)
    launcher.Parent = gui
    corner(launcher, 8)

    local shade = Instance.new("Frame")
    shade.Name = "ModalBackdrop"
    shade.Size = UDim2.fromScale(1, 1)
    shade.BackgroundColor3 = Color3.fromRGB(5, 10, 17)
    shade.BackgroundTransparency = 0.20
    shade.Visible = false
    shade.Active = true
    shade.Parent = gui
    -- Keep picker/launcher inside Core UI safe insets, but shade the entire viewport.
    local backdrop = Instance.new("Frame")
    backdrop.Name = "FullViewportBackdrop"
    backdrop.Size = UDim2.fromScale(1, 1)
    backdrop.BackgroundColor3 = shade.BackgroundColor3
    backdrop.BackgroundTransparency = shade.BackgroundTransparency
    backdrop.BorderSizePixel = 0
    backdrop.Active = true
    backdrop.Visible = false
    backdrop.Parent = FullScreenLayer.Create(gui, "Game1LanguageBackdrop", 300)
    shade.BackgroundTransparency = 1
    shade:GetPropertyChangedSignal("Visible"):Connect(function() backdrop.Visible = shade.Visible end)

    local panel = Instance.new("Frame")
    panel.Name = "LanguagePicker"
    panel.AnchorPoint = Vector2.new(0.5, 0.5)
    panel.Position = UDim2.fromScale(0.5, 0.5)
    panel.BackgroundColor3 = Color3.fromRGB(27, 37, 49)
    panel.BorderSizePixel = 0
    panel.Parent = shade
    corner(panel, 14)
    local stroke = Instance.new("UIStroke")
    stroke.Color = Color3.fromRGB(84, 113, 132)
    stroke.Parent = panel

    local title = label(panel, "Heading", "", 22, 34)
    title.Position = UDim2.fromOffset(12, 14)
    title.Size = UDim2.new(1, -24, 0, 34)
    title.Font = Enum.Font.GothamBold

    local subtitle = label(panel, "Subtitle", "", 13, 30)
    subtitle.Position = UDim2.fromOffset(12, 49)
    subtitle.Size = UDim2.new(1, -24, 0, 30)
    subtitle.TextColor3 = Color3.fromRGB(182, 200, 211)

    local list = Instance.new("ScrollingFrame")
    list.Name = "AvailableLocales"
    list.Position = UDim2.fromOffset(13, 145)
    list.Size = UDim2.new(1, -26, 1, -213)
    list.BackgroundTransparency = 1
    list.BorderSizePixel = 0
    list.ScrollBarThickness = 3
    list.ScrollingDirection = Enum.ScrollingDirection.Y
    list.AutomaticCanvasSize = Enum.AutomaticSize.Y
    list.CanvasSize = UDim2.fromScale(0, 0)
    list.Parent = panel
    local grid = Instance.new("UIGridLayout")
    grid.SortOrder = Enum.SortOrder.LayoutOrder
    grid.FillDirectionMaxCells = 2
    grid.CellSize = UDim2.new(0.5, -5, 0, 44)
    grid.CellPadding = UDim2.fromOffset(8, 8)
    grid.Parent = list

    local settingsTab = "language"
    local settingsTabs: {[string]: TextButton} = {}
    for order, tab in ipairs({"language", "character", "graphics", "sound"}) do
        local item = Instance.new("TextButton")
        item.Name = "Settings_" .. tab
        item.Position = UDim2.new((order - 1) / 4, 9, 0, 93)
        item.Size = UDim2.new(0.25, -17, 0, 40)
        item.Font = Enum.Font.GothamBold
        item.TextSize = 12
        item.TextColor3 = Color3.fromRGB(240, 238, 222)
        item.BackgroundColor3 = Color3.fromRGB(44, 59, 71)
        item.ZIndex = 2
        item.Parent = panel
        corner(item, 7)
        settingsTabs[tab] = item
    end
    local details = label(panel, "SettingsDescription", "", 16, 90)
    details.Position = UDim2.fromOffset(18, 174)
    details.Size = UDim2.new(1, -36, 0, 90)
    details.TextColor3 = Color3.fromRGB(211, 222, 227)
    details.Visible = false
    local settingsAction = Instance.new("TextButton")
    settingsAction.Name = "SettingsAction"
    settingsAction.Position = UDim2.fromOffset(18, 285)
    settingsAction.Size = UDim2.new(1, -36, 0, 45)
    settingsAction.BackgroundColor3 = Color3.fromRGB(70, 114, 100)
    settingsAction.Font = Enum.Font.GothamBold
    settingsAction.TextSize = 15
    settingsAction.TextColor3 = Color3.fromRGB(255, 255, 255)
    settingsAction.Visible = false
    settingsAction.Parent = panel
    corner(settingsAction, 9)
    local buttons: {[string]: TextButton} = {}
    for order, locale in ipairs(ORDER) do
        local button = Instance.new("TextButton")
        button.Name = locale
        button.LayoutOrder = order
        button.Size = UDim2.fromOffset(150, 44)
        button.Font = Enum.Font.GothamBold
        button.TextSize = 15
        button.TextColor3 = Color3.fromRGB(238, 245, 249)
        button.Text = FLAGS[locale] .. "  " .. Catalog.locales[locale]
        button.TextTruncate = Enum.TextTruncate.AtEnd
        button.Parent = list
        corner(button, 8)
        buttons[locale] = button
    end

    local status = label(panel, "SaveStatus", "", 12, 20)
    status.Position = UDim2.new(0, 14, 1, -65)
    status.Size = UDim2.new(1, -28, 0, 18)
    status.TextColor3 = Color3.fromRGB(255, 193, 135)
    local confirm = Instance.new("TextButton")
    confirm.Name = "ConfirmLanguage"
    confirm.AnchorPoint = Vector2.new(0.5, 1)
    confirm.Position = UDim2.new(0.5, 0, 1, -12)
    confirm.Size = UDim2.new(1, -28, 0, 39)
    confirm.BackgroundColor3 = Color3.fromRGB(46, 129, 110)
    confirm.TextColor3 = Color3.fromRGB(255, 255, 255)
    confirm.Font = Enum.Font.GothamBold
    confirm.TextSize = 16
    confirm.Parent = panel
    corner(confirm, 9)

    local chosen = State.Current()
    local previous = chosen
    local pending = false
    local hasChosen = false
    local close = Instance.new("TextButton")
    close.Name = "CancelLanguage"
    close.Position = UDim2.new(1, -43, 0, 13)
    close.Size = UDim2.fromOffset(28, 28)
    close.Text = "×"
    close.TextSize = 18
    close.Font = Enum.Font.GothamBold
    close.TextColor3 = Color3.fromRGB(238, 245, 249)
    close.BackgroundColor3 = Color3.fromRGB(51, 65, 80)
    close.Parent = panel
    corner(close, 7)
    local function paint()
        title.Text = State.Translate("language.title")
        subtitle.Text = State.Translate("language.subtitle")
        confirm.Text = State.Translate("language.confirm")
        launcher.Text = "⚙"
        for locale, button in pairs(buttons) do
            button.BackgroundColor3 = if locale == chosen
                then Color3.fromRGB(48, 105, 91) else Color3.fromRGB(41, 57, 73)
        end
        local current = settingsTab == "language"
        list.Visible = current
        confirm.Visible = current
        subtitle.Visible = current and panel.AbsoluteSize.Y >= 360
        details.Visible = not current
        settingsAction.Visible = settingsTab == "character"
        for tab, item in pairs(settingsTabs) do
            item.Text = State.Translate("settings." .. tab)
            item.BackgroundColor3 = if tab == settingsTab
                then Color3.fromRGB(77, 107, 95) else Color3.fromRGB(44, 59, 71)
        end
        if settingsTab == "character" then
            details.Text = State.Translate("settings.character_hint")
            settingsAction.Text = State.Translate("settings.change_character")
        elseif settingsTab == "graphics" or settingsTab == "sound" then
            details.Text = State.Translate("settings.coming_soon")
        end
    end
    local function open()
        previous = State.Current()
        chosen = previous
        settingsTab = "language"
        status.Text = ""
        close.Visible = hasChosen or player:GetAttribute("Game1LanguageChoice") ~= nil
        shade.Visible = true
        paint()
    end
    for tab, item in pairs(settingsTabs) do
        item.Activated:Connect(function()
            if pending then return end
            settingsTab = tab
            status.Text = ""
            paint()
        end)
    end
    settingsAction.Activated:Connect(function()
        if pending then return end
        pending = true
        status.Text = State.Translate("language.loading")
        task.spawn(function()
            local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes")
            local remote = remotes and remotes:FindFirstChild("CharacterCreationManage")
            local ok, response = false, nil
            if remote and remote:IsA("RemoteFunction") then
                ok, response = pcall(function() return remote:InvokeServer() end)
            end
            pending = false
            if ok and type(response) == "table" and response.ok == true then
                shade.Visible = false
            else
                status.Text = State.Translate("settings.change_unavailable")
            end
        end)
    end)
    for locale, button in pairs(buttons) do
        button.Activated:Connect(function()
            if pending then return end
            hasChosen = true
            chosen = locale
            State.SetLocale(locale)
            status.Text = ""
            paint()
        end)
    end
    launcher.Activated:Connect(function()
        if not pending and not shade.Visible then open() end
    end)
    close.Activated:Connect(function()
        if pending then return end
        State.SetLocale(previous)
        shade.Visible = false
    end)
    confirm.Activated:Connect(function()
        if pending then return end
        pending = true
        State.SetLocale(chosen)
        hasChosen = true
        shade.Visible = false
        task.spawn(function()
            local remotes = ReplicatedStorage:WaitForChild("Game1Remotes", 5)
            local remote = remotes and remotes:WaitForChild("SetPlayerLanguage", 5)
            local ok, response = false, nil
            if remote and remote:IsA("RemoteFunction") then
                ok, response = pcall(function() return remote:InvokeServer(chosen) end)
            end
            pending = false
            -- The locale is already active locally. Persistence is optional;
            -- never require a second Continue for a session-only preference.
            if not ok or typeof(response) ~= "table" or response.ok ~= true then
                warn("[game1][language] preference confirmation unavailable; using local session locale")
            elseif response.persisted == false then
                warn("[game1][language] preference applied for this session only")
            end
        end)
    end)
    State.Changed:Connect(paint)
    paint()
    local function resize()
        local width = math.max(1, math.min(460, gui.AbsoluteSize.X - 24))
        local height = math.max(1, math.min(456, gui.AbsoluteSize.Y - 24))
        local compact = height < 360
        panel.Size = UDim2.fromOffset(width, height)
        title.Position = UDim2.fromOffset(12, if compact then 3 else 14)
        title.TextSize = if compact then 17 else 22
        title.Size = UDim2.new(1, -62, 0, 34)
        close.Position = UDim2.new(1, -43, 0, if compact then 4 else 13)
        subtitle.Visible = not compact and settingsTab == "language"
        local tabsY = if compact then 38 else 93
        for _, item in pairs(settingsTabs) do
            item.Position = UDim2.new(item.Position.X.Scale, item.Position.X.Offset, 0, tabsY)
            item.Size = UDim2.new(0.25, -17, 0, if compact then 32 else 40)
            item.TextWrapped = true
            item.TextSize = if compact then 11 else 12
        end
        local top = tabsY + (if compact then 38 else 52)
        local footer = 68
        list.Position = UDim2.fromOffset(13, top)
        list.Size = UDim2.new(1, -26, 0, math.max(1, height - top - footer))
        local available = math.max(1, height - top - footer)
        details.Position = UDim2.fromOffset(18, top)
        details.Size = UDim2.new(1, -36, 0, if settingsTab == "character" then math.max(1, available - 38) else available)
        details.TextScaled = compact
        settingsAction.Position = UDim2.fromOffset(18, top + math.max(0, available - 34))
        settingsAction.Size = UDim2.new(1, -36, 0, 34)
        settingsAction.TextWrapped = true
        settingsAction.TextSize = if compact then 12 else 15
    end
    gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(resize)
    for _, item in pairs(settingsTabs) do item.Activated:Connect(function() task.defer(resize) end) end
    shade:GetPropertyChangedSignal("Visible"):Connect(resize)
    resize()

    task.spawn(function()
        -- Load persisted preference before deciding whether first-run modal
        -- is necessary. Never stall the rest of client boot for DataStore.
        local elapsed = 0
        while player:GetAttribute("Game1LanguageReady") ~= true and elapsed < 6 do
            elapsed += task.wait(0.1)
        end
        if hasChosen or not gui.Parent then return end
        local saved = player:GetAttribute("Game1LanguageChoice")
        if typeof(saved) == "string" and Catalog.locales[saved] then
            chosen = saved
            State.SetLocale(saved)
            paint()
        else
            open()
        end
    end)
end

return table.freeze(Controller)
