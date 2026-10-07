-- Player-death UI. The server remains authoritative: this controller only exposes
-- the explicit Return to Town action once the authored death animation reached DeathIdle.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Controller = {}
local started = false
local localPlayer = Players.LocalPlayer
local screenGui: ScreenGui? = nil
local button: TextButton? = nil
local statusLabel: TextLabel? = nil
local boundCharacter: Model? = nil
local characterConnections = {}
local invoking = false

local function disconnectCharacter()
    for _, connection in ipairs(characterConnections) do
        connection:Disconnect()
    end
    table.clear(characterConnections)
    boundCharacter = nil
end

local function ensureGui()
    if screenGui and screenGui.Parent then
        return
    end
    local playerGui = localPlayer:WaitForChild("PlayerGui")
    local gui = Instance.new("ScreenGui")
    gui.Name = "Game1DeathRespawn"
    gui.ResetOnSpawn = false
    gui.IgnoreGuiInset = true
    gui.DisplayOrder = 250
    gui.Enabled = true
    gui.Parent = playerGui

    local frame = Instance.new("Frame")
    frame.Name = "Panel"
    frame.AnchorPoint = Vector2.new(0.5, 1)
    frame.Position = UDim2.fromScale(0.5, 0.88)
    frame.Size = UDim2.fromOffset(250, 78)
    frame.BackgroundColor3 = Color3.fromRGB(18, 18, 22)
    frame.BackgroundTransparency = 0.12
    frame.BorderSizePixel = 0
    frame.Visible = false
    frame.Parent = gui

    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, 7)
    corner.Parent = frame

    local title = Instance.new("TextLabel")
    title.Name = "DeathTitle"
    title.BackgroundTransparency = 1
    title.Position = UDim2.fromOffset(10, 7)
    title.Size = UDim2.new(1, -20, 0, 22)
    title.Font = Enum.Font.GothamMedium
    title.Text = "Персонаж погиб"
    title.TextColor3 = Color3.fromRGB(230, 230, 235)
    title.TextSize = 15
    title.Parent = frame

    local returnButton = Instance.new("TextButton")
    returnButton.Name = "ReturnToTown"
    returnButton.Position = UDim2.fromOffset(10, 34)
    returnButton.Size = UDim2.new(1, -20, 0, 34)
    returnButton.BackgroundColor3 = Color3.fromRGB(64, 72, 92)
    returnButton.BorderSizePixel = 0
    returnButton.Font = Enum.Font.GothamBold
    returnButton.Text = "В город"
    returnButton.TextColor3 = Color3.fromRGB(255, 255, 255)
    returnButton.TextSize = 15
    returnButton.AutoButtonColor = true
    returnButton.Parent = frame

    local buttonCorner = Instance.new("UICorner")
    buttonCorner.CornerRadius = UDim.new(0, 5)
    buttonCorner.Parent = returnButton

    local status = Instance.new("TextLabel")
    status.Name = "Status"
    status.BackgroundTransparency = 1
    status.AnchorPoint = Vector2.new(0.5, 0)
    status.Position = UDim2.new(0.5, 0, 1, 4)
    status.Size = UDim2.fromOffset(320, 18)
    status.Font = Enum.Font.Gotham
    status.Text = ""
    status.TextColor3 = Color3.fromRGB(230, 120, 120)
    status.TextSize = 12
    status.Visible = false
    status.Parent = frame

    screenGui = gui
    button = returnButton
    statusLabel = status

    returnButton.Activated:Connect(function()
        if invoking or not boundCharacter or tostring(boundCharacter:GetAttribute("LifeState") or "") ~= "DeathIdle" then
            return
        end
        invoking = true
        returnButton.Active = false
        returnButton.AutoButtonColor = false
        returnButton.Text = "Возвращение..."
        if statusLabel then
            statusLabel.Visible = false
        end
        local remotes = ReplicatedStorage:WaitForChild("Game1Remotes")
        local remote = remotes:WaitForChild("ReturnToTown") :: RemoteFunction
        local ok, accepted, errorMessage = pcall(function()
            return remote:InvokeServer()
        end)
        if not ok or accepted ~= true then
            invoking = false
            returnButton.Active = true
            returnButton.AutoButtonColor = true
            returnButton.Text = "В город"
            if statusLabel then
                statusLabel.Text = tostring(if ok then errorMessage else accepted)
                statusLabel.Visible = true
            end
        end
    end)
end

local function updateVisibility()
    ensureGui()
    local panel = screenGui and screenGui:FindFirstChild("Panel")
    if not panel or not panel:IsA("Frame") then
        return
    end
    local character = boundCharacter
    local visible = character ~= nil
        and character.Parent ~= nil
        and tostring(character:GetAttribute("LifeState") or "") == "DeathIdle"
        and character:GetAttribute("ReturnToTownAvailable") == true
    panel.Visible = visible
    if visible and button and not invoking then
        button.Active = true
        button.AutoButtonColor = true
        button.Text = "В город"
    end
end

local function bindCharacter(character: Model?)
    disconnectCharacter()
    invoking = false
    if not character then
        updateVisibility()
        return
    end
    boundCharacter = character
    table.insert(characterConnections, character:GetAttributeChangedSignal("LifeState"):Connect(updateVisibility))
    table.insert(characterConnections, character:GetAttributeChangedSignal("ReturnToTownAvailable"):Connect(updateVisibility))
    table.insert(characterConnections, character.Destroying:Connect(function()
        if boundCharacter == character then
            disconnectCharacter()
            updateVisibility()
        end
    end))
    updateVisibility()
end

function Controller.Start()
    if started then
        return
    end
    started = true
    ensureGui()
    localPlayer.CharacterAdded:Connect(function(character)
        bindCharacter(character)
    end)
    localPlayer.CharacterRemoving:Connect(function(character)
        if boundCharacter == character then
            disconnectCharacter()
            updateVisibility()
        end
    end)
    if localPlayer.Character then
        task.defer(bindCharacter, localPlayer.Character)
    else
        updateVisibility()
    end
end

return table.freeze(Controller)
