--!strict
-- One dismissible bottom HUD for House fireplaces and world Campfires.
-- Server attributes own time/state; this client only chooses the nearest
-- active source within the configurable presentation radius.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local SpatialRoot = require(Shared:WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))
local Config = require(Shared:WaitForChild("world"):WaitForChild("FireplaceMechanicsConfig"))
local UiSettings = require(script.Parent:WaitForChild("UiPresentationSettings"))

local player = Players.LocalPlayer
local Controller = {}
local started = false
local tracked: {[Attachment]: boolean} = {}
local dismissed: {[Attachment]: boolean} = {}
local selected: Attachment? = nil

local function rounded(parent: GuiObject, radius: number)
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, radius)
    corner.Parent = parent
end

local function row(parent: Frame, y: number, name: string, title: string): Frame
    local container = Instance.new("Frame")
    container.Name = name
    container.BackgroundTransparency = 1
    container.Position = UDim2.fromOffset(12, y)
    container.Size = UDim2.new(1, -24, 0, 25)
    container.Parent = parent

    local label = Instance.new("TextLabel")
    label.BackgroundTransparency = 1
    label.Size = UDim2.fromOffset(65, 22)
    label.Font = Enum.Font.GothamSemibold
    label.TextSize = 12
    label.Text = title
    label.TextXAlignment = Enum.TextXAlignment.Left
    label.TextColor3 = Color3.fromRGB(240, 245, 249)
    label.Parent = container

    local bar = Instance.new("Frame")
    bar.Name = "Bar"
    bar.Position = UDim2.fromOffset(68, 3)
    bar.Size = UDim2.new(1, -68, 0, 16)
    bar.BackgroundColor3 = Color3.fromRGB(48, 60, 70)
    bar.ClipsDescendants = true
    bar.Parent = container
    rounded(bar, 7)

    local fill = Instance.new("Frame")
    fill.Name = "Fill"
    fill.Size = UDim2.fromScale(0, 1)
    fill.BackgroundColor3 = Color3.fromRGB(232, 136, 52)
    fill.Parent = bar
    rounded(fill, 7)

    local remaining = Instance.new("TextLabel")
    remaining.Name = "Remaining"
    remaining.Size = UDim2.fromScale(1, 1)
    remaining.BackgroundTransparency = 1
    remaining.Font = Enum.Font.GothamMedium
    remaining.TextColor3 = Color3.fromRGB(249, 249, 249)
    remaining.TextSize = 11
    remaining.Parent = bar
    return container
end

local function ui(): (Frame, Frame, Frame)
    local screen = Instance.new("ScreenGui")
    screen.Name = "Game1FireplaceStatus"
    screen.ResetOnSpawn = false
    screen.DisplayOrder = 18
    screen.ScreenInsets = Enum.ScreenInsets.CoreUISafeInsets
    screen.Parent = player:WaitForChild("PlayerGui")

    local panel = Instance.new("Frame")
    panel.Name = "Panel"
    panel.Visible = false
    panel.AnchorPoint = Vector2.new(0.5, 1)
    panel.Position = UDim2.new(0.5, 0, 1, -24)
    panel.Size = UDim2.new(0.9, 0, 0, 92)
    panel.BackgroundColor3 = Color3.fromRGB(19, 27, 35)
    panel.BackgroundTransparency = 0.04
    panel.Parent = screen
    rounded(panel, 11)
    local constraint = Instance.new("UISizeConstraint")
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
    title.Size = UDim2.new(1, -48, 0, 20)
    title.Font = Enum.Font.GothamSemibold
    title.Text = "Камин"
    title.TextColor3 = Color3.fromRGB(242, 247, 250)
    title.TextSize = 13
    title.TextXAlignment = Enum.TextXAlignment.Left
    title.Parent = panel

    local close = Instance.new("TextButton")
    close.Name = "Dismiss"
    close.Position = UDim2.new(1, -32, 0, 5)
    close.Size = UDim2.fromOffset(25, 23)
    close.Text = "×"
    close.Font = Enum.Font.GothamSemibold
    close.TextSize = 18
    close.TextColor3 = Color3.fromRGB(220, 226, 232)
    close.BackgroundColor3 = Color3.fromRGB(44, 57, 69)
    close.Parent = panel
    rounded(close, 6)
    close.Activated:Connect(function()
        if selected then dismissed[selected] = true end
        panel.Visible = false
    end)
    local fuelRow = row(panel, 30, "FuelRow", "Огонь")
    local cookRow = row(panel, 60, "CookRow", "Блюдо")
    local function applyStyle()
        local cfg = UiSettings.Current().status
        local barHeight = math.max(16, cfg.timerFontPx + 6)
        local rowHeight = math.max(25, cfg.labelFontPx + 6, barHeight + 4)
        local headerHeight = math.max(24, cfg.titleFontPx + 8)
        local firstRowTop = headerHeight + 6
        local panelHeight = firstRowTop + 2 * rowHeight + 4
        panel.Position = UDim2.new(0.5, cfg.offsetXPx, 1, -24 + cfg.offsetYPx)
        panel.Size = UDim2.new(0.9, 0, 0, panelHeight)
        constraint.MaxSize = Vector2.new(340, panelHeight)
        constraint.MinSize = Vector2.new(250, panelHeight)
        title.TextSize = cfg.titleFontPx
        title.Size = UDim2.new(1, -48, 0, headerHeight)
        for index, entry in ipairs({fuelRow, cookRow}) do
            entry.Position = UDim2.fromOffset(12, firstRowTop + (index - 1) * (rowHeight + 2))
            entry.Size = UDim2.new(1, -24, 0, rowHeight)
            local label = entry:FindFirstChildOfClass("TextLabel")
            if label then
                label.TextSize = cfg.labelFontPx
                label.Size = UDim2.fromOffset(65, rowHeight)
            end
            entry.Bar.Position = UDim2.fromOffset(68, math.floor((rowHeight - barHeight) / 2))
            entry.Bar.Size = UDim2.new(1, -68, 0, barHeight)
            entry.Bar.Remaining.TextSize = cfg.timerFontPx
        end
    end
    applyStyle()
    UiSettings.Changed:Connect(applyStyle)
    return panel, fuelRow, cookRow
end

local function listen(instance: Instance)
    if not instance:IsA("Attachment") then return end
    if instance.Name ~= "fireplace_01_socket" and instance.Name ~= "fire_socket" then return end
    tracked[instance] = true
end

local function socketPosition(socket: Attachment): Vector3
    return if socket:IsA("Bone") then (socket :: Bone).TransformedWorldCFrame.Position else socket.WorldPosition
end

local function active(socket: Attachment): boolean
    local fuel = socket:GetAttribute("Game1FireplaceFuelState")
    local cooking = socket:GetAttribute("Game1FireplaceCookState")
    return fuel == "firewood" or fuel == "fire" or fuel == "embers"
        or cooking == "cooking" or cooking == "ready"
end

local function setBar(entry: Frame, ratio: number, caption: string, color: Color3)
    entry.Visible = true
    entry.Bar.Fill.Size = UDim2.fromScale(math.clamp(ratio, 0, 1), 1)
    entry.Bar.Fill.BackgroundColor3 = color
    entry.Bar.Remaining.Text = caption
end

local function render(socket: Attachment, panel: Frame, fuelRow: Frame, cookRow: Frame, timeNow: number)
    local fuel = tostring(socket:GetAttribute("Game1FireplaceFuelState") or "empty")
    local fuelEnd = tonumber(socket:GetAttribute("Game1FireplaceFuelEndsAt")) or 0
    local fuelDuration = tonumber(socket:GetAttribute("Game1FireplaceFuelDuration")) or 0
    local cook = tostring(socket:GetAttribute("Game1FireplaceCookState") or "idle")
    local cookEnd = tonumber(socket:GetAttribute("Game1FireplaceCookEndsAt")) or 0
    local cookDuration = tonumber(socket:GetAttribute("Game1FireplaceCookDuration")) or 0

    panel.SourceTitle.Text = if socket.Name == "fire_socket" then "Костёр" else "Камин"
    fuelRow.Visible = false
    cookRow.Visible = false
    if fuel == "firewood" or fuel == "fire" or fuel == "embers" then
        local remaining = math.max(0, fuelEnd - timeNow)
        local ratio = if fuelDuration > 0 then remaining / fuelDuration else 0
        setBar(fuelRow, ratio,
            (if fuel == "embers" then "Угли · " else "Огонь · ") .. tostring(math.ceil(remaining)) .. "с",
            if fuel == "embers" then Color3.fromRGB(192, 76, 67) else Color3.fromRGB(235, 145, 55))
    end
    if cook == "cooking" or cook == "ready" then
        local remaining = math.max(0, cookEnd - timeNow)
        setBar(cookRow, if cook == "ready" then 1 else if cookDuration > 0 then 1 - remaining / cookDuration else 0,
            if cook == "ready" then "Готово" else tostring(math.ceil(remaining)) .. "с",
            Color3.fromRGB(92, 171, 116))
    end
    panel.Visible = fuelRow.Visible or cookRow.Visible
end

function Controller.Start()
    if started then return end
    started = true
    local panel, fuelRow, cookRow = ui()
    for _, descendant in ipairs(Workspace:GetDescendants()) do listen(descendant) end
    Workspace.DescendantAdded:Connect(listen)
    local elapsed = 0
    RunService.Heartbeat:Connect(function(dt)
        elapsed += dt
        if elapsed < 0.1 then return end
        elapsed = 0
        local root = SpatialRoot.Get(player)
        local closest: Attachment? = nil
        local minDistance = math.huge
        for socket in pairs(tracked) do
            if not socket:IsDescendantOf(Workspace) then
                tracked[socket] = nil
                dismissed[socket] = nil
            elseif root then
                local radius = tonumber(socket:GetAttribute("Game1FireplaceVisibleRadius")) or Config.ProgressVisibleRadius
                local distance = (socketPosition(socket) - root.Position).Magnitude
                if distance > radius then
                    dismissed[socket] = nil
                elseif active(socket) and not dismissed[socket] and distance < minDistance then
                    minDistance = distance
                    closest = socket
                end
            end
        end
        selected = closest
        if closest and root then
            render(closest, panel, fuelRow, cookRow, Workspace:GetServerTimeNow())
        else
            panel.Visible = false
        end
    end)
end

return table.freeze(Controller)
