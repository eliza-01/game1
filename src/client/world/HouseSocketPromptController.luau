--!strict
-- One compact, consistent prompt for every authored house interaction.
-- Keyboard/gamepad targeting and line of sight remain Roblox-owned.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ProximityPromptService = game:GetService("ProximityPromptService")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Contract = require(Shared:WaitForChild("world"):WaitForChild("HouseSocketContract"))
local SpatialRoot = require(Shared:WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))
local player = Players.LocalPlayer
local Controller = {}
local started = false
local prompts: {[ProximityPrompt]: RBXScriptConnection} = {}
local visible: {[ProximityPrompt]: BillboardGui} = {}
local selectedCustom: ProximityPrompt? = nil

local function radius(name: string): number
    local definition = Contract.Get(name)
    if not definition then return 0 end
    local attr = player:GetAttribute(Contract.RadiusAttribute(name))
    if typeof(attr) == "number" then
        return math.clamp(attr, Contract.MinDebugRadius, Contract.MaxDebugRadius)
    end
    return definition.radius
end

local function listen(instance: Instance)
    if not instance:IsA("ProximityPrompt") or instance.Name ~= "Game1HouseInteraction"
        or prompts[instance] then return end
    local name = instance:GetAttribute("Game1HouseSocketName")
    if typeof(name) ~= "string" or not Contract.Get(name) then return end
    local prompt: ProximityPrompt = instance
    prompt.MaxActivationDistance = radius(name)
    prompts[prompt] = prompt.AncestryChanged:Connect(function()
        if not prompt:IsDescendantOf(Workspace) then
            local connection = prompts[prompt]
            if connection then connection:Disconnect() end
            prompts[prompt] = nil
            local gui = visible[prompt]
            if gui then gui:Destroy(); visible[prompt] = nil end
        end
    end)
end

function Controller.SetRadius(name: string, value: number)
    for prompt in prompts do
        if prompt:GetAttribute("Game1HouseSocketName") == name then
            prompt.MaxActivationDistance = value
        end
    end
end

local function rounded(parent: Instance, radiusPixels: number)
    local item = Instance.new("UICorner")
    item.CornerRadius = UDim.new(0, radiusPixels)
    item.Parent = parent
end

local function makeGui(prompt: ProximityPrompt): BillboardGui?
    local anchor = prompt.Parent
    if not anchor or not anchor:IsA("Attachment") then return nil end
    local gui = Instance.new("BillboardGui")
    gui.Name = "Game1HousePrompt"
    gui.Adornee = anchor
    gui.Size = UDim2.fromOffset(232, 48)
    gui.StudsOffsetWorldSpace = Vector3.new(0, 1.15, 0)
    gui.AlwaysOnTop = true
    gui.LightInfluence = 0
    gui.ResetOnSpawn = false
    gui.Parent = player:WaitForChild("PlayerGui")
    local background = Instance.new("Frame")
    background.Name = "Panel"
    background.BackgroundColor3 = Color3.fromRGB(18, 24, 31)
    background.BackgroundTransparency = 0.06
    background.Size = UDim2.fromScale(1, 1)
    background.Parent = gui
    rounded(background, 11)
    local stroke = Instance.new("UIStroke")
    stroke.Color = Color3.fromRGB(75, 91, 104)
    stroke.Thickness = 1
    stroke.Transparency = 0.12
    stroke.Parent = background
    local key = Instance.new("TextLabel")
    key.Name = "Key"
    key.Position = UDim2.fromOffset(8, 7)
    key.Size = UDim2.fromOffset(34, 34)
    key.BackgroundColor3 = Color3.fromRGB(41, 54, 65)
    key.TextColor3 = Color3.fromRGB(242, 246, 249)
    key.Font = Enum.Font.GothamBold
    key.TextSize = 16
    key.Text = "F"
    key.Parent = background
    rounded(key, 7)
    local keyStroke = Instance.new("UIStroke")
    keyStroke.Color = Color3.fromRGB(122, 141, 155)
    keyStroke.Transparency = 0.2
    keyStroke.Parent = key
    local text = Instance.new("TextLabel")
    text.Name = "Action"
    text.Position = UDim2.fromOffset(51, 5)
    text.Size = UDim2.new(1, -61, 1, -10)
    text.BackgroundTransparency = 1
    text.TextColor3 = Color3.fromRGB(244, 246, 249)
    text.TextXAlignment = Enum.TextXAlignment.Left
    text.TextYAlignment = Enum.TextYAlignment.Center
    text.Font = Enum.Font.GothamSemibold
    text.TextSize = 13
    text.TextTruncate = Enum.TextTruncate.AtEnd
    text.Text = prompt.ActionText
    text.Parent = background
    local change = prompt:GetPropertyChangedSignal("ActionText"):Connect(function()
        text.Text = prompt.ActionText
    end)
    gui.Destroying:Connect(function() change:Disconnect() end)
    return gui
end

-- The custom ControllerManager character has no Humanoid. Keep the native
-- ProximityPrompt path for standard avatars, but select cached server-created
-- prompts locally for game1's character. No per-frame Workspace traversal.
local function nearestCustomPrompt(root: BasePart): ProximityPrompt?
    local camera = Workspace.CurrentCamera
    if not camera then return nil end
    local mousePosition = UserInputService:GetMouseLocation()
    local nearest: ProximityPrompt? = nil
    local bestDistance = math.huge
    for prompt in prompts do
        if not prompt.Enabled or not prompt:IsDescendantOf(Workspace) then continue end
        local socket = prompt.Parent
        if not socket or not socket:IsA("Attachment") then continue end
        local name = prompt:GetAttribute("Game1HouseSocketName")
        if typeof(name) ~= "string" then continue end
        local definition = Contract.Get(name)
        if not definition or not definition.interact then continue end
        local frame = if socket:IsA("Bone") then socket.TransformedWorldCFrame else socket.WorldCFrame
        local distance = (frame.Position - root.Position).Magnitude
        if distance > radius(name) then continue end
        local projected, onScreen = camera:WorldToViewportPoint(frame.Position)
        if not onScreen or projected.Z <= 0 then continue end
        if definition.role == "elevator" then
            -- Lift selection is gaze/mouse-directed within its screen region.
            if (Vector2.new(projected.X, projected.Y) - mousePosition).Magnitude > 140 then continue end
        end
        if distance < bestDistance then
            nearest, bestDistance = prompt, distance
        end
    end
    return nearest
end

local function updateCustomPrompt()
    local root = if SpatialRoot.IsCustom(player) then SpatialRoot.Get(player) else nil
    local nextPrompt = if root then nearestCustomPrompt(root) else nil
    if selectedCustom == nextPrompt then return end
    if selectedCustom then
        local old = visible[selectedCustom]
        if old then old:Destroy(); visible[selectedCustom] = nil end
    end
    selectedCustom = nextPrompt
    if nextPrompt then
        local gui = makeGui(nextPrompt)
        if gui then visible[nextPrompt] = gui end
    end
end

function Controller.Start()
    if started then return end
    started = true
    for _, instance in Workspace:GetDescendants() do listen(instance) end
    Workspace.DescendantAdded:Connect(listen)
    for _, definition in Contract.Definitions do
        player:GetAttributeChangedSignal(Contract.RadiusAttribute(definition.name)):Connect(function()
            Controller.SetRadius(definition.name, radius(definition.name))
        end)
    end
    task.spawn(function()
        local remotes = ReplicatedStorage:WaitForChild("Game1Remotes", 15)
        local feedbackRemote = remotes and remotes:WaitForChild("HouseSocketFeedback", 15)
        if not feedbackRemote or not feedbackRemote:IsA("RemoteEvent") then return end
        local gui = Instance.new("ScreenGui")
        gui.Name = "Game1HouseFeedback"
        gui.DisplayOrder = 35
        gui.ResetOnSpawn = false
        gui.Parent = player:WaitForChild("PlayerGui")
        local message = Instance.new("TextLabel")
        message.AnchorPoint = Vector2.new(0.5, 1)
        message.Position = UDim2.new(0.5, 0, 0.83, 0)
        message.Size = UDim2.fromOffset(280, 42)
        message.BackgroundColor3 = Color3.fromRGB(22, 30, 39)
        message.TextColor3 = Color3.fromRGB(239, 245, 248)
        message.Font = Enum.Font.GothamMedium
        message.TextSize = 13
        message.Visible = false
        message.Parent = gui
        rounded(message, 9)
        local revision = 0
        feedbackRemote.OnClientEvent:Connect(function(text)
            if typeof(text) ~= "string" then return end
            revision += 1
            local thisRevision = revision
            message.Text = text
            message.Visible = true
            task.delay(2.7, function()
                if revision == thisRevision then message.Visible = false end
            end)
        end)
    end)
    -- Ten hertz is sufficient for range/visibility UI. The server still
    -- authoritatively validates each F interaction and player life state.
    local elapsed = 0
    RunService.Heartbeat:Connect(function(dt)
        elapsed += dt
        if elapsed < 0.1 then return end
        elapsed = 0
        updateCustomPrompt()
    end)
    UserInputService.InputBegan:Connect(function(input, processed)
        if processed or input.KeyCode ~= Enum.KeyCode.F or UserInputService:GetFocusedTextBox() then return end
        if not SpatialRoot.IsCustom(player) or not SpatialRoot.Get(player) then return end
        local prompt = selectedCustom
        if not prompt or not prompt.Enabled or not prompt:IsDescendantOf(Workspace) then return end
        local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
        local remote = folder and folder:FindFirstChild("HouseSocketInteract")
        local socket = prompt.Parent
        if remote and remote:IsA("RemoteEvent") and socket and socket:IsA("Attachment") then
            remote:FireServer(socket)
        end
    end)
    ProximityPromptService.PromptShown:Connect(function(prompt)
        if SpatialRoot.IsCustom(player) then return end
        if prompt.Name ~= "Game1HouseInteraction" then return end
        if visible[prompt] then return end
        local gui = makeGui(prompt)
        if gui then visible[prompt] = gui end
    end)
    ProximityPromptService.PromptHidden:Connect(function(prompt)
        if SpatialRoot.IsCustom(player) then return end
        local gui = visible[prompt]
        if gui then gui:Destroy(); visible[prompt] = nil end
    end)
end

return table.freeze(Controller)
