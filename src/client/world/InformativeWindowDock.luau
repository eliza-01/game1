--!strict
-- Shared bottom information surface. Gameplay presenters supply content, never
-- own a second ScreenGui or write panel/collapse visibility themselves.
-- The same neutral chevron controls are reusable for other informational views.
local Players = game:GetService("Players")
local UiSettings = require(script.Parent:WaitForChild("UiPresentationSettings"))
local MobileLayout = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("mobile"):WaitForChild("MobileLayout"))

local Dock = {}
local singleton: any = nil

local function rounded(parent: GuiObject, pixels: number)
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, pixels)
    corner.Parent = parent
end

-- Real two-stroke chevrons, not a checkmark or a themed emoji.
local function chevron(button: TextButton, up: boolean, x: number)
    local left = Instance.new("Frame")
    left.Name = "ChevronLeft"
    left.AnchorPoint = Vector2.new(0.5, 0.5)
    left.Position = UDim2.new(0, x, 0.5, 0)
    left.Size = UDim2.fromOffset(10, 2)
    left.Rotation = if up then -42 else 42
    left.BorderSizePixel = 0
    left.BackgroundColor3 = Color3.fromRGB(225, 235, 242)
    left.Parent = button

    local right = left:Clone()
    right.Name = "ChevronRight"
    right.Position = UDim2.new(0, x + 7, 0.5, 0)
    right.Rotation = if up then 42 else -42
    right.Parent = button
end

function Dock.Get(): any
    if singleton then return singleton end

    local gui = Instance.new("ScreenGui")
    gui.Name = "Game1InformativeWindow"
    gui.DisplayOrder = 18
    gui.ResetOnSpawn = false
    gui.ScreenInsets = Enum.ScreenInsets.CoreUISafeInsets
    gui.SafeAreaCompatibility = Enum.SafeAreaCompatibility.None
    gui.ClipToDeviceSafeArea = true
    gui.Parent = Players.LocalPlayer:WaitForChild("PlayerGui")

    local panel = Instance.new("Frame")
    panel.Name = "Panel"
    panel.Visible = false
    panel.AnchorPoint = Vector2.new(0.5, 1)
    panel.Position = UDim2.new(0.5, 0, 1, -24)
    panel.Size = UDim2.new(0.9, 0, 0, 92)
    panel.BackgroundColor3 = Color3.fromRGB(19, 27, 35)
    panel.BackgroundTransparency = 0.04
    panel.BorderSizePixel = 0
    panel.Parent = gui
    rounded(panel, 11)
    local constraint = Instance.new("UISizeConstraint")
    constraint.Name = "SizeLimit"
    constraint.MaxSize = Vector2.new(340, 92)
    constraint.MinSize = Vector2.new(250, 92)
    constraint.Parent = panel
    local stroke = Instance.new("UIStroke")
    stroke.Color = Color3.fromRGB(89, 106, 120)
    stroke.Transparency = 0.2
    stroke.Parent = panel

    local title = Instance.new("TextLabel")
    title.Name = "SourceTitle"
    title.BackgroundTransparency = 1
    title.Position = UDim2.fromOffset(12, 5)
    title.Size = UDim2.new(1, -48, 0, 22)
    title.Font = Enum.Font.GothamSemibold
    title.TextColor3 = Color3.fromRGB(242, 247, 250)
    title.TextSize = 13
    title.TextXAlignment = Enum.TextXAlignment.Left
    title.Parent = panel

    local collapse = Instance.new("TextButton")
    collapse.Name = "Collapse"
    collapse.Position = UDim2.new(1, -34, 0, 5)
    collapse.Size = UDim2.fromOffset(26, 24)
    collapse.BackgroundColor3 = Color3.fromRGB(44, 57, 69)
    collapse.Text = ""
    collapse.AutoButtonColor = true
    collapse.Parent = panel
    rounded(collapse, 6)
    chevron(collapse, false, 9)

    local content = Instance.new("Frame")
    content.Name = "Contents"
    content.BackgroundTransparency = 1
    content.Position = UDim2.fromOffset(12, 32)
    content.Size = UDim2.new(1, -24, 0, 54)
    content.Parent = panel

    local restore = Instance.new("TextButton")
    restore.Name = "Restore"
    restore.AnchorPoint = Vector2.new(1, 1)
    restore.Size = UDim2.fromOffset(82, 40)
    restore.BackgroundColor3 = Color3.fromRGB(30, 42, 53)
    restore.BackgroundTransparency = 0.05
    restore.TextColor3 = Color3.fromRGB(240, 246, 249)
    restore.Text = "Инфо"
    restore.Font = Enum.Font.GothamSemibold
    restore.TextSize = 12
    restore.TextXAlignment = Enum.TextXAlignment.Left
    restore.Visible = false
    restore.AutoButtonColor = true
    restore.Parent = gui
    rounded(restore, 10)
    local padding = Instance.new("UIPadding")
    padding.PaddingLeft = UDim.new(0, 12)
    padding.Parent = restore
    chevron(restore, true, 53)
    local restoreStroke = Instance.new("UIStroke")
    restoreStroke.Color = Color3.fromRGB(104, 122, 139)
    restoreStroke.Transparency = 0.24
    restoreStroke.Parent = restore

    local panes: {[string]: Frame} = {}
    local collapsed: {[Instance]: boolean} = {}
    local currentSource: Instance? = nil
    local currentProvider: string? = nil
    local available = false
    local contentHeight = 54
    local lastWidth = -1
    local lastHeight = -1

    local function display()
        local show = available and currentSource ~= nil
        local isCollapsed = show and collapsed[currentSource :: Instance] == true
        panel.Visible = show and not isCollapsed
        restore.Visible = show and isCollapsed
    end

    local function applyStyle()
        local cfg = UiSettings.Current().status
        local headerHeight = math.max(24, cfg.titleFontPx + 8)
        local panelHeight = headerHeight + 6 + contentHeight + 6
        panel.Position = UDim2.new(0.5, cfg.offsetXPx, 1, -24 + cfg.offsetYPx)
        panel.Size = UDim2.new(0.9, 0, 0, panelHeight)
        constraint.MaxSize = Vector2.new(340, panelHeight)
        constraint.MinSize = Vector2.new(250, panelHeight)
        title.TextSize = cfg.titleFontPx
        title.Size = UDim2.new(1, -48, 0, headerHeight)
        content.Position = UDim2.fromOffset(12, headerHeight + 6)
        content.Size = UDim2.new(1, -24, 0, contentHeight)

        -- Use the full combat cluster, not only the attack rectangle.
        local size = gui.AbsoluteSize
        local width = if size.X >= 240 then size.X else 1280
        local height = if size.Y >= 180 then size.Y else 720
        local bounds = MobileLayout.Resolve(width, height)
        if UiSettings.ActiveDevice() == "mobile" then
            local box = MobileLayout.Context(width, height, panelHeight, math.min(340, width-24))
            panel.AnchorPoint = Vector2.new(1, 1)
            panel.Position = UDim2.new(1, -box.x + cfg.offsetXPx, 1, -box.y + cfg.offsetYPx)
            panel.Size = UDim2.fromOffset(box.width, panelHeight)
            constraint.MinSize = Vector2.new(math.min(250, box.width), panelHeight)
            local collapsedBox = MobileLayout.Context(width, height, 40, 82)
            restore.Position = UDim2.new(1, -collapsedBox.x + cfg.offsetXPx, 1, -collapsedBox.y + cfg.offsetYPx)
        else
            panel.AnchorPoint = Vector2.new(0.5, 1)
            local rightInset = bounds.jump.x + bounds.jump.size + bounds.gap
            restore.Position = UDim2.new(1, -rightInset + cfg.offsetXPx, 1, -bounds.attack.y + cfg.offsetYPx)
        end
        restore.TextSize = math.max(12, cfg.titleFontPx - 1)
    end

    collapse.Activated:Connect(function()
        if not available or not currentSource then return end
        collapsed[currentSource] = true
        display()
    end)
    restore.Activated:Connect(function()
        if not available or not currentSource then return end
        collapsed[currentSource] = nil
        display()
    end)

    local host = {}

    function host:Pane(provider: string): Frame
        local existing = panes[provider]
        if existing then return existing end
        local pane = Instance.new("Frame")
        pane.Name = provider .. "Contents"
        pane.BackgroundTransparency = 1
        pane.Size = UDim2.fromScale(1, 1)
        pane.Visible = false
        pane.Parent = content
        panes[provider] = pane
        return pane
    end

    function host:Present(provider: string, source: Instance?, caption: string, hasContent: boolean)
        if source and hasContent then
            currentSource = source
            currentProvider = provider
            available = true
            title.Text = caption
            for name, pane in pairs(panes) do
                pane.Visible = name == provider
            end
        elseif currentProvider == provider then
            available = false
            currentSource = nil
        end
        display()
    end

    function host:Forget(source: Instance)
        collapsed[source] = nil
        if currentSource == source then
            available = false
            currentSource = nil
            display()
        end
    end

    function host:Fit(height: number)
        local bounded = math.clamp(math.ceil(height), 22, 500)
        local size = gui.AbsoluteSize
        if bounded == contentHeight and size.X == lastWidth and size.Y == lastHeight then
            return
        end
        contentHeight = bounded
        lastWidth, lastHeight = size.X, size.Y
        applyStyle()
    end

    UiSettings.Changed:Connect(applyStyle)
    -- Layout is applied after the host exists; visibility never depends on
    -- a viewport-resize callback or the first frame's AbsoluteSize being nonzero.
    singleton = host
    return host
end

return table.freeze(Dock)
