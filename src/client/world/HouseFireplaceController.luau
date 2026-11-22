--!strict
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local SpatialRoot = require(Shared:WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))
local Config = require(Shared:WaitForChild("world"):WaitForChild("FireplaceMechanicsConfig"))

local player = Players.LocalPlayer
local Controller = {}
local started = false
local tracked: {[Attachment]: BillboardGui} = {}

local function rounded(parent: GuiObject, radius: number)
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, radius)
    corner.Parent = parent
end

local function makeBar(parent: Instance, y: number, name: string, labelText: string)
    local row = Instance.new("Frame")
    row.Name = name
    row.BackgroundTransparency = 1
    row.Position = UDim2.fromOffset(10, y)
    row.Size = UDim2.new(1, -20, 0, 26)
    row.Parent = parent

    local label = Instance.new("TextLabel")
    label.Name = "Label"
    label.BackgroundTransparency = 1
    label.Size = UDim2.fromOffset(70, 24)
    label.Font = Enum.Font.GothamSemibold
    label.TextSize = 12
    label.TextColor3 = Color3.fromRGB(241, 245, 249)
    label.TextXAlignment = Enum.TextXAlignment.Left
    label.Text = labelText
    label.Parent = row

    local shell = Instance.new("Frame")
    shell.Name = "Shell"
    shell.BackgroundColor3 = Color3.fromRGB(46, 55, 66)
    shell.Position = UDim2.fromOffset(74, 4)
    shell.Size = UDim2.new(1, -74, 0, 16)
    shell.Parent = row
    rounded(shell, 8)

    local fill = Instance.new("Frame")
    fill.Name = "Fill"
    fill.BackgroundColor3 = Color3.fromRGB(231, 128, 48)
    fill.Size = UDim2.fromScale(1, 1)
    fill.Parent = shell
    rounded(fill, 8)

    local value = Instance.new("TextLabel")
    value.Name = "Value"
    value.BackgroundTransparency = 1
    value.Size = UDim2.fromScale(1, 1)
    value.Font = Enum.Font.GothamMedium
    value.TextSize = 11
    value.TextColor3 = Color3.fromRGB(250, 251, 252)
    value.Text = ""
    value.Parent = shell

    return row
end

local function build(socket: Attachment): BillboardGui
    local gui = Instance.new("BillboardGui")
    gui.Name = "Game1FireplaceHud"
    gui.Adornee = socket
    gui.AlwaysOnTop = true
    gui.LightInfluence = 0
    gui.StudsOffsetWorldSpace = Vector3.new(0, 2.6, 0)
    gui.Size = UDim2.fromOffset(220, 74)

    local frame = Instance.new("Frame")
    frame.Name = "Panel"
    frame.BackgroundColor3 = Color3.fromRGB(20, 26, 34)
    frame.BackgroundTransparency = 0.07
    frame.Size = UDim2.fromScale(1, 1)
    frame.Parent = gui
    rounded(frame, 10)
    local stroke = Instance.new("UIStroke")
    stroke.Color = Color3.fromRGB(79, 93, 109)
    stroke.Transparency = 0.18
    stroke.Parent = frame

    makeBar(frame, 8, "FuelRow", "Топливо")
    makeBar(frame, 39, "CookRow", "Блюдо")
    return gui
end

local function listen(instance: Instance)
    if not instance:IsA("Attachment") then return end
    if instance.Name ~= "fireplace_01_socket" then return end
    if tracked[instance] then return end
    local gui = build(instance)
    gui.Parent = player:WaitForChild("PlayerGui")
    tracked[instance] = gui
end

local function setBar(row: Frame, active: boolean, ratio: number, label: string, fillColor: Color3)
    row.Visible = active
    if not active then return end
    local fill = row.Shell.Fill
    fill.Size = UDim2.fromScale(math.clamp(ratio, 0, 1), 1)
    fill.BackgroundColor3 = fillColor
    row.Shell.Value.Text = label
end

local function updateOne(socket: Attachment, gui: BillboardGui, root: BasePart, serverNow: number)
    if not socket:IsDescendantOf(Workspace) then gui:Destroy(); tracked[socket] = nil; return end
    gui.Enabled = false
    local visibleRadius = tonumber(socket:GetAttribute("Game1FireplaceVisibleRadius")) or Config.ProgressVisibleRadius
    local distance = (socket.WorldPosition - root.Position).Magnitude
    if distance > visibleRadius then return end
    local fuelState = tostring(socket:GetAttribute("Game1FireplaceFuelState") or "empty")
    local fuelEndsAt = tonumber(socket:GetAttribute("Game1FireplaceFuelEndsAt")) or 0
    local fuelDuration = tonumber(socket:GetAttribute("Game1FireplaceFuelDuration")) or 0
    local cookState = tostring(socket:GetAttribute("Game1FireplaceCookState") or "idle")
    local cookEndsAt = tonumber(socket:GetAttribute("Game1FireplaceCookEndsAt")) or 0
    local cookDuration = tonumber(socket:GetAttribute("Game1FireplaceCookDuration")) or 0

    local fuelFrame = gui.Panel:FindFirstChild("FuelRow") :: Frame
    local cookFrame = gui.Panel:FindFirstChild("CookRow") :: Frame
    if not fuelFrame or not cookFrame then return end

    local fuelActive = fuelState == "firewood" or fuelState == "embers"
    local fuelRemaining = math.max(0, fuelEndsAt - serverNow)
    local fuelRatio = if fuelActive and fuelDuration > 0 then fuelRemaining / fuelDuration else 0
    setBar(fuelFrame, fuelActive, fuelRatio,
        if fuelState == "embers" then "Угли" else "Огонь",
        if fuelState == "embers" then Color3.fromRGB(205, 88, 64) else Color3.fromRGB(234, 146, 53))

    local cookActive = cookState == "cooking" or cookState == "ready"
    local cookRatio = if cookState == "ready" then 1
        elseif cookDuration > 0 then 1 - math.max(0, cookEndsAt - serverNow) / cookDuration
        else 0
    setBar(cookFrame, cookActive, cookRatio,
        if cookState == "ready" then "Готово" else string.format("%ds", math.ceil(math.max(0, cookEndsAt - serverNow))),
        Color3.fromRGB(89, 164, 111))

    gui.Enabled = fuelActive or cookActive
end

function Controller.Start()
    if started then return end
    started = true
    for _, instance in ipairs(Workspace:GetDescendants()) do listen(instance) end
    Workspace.DescendantAdded:Connect(listen)
    local acc = 0
    RunService.Heartbeat:Connect(function(dt)
        acc += dt
        if acc < 0.1 then return end
        acc = 0
        local root = SpatialRoot.Get(player)
        if not root then
            for _, gui in pairs(tracked) do gui.Enabled = false end
            return
        end
        local serverNow = Workspace:GetServerTimeNow()
        for socket, gui in pairs(tracked) do
            updateOne(socket, gui, root, serverNow)
        end
    end)
end

return table.freeze(Controller)
