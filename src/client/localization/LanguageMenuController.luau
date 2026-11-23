--!strict
-- One first-run language picker and an always-available change-language control.
-- UI selection is local and immediate; server persists a validated preference.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local State = require(script.Parent:WaitForChild("LanguageState"))
local Catalog = require(ReplicatedStorage:WaitForChild("Game1Shared")
    :WaitForChild("localization"):WaitForChild("GameTextCatalog"))
local Controller = {}
local started = false

local ORDER = {"ru-ru", "en-us", "de-de", "zh-cn", "it-it", "es-es",
    "fr-fr", "pt-br", "ja-jp", "ko-kr"}

local function corner(parent: Instance, radius: number)
    local value = Instance.new("UICorner")
    value.CornerRadius = UDim.new(0, radius)
    value.Parent = parent
end

local function label(parent: Instance, name: string, text: string, size: number, height: number): TextLabel
    local result = Instance.new("TextLabel")
    result.Name = name
    result.BackgroundTransparency = 1
    result.Font = Enum.Font.Gotham
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
    launcher.Size = UDim2.fromOffset(112, 34)
    launcher.Font = Enum.Font.GothamSemibold
    launcher.TextSize = 13
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
    list.Position = UDim2.fromOffset(13, 89)
    list.Size = UDim2.new(1, -26, 1, -157)
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

    local buttons: {[string]: TextButton} = {}
    for order, locale in ipairs(ORDER) do
        local button = Instance.new("TextButton")
        button.Name = locale
        button.LayoutOrder = order
        button.Size = UDim2.fromOffset(150, 44)
        button.Font = Enum.Font.GothamMedium
        button.TextSize = 15
        button.TextColor3 = Color3.fromRGB(238, 245, 249)
        button.Text = Catalog.locales[locale]
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
        launcher.Text = "🌐  " .. State.Translate("language.button")
        for locale, button in pairs(buttons) do
            button.BackgroundColor3 = if locale == chosen
                then Color3.fromRGB(48, 105, 91) else Color3.fromRGB(41, 57, 73)
        end
    end
    local function open()
        previous = State.Current()
        chosen = previous
        status.Text = ""
        status:SetAttribute("Game1SaveFailed", false)
        close.Visible = player:GetAttribute("Game1LanguageChoice") ~= nil
        shade.Visible = true
        paint()
    end
    for locale, button in pairs(buttons) do
        button.Activated:Connect(function()
            if pending then return end
            hasChosen = true
            chosen = locale
            State.SetLocale(locale)
            status.Text = ""
            status:SetAttribute("Game1SaveFailed", false)
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
        paint()
        status.Text = State.Translate("language.loading")
        task.spawn(function()
            local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes")
            local remote = remotes and remotes:FindFirstChild("SetPlayerLanguage")
            local ok, response = false, nil
            if remote and remote:IsA("RemoteFunction") then
                ok, response = pcall(function() return remote:InvokeServer(chosen) end)
            end
            pending = false
            if ok and typeof(response) == "table" and response.ok == true then
                status.Text = State.Translate("language.saved")
                shade.Visible = false
            else
                -- Do not keep the player captive: a second click continues
                -- with a session-only language if DataStore has no API access.
                if status:GetAttribute("Game1SaveFailed") == true then
                    shade.Visible = false
                else
                    status:SetAttribute("Game1SaveFailed", true)
                    status.Text = State.Translate("language.unsaved")
                end
            end
        end)
    end)
    State.Changed:Connect(paint)
    paint()
    gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(function()
        panel.Size = UDim2.fromOffset(math.min(460, math.max(270, gui.AbsoluteSize.X - 24)),
            math.min(456, math.max(225, gui.AbsoluteSize.Y - 24)))
    end)
    panel.Size = UDim2.fromOffset(math.min(460, math.max(270, gui.AbsoluteSize.X - 24)),
        math.min(456, math.max(225, gui.AbsoluteSize.Y - 24)))

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
