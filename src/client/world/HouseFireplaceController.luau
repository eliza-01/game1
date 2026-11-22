--!strict
-- Fireplace/Campfire information presenter. The shared InformativeWindowDock
-- alone owns open/collapsed visibility; this module only selects a registered
-- source in range and fills its two status rows from server-owned attributes.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local SpatialRoot = require(Shared:WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))
local Config = require(Shared:WaitForChild("world"):WaitForChild("FireplaceMechanicsConfig"))
local UiSettings = require(script.Parent:WaitForChild("UiPresentationSettings"))
local InfoDock = require(script.Parent:WaitForChild("InformativeWindowDock"))

local player = Players.LocalPlayer
local Controller = {}
local started = false
local tracked: {[Attachment]: boolean} = {}

local function rounded(parent: GuiObject, pixels: number)
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, pixels)
    corner.Parent = parent
end

local function barRow(parent: Frame, name: string, title: string): Frame
    local entry = Instance.new("Frame")
    entry.Name = name
    entry.BackgroundTransparency = 1
    entry.Size = UDim2.new(1, 0, 0, 25)
    entry.Parent = parent

    local label = Instance.new("TextLabel")
    label.Name = "Label"
    label.BackgroundTransparency = 1
    label.Text = title
    label.Font = Enum.Font.GothamSemibold
    label.TextColor3 = Color3.fromRGB(240, 245, 249)
    label.TextXAlignment = Enum.TextXAlignment.Left
    label.Size = UDim2.fromOffset(65, 22)
    label.Parent = entry

    local bar = Instance.new("Frame")
    bar.Name = "Bar"
    bar.Position = UDim2.fromOffset(68, 3)
    bar.Size = UDim2.new(1, -68, 0, 16)
    bar.BackgroundColor3 = Color3.fromRGB(48, 60, 70)
    bar.ClipsDescendants = true
    bar.Parent = entry
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
    return entry
end

local function listen(instance: Instance)
    if not instance:IsA("Attachment") then return end
    if instance.Name ~= "fireplace_01_socket" and instance.Name ~= "fire_socket" then return end
    tracked[instance] = true
end

local function socketPosition(socket: Attachment): Vector3
    return if socket:IsA("Bone") then (socket :: Bone).TransformedWorldCFrame.Position else socket.WorldPosition
end

local function registered(socket: Attachment): boolean
    -- Unmanaged authoring Bones/Attachments must not create empty status HUDs.
    -- A recognized server source writes this attribute on registration.
    return typeof(socket:GetAttribute("Game1FireplaceFuelState")) == "string"
end

local function setBar(entry: Frame, ratio: number, caption: string, color: Color3)
    entry.Bar.Fill.Size = UDim2.fromScale(math.clamp(ratio, 0, 1), 1)
    entry.Bar.Fill.BackgroundColor3 = color
    entry.Bar.Remaining.Text = caption
end

function Controller.Start()
    if started then return end
    started = true
    local dock = InfoDock.Get()
    local pane = dock:Pane("fireplace")
    local fuelRow = barRow(pane, "FuelRow", "Огонь")
    local cookRow = barRow(pane, "CookRow", "Блюдо")
    local rowHeight = 25

    local function applyStyle()
        local cfg = UiSettings.Current().status
        local barHeight = math.max(16, cfg.timerFontPx + 6)
        rowHeight = math.max(25, cfg.labelFontPx + 6, barHeight + 4)
        for index, entry in ipairs({fuelRow, cookRow}) do
            entry.Position = UDim2.fromOffset(0, (index - 1) * (rowHeight + 2))
            entry.Size = UDim2.new(1, 0, 0, rowHeight)
            entry.Label.TextSize = cfg.labelFontPx
            entry.Label.Size = UDim2.fromOffset(65, rowHeight)
            entry.Bar.Position = UDim2.fromOffset(68, math.floor((rowHeight - barHeight) / 2))
            entry.Bar.Size = UDim2.new(1, -68, 0, barHeight)
            entry.Bar.Remaining.TextSize = cfg.timerFontPx
        end
    end
    applyStyle()
    UiSettings.Changed:Connect(applyStyle)

    local function render(socket: Attachment, timeNow: number)
        local fuel = tostring(socket:GetAttribute("Game1FireplaceFuelState") or "empty")
        local fuelEnd = tonumber(socket:GetAttribute("Game1FireplaceFuelEndsAt")) or 0
        local fuelDuration = tonumber(socket:GetAttribute("Game1FireplaceFuelDuration")) or 0
        local cook = tostring(socket:GetAttribute("Game1FireplaceCookState") or "idle")
        local cookEnd = tonumber(socket:GetAttribute("Game1FireplaceCookEndsAt")) or 0
        local cookDuration = tonumber(socket:GetAttribute("Game1FireplaceCookDuration")) or 0
        local potPresent = socket:GetAttribute("Game1FireplacePotPresent") == true

        -- An empty registered source still reports "Не горит". Previously the
        -- entire information HUD disappeared when the active predicate failed,
        -- making collapse/restore impossible to distinguish from a broken UI.
        if fuel == "firewood" or fuel == "fire" or fuel == "embers" then
            local remaining = math.max(0, fuelEnd - timeNow)
            setBar(fuelRow, if fuelDuration > 0 then remaining / fuelDuration else 0,
                (if fuel == "embers" then "Угли · " else "Огонь · ") .. tostring(math.ceil(remaining)) .. "с",
                if fuel == "embers" then Color3.fromRGB(192, 76, 67) else Color3.fromRGB(235, 145, 55))
        else
            setBar(fuelRow, 0, "Не горит", Color3.fromRGB(105, 116, 126))
        end
        fuelRow.Visible = true

        cookRow.Visible = potPresent or cook == "cooking" or cook == "ready"
        if cook == "cooking" or cook == "ready" then
            local remaining = math.max(0, cookEnd - timeNow)
            setBar(cookRow,
                if cook == "ready" then 1 else if cookDuration > 0 then 1 - remaining / cookDuration else 0,
                if cook == "ready" then "Готово" else tostring(math.ceil(remaining)) .. "с",
                Color3.fromRGB(92, 171, 116))
        elseif potPresent then
            setBar(cookRow, 0, "Пустой котёл", Color3.fromRGB(105, 116, 126))
        end

        local contentHeight = rowHeight + (if cookRow.Visible then rowHeight + 2 else 0)
        dock:Fit(contentHeight)
        dock:Present("fireplace", socket,
            if socket.Name == "fire_socket" then "Костёр" else "Камин", true)
    end

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
                dock:Forget(socket)
            elseif root then
                local radius = tonumber(socket:GetAttribute("Game1FireplaceVisibleRadius")) or Config.ProgressVisibleRadius
                local distance = (socketPosition(socket) - root.Position).Magnitude
                if distance > radius then
                    dock:Forget(socket)
                elseif registered(socket) and distance < minDistance then
                    minDistance = distance
                    closest = socket
                end
            end
        end
        if closest then
            render(closest, Workspace:GetServerTimeNow())
        else
            dock:Present("fireplace", nil, "", false)
        end
    end)
end

return table.freeze(Controller)
