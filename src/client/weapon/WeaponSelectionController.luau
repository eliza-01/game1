--!strict
-- Small runtime Playtest inventory picker. Only server WeaponSelectionService
-- decides which registered weapons exist and performs equipment changes.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Config = require(Shared:WaitForChild("weapon"):WaitForChild("WeaponSelectionConfig"))
local GameOptions = require(Shared:WaitForChild("GameOptions"))
local PublishedDebugAccess = require(Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))

local Controller = {}
local started = false
local DARK = Color3.fromRGB(18, 22, 29)
local SURFACE = Color3.fromRGB(34, 41, 51)
local WHITE = Color3.fromRGB(240, 243, 246)
local MUTED = Color3.fromRGB(165, 179, 190)
local ACCENT = Color3.fromRGB(69, 205, 168)

local function rounded(object: GuiObject, pixels: number)
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, pixels)
    corner.Parent = object
end

local function makeButton(parent: Instance, text: string, height: number): TextButton
    local button = Instance.new("TextButton")
    button.AutoButtonColor = true
    button.BackgroundColor3 = SURFACE
    button.TextColor3 = WHITE
    button.Font = Enum.Font.GothamMedium
    button.TextSize = 14
    button.Text = text
    button.BorderSizePixel = 0
    button.Size = UDim2.new(1, 0, 0, height)
    button.Parent = parent
    rounded(button, 9)
    return button
end

function Controller.Start()
    -- The playtest weapon picker is a debug control, not the eventual game inventory.
    if started or not Config.Enabled then return end
    if not PublishedDebugAccess.ClientAllowed() then return end
    started = true
    task.spawn(function()
        local remotes = ReplicatedStorage:WaitForChild("Game1Remotes", 15)
        local getCatalog = remotes and remotes:WaitForChild("GetWeaponSelectionCatalog", 12)
        local selectRemote = remotes and remotes:WaitForChild("SelectWeapon", 12)
        if not getCatalog or not selectRemote then
            warn("[game1][weapon-menu] selection remotes not available")
            return
        end
        local player = Players.LocalPlayer
        local playerGui = player:WaitForChild("PlayerGui")
        local existing = playerGui:FindFirstChild("Game1WeaponSelectionGui")
        if existing then existing:Destroy() end
        local gui = Instance.new("ScreenGui")
        gui.Name = "Game1WeaponSelectionGui"
        gui.ResetOnSpawn = false
        gui.IgnoreGuiInset = false
        gui.DisplayOrder = 20
        gui.Parent = playerGui

        local launcher = makeButton(gui, "⚔  ОРУЖИЕ", 42)
        launcher.Name = "WeaponMenuToggle"
        launcher.AnchorPoint = Vector2.zero
        launcher.Position = UDim2.fromOffset(14, 58)
        launcher.Size = UDim2.fromOffset(132, 42)
        launcher.BackgroundColor3 = DARK
        launcher.BackgroundTransparency = 0.15

        local panel = Instance.new("Frame")
        panel.Name = "WeaponMenuPanel"
        panel.Position = UDim2.fromOffset(14, 108)
        panel.Size = UDim2.fromOffset(294, 365)
        panel.BackgroundColor3 = DARK
        panel.BackgroundTransparency = 0.07
        panel.BorderSizePixel = 0
        panel.Visible = false
        panel.Parent = gui
        rounded(panel, 13)

        local header = Instance.new("TextLabel")
        header.BackgroundTransparency = 1
        header.Position = UDim2.fromOffset(13, 8)
        header.Size = UDim2.new(1, -60, 0, 30)
        header.TextXAlignment = Enum.TextXAlignment.Left
        header.Font = Enum.Font.GothamBold
        header.TextSize = 17
        header.TextColor3 = WHITE
        header.Text = "Выбор оружия"
        header.Parent = panel
        local close = makeButton(panel, "×", 32)
        close.Name = "Close"
        close.Position = UDim2.new(1, -42, 0, 7)
        close.Size = UDim2.fromOffset(32, 32)

        local categories = Instance.new("ScrollingFrame")
        categories.Name = "Categories"
        categories.BackgroundTransparency = 1
        categories.ScrollBarThickness = 0
        categories.ScrollingDirection = Enum.ScrollingDirection.X
        categories.Position = UDim2.fromOffset(10, 46)
        categories.Size = UDim2.new(1, -20, 0, 36)
        categories.Parent = panel
        local categoryLayout = Instance.new("UIListLayout")
        categoryLayout.FillDirection = Enum.FillDirection.Horizontal
        categoryLayout.Padding = UDim.new(0, 6)
        categoryLayout.SortOrder = Enum.SortOrder.LayoutOrder
        categoryLayout.Parent = categories

        local list = Instance.new("ScrollingFrame")
        list.Name = "Weapons"
        list.BackgroundTransparency = 1
        list.BorderSizePixel = 0
        list.ScrollBarThickness = 4
        list.Position = UDim2.fromOffset(10, 88)
        list.Size = UDim2.new(1, -20, 1, -133)
        list.CanvasSize = UDim2.fromOffset(0, 0)
        list.Parent = panel
        local listLayout = Instance.new("UIListLayout")
        listLayout.SortOrder = Enum.SortOrder.LayoutOrder
        listLayout.Padding = UDim.new(0, 6)
        listLayout.Parent = list
        listLayout:GetPropertyChangedSignal("AbsoluteContentSize"):Connect(function()
            list.CanvasSize = UDim2.fromOffset(0, listLayout.AbsoluteContentSize.Y + 8)
        end)
        categoryLayout:GetPropertyChangedSignal("AbsoluteContentSize"):Connect(function()
            categories.CanvasSize = UDim2.fromOffset(categoryLayout.AbsoluteContentSize.X + 6, 0)
        end)

        local status = Instance.new("TextLabel")
        status.Name = "Status"
        status.TextColor3 = MUTED
        status.BackgroundTransparency = 1
        status.TextXAlignment = Enum.TextXAlignment.Left
        status.Font = Enum.Font.Gotham
        status.TextSize = 11
        status.Position = UDim2.fromOffset(13, 335)
        status.Size = UDim2.new(1, -26, 0, 24)
        status.TextTruncate = Enum.TextTruncate.AtEnd
        status.Parent = panel
        status.Text = ""

        local rows: {any} = {}
        local activeCategory = "all"
        local selectedSlug = ""
        local loading = false
        local renderRows: () -> ()
        local function clear(frame: Instance, except: Instance)
            for _, child in ipairs(frame:GetChildren()) do
                if child ~= except then child:Destroy() end
            end
        end
        local categoryLabels = {
            all = "Все", hands = "Руки", dagger = "Кинжалы", sword = "Мечи",
            bigsword = "Двуручные", bow = "Луки",
        }
        local function drawCategories()
            clear(categories, categoryLayout)
            local kinds = { "all" }
            local seen = { all = true }
            for _, row in ipairs(rows) do
                local kind = tostring(row.weaponType or "hands")
                if not seen[kind] then
                    table.insert(kinds, kind)
                    seen[kind] = true
                end
            end
            for index, kind in ipairs(kinds) do
                local button = makeButton(categories, categoryLabels[kind] or kind, 30)
                button.Size = UDim2.fromOffset(math.clamp(30 + #button.Text * 8, 70, 144), 30)
                button.BackgroundColor3 = if activeCategory == kind then Color3.fromRGB(31, 94, 81) else SURFACE
                button.TextSize = 12
                button.LayoutOrder = index
                button.Activated:Connect(function()
                    activeCategory = kind
                    drawCategories()
                    renderRows()
                end)
            end
            categories.CanvasSize = UDim2.fromOffset(categoryLayout.AbsoluteContentSize.X + 6, 0)
        end
        renderRows = function()
            clear(list, listLayout)
            local index = 0
            for _, row in ipairs(rows) do
                local kind = tostring(row.weaponType or "hands")
                if activeCategory ~= "all" and activeCategory ~= kind then continue end
                index += 1
                local slug = tostring(row.slug or "")
                local title = tostring(row.label or slug)
                local chosen = selectedSlug == slug
                local button = makeButton(list, (if chosen then "✓  " else "     ") .. title, 45)
                button.Name = if slug == "" then "Unarmed" else slug
                button.TextXAlignment = Enum.TextXAlignment.Left
                button.TextTruncate = Enum.TextTruncate.AtEnd
                button.TextSize = 13
                button.LayoutOrder = index
                button.BackgroundColor3 = if chosen then Color3.fromRGB(31, 94, 81) else SURFACE
                button.Activated:Connect(function()
                    if loading then return end
                    loading = true
                    status.Text = "Применяем…"
                    task.spawn(function()
                        local success, result = pcall(function() return selectRemote:InvokeServer(slug) end)
                        loading = false
                        if success and typeof(result) == "table" and result.ok == true then
                            selectedSlug = tostring(result.selectedWeaponSlug or "")
                            status.Text = "Оружие экипировано"
                            renderRows()
                        else
                            status.Text = if success and typeof(result) == "table"
                                then tostring(result.error or "Не удалось экипировать")
                                else "Нет ответа сервера"
                        end
                    end)
                end)
            end
            list.CanvasSize = UDim2.fromOffset(0, listLayout.AbsoluteContentSize.Y + 8)
        end
        local function refresh()
            if loading then return end
            loading = true
            status.Text = "Загружаем оружие…"
            task.spawn(function()
                local ok, catalog = pcall(function() return getCatalog:InvokeServer() end)
                loading = false
                if not ok or typeof(catalog) ~= "table" or catalog.enabled ~= true then
                    status.Text = "Каталог недоступен"
                    return
                end
                rows = catalog.weapons or {}
                selectedSlug = tostring(catalog.selectedWeaponSlug or "")
                status.Text = "Выбери оружие для теста"
                drawCategories()
                renderRows()
            end)
        end
        local function resize()
            local camera = workspace.CurrentCamera
            if not camera then return end
            local viewport = camera.ViewportSize
            panel.Size = UDim2.fromOffset(math.min(294, math.max(220, viewport.X - 28)), math.min(365, math.max(218, viewport.Y - 158)))
            status.Position = UDim2.new(0, 13, 1, -31)
        end
        resize()
        launcher.Activated:Connect(function()
            panel.Visible = not panel.Visible
            if panel.Visible then refresh() end
        end)
        close.Activated:Connect(function() panel.Visible = false end)
        local camera = workspace.CurrentCamera
        if camera then camera:GetPropertyChangedSignal("ViewportSize"):Connect(resize) end
        player.CharacterAdded:Connect(function() if panel.Visible then refresh() end end)
    end)
end

return table.freeze(Controller)
