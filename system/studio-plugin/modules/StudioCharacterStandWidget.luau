-- Dock widget contains presentation only. No asset imports or Workspace writes.
local Widget = {}

function Widget.new(plugin: Plugin): any
    local info = DockWidgetPluginGuiInfo.new(Enum.InitialDockState.Right, false, false, 340, 290, 300, 260)
    local dock = plugin:CreateDockWidgetPluginGui("Game1CharacterTestStand_v1", info)
    dock.Title = "game1 · Character Test Stand"

    local root = Instance.new("Frame")
    root.Name = "Root"
    root.BackgroundColor3 = Color3.fromRGB(28, 32, 39)
    root.Size = UDim2.fromScale(1, 1)
    root.BorderSizePixel = 0
    root.Parent = dock

    local layout = Instance.new("UIListLayout")
    layout.Padding = UDim.new(0, 9)
    layout.HorizontalAlignment = Enum.HorizontalAlignment.Center
    layout.SortOrder = Enum.SortOrder.LayoutOrder
    layout.Parent = root

    local padding = Instance.new("UIPadding")
    padding.PaddingTop = UDim.new(0, 14)
    padding.PaddingLeft = UDim.new(0, 12)
    padding.PaddingRight = UDim.new(0, 12)
    padding.Parent = root

    local function label(name: string, text: string, height: number): TextLabel
        local item = Instance.new("TextLabel")
        item.Name = name
        item.LayoutOrder = #root:GetChildren()
        item.Size = UDim2.new(1, 0, 0, height)
        item.BackgroundTransparency = 1
        item.Font = Enum.Font.SourceSans
        item.TextSize = 14
        item.TextColor3 = Color3.fromRGB(222, 228, 235)
        item.TextWrapped = true
        item.TextXAlignment = Enum.TextXAlignment.Left
        item.Text = text
        item.Parent = root
        return item
    end

    local function button(name: string, text: string): TextButton
        local item = Instance.new("TextButton")
        item.Name = name
        item.LayoutOrder = #root:GetChildren()
        item.Size = UDim2.new(1, 0, 0, 37)
        item.BackgroundColor3 = Color3.fromRGB(44, 75, 93)
        item.BorderSizePixel = 0
        item.Font = Enum.Font.SourceSansSemibold
        item.TextSize = 15
        item.TextColor3 = Color3.fromRGB(245, 248, 252)
        item.Text = text
        item.Parent = root
        return item
    end

    label("Description", "Профиль из опубликованного CharacterRegistry", 25)
    local profile = button("Profile", "Выбрать профиль")
    local build = button("Assemble", "1 · Собрать персонажа")
    local place = button("Place", "2 · Поставить на поверхность")
    local status = label("Status", "Выбери профиль и собери тестовую модель.", 67)
    return {dock = dock, profile = profile, build = build, place = place, status = status}
end

return table.freeze(Widget)
