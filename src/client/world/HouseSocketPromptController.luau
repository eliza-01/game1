--!strict
-- One compact, consistent prompt for every authored house interaction.
-- The server owns prompt/action state; client groups E/F into one badge.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ProximityPromptService = game:GetService("ProximityPromptService")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Contract = require(Shared:WaitForChild("world"):WaitForChild("HouseSocketContract"))
local Aim = require(Shared:WaitForChild("world"):WaitForChild("HouseSocketAimPolicy"))
local Occlusion = require(script.Parent:WaitForChild("HouseSocketAimOcclusion"))
local SpatialRoot = require(Shared:WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))
local player = Players.LocalPlayer
local Controller = {}
local started = false
local prompts: {[ProximityPrompt]: RBXScriptConnection} = {}
-- Exactly one BillboardGui per socket (inside/outside each get one panel).
local visible: {[Attachment]: BillboardGui} = {}
local visibleSignature: {[Attachment]: string} = {}
local nativeShown: {[ProximityPrompt]: boolean} = {}
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

local function hoverRadius(name: string): number
    local definition = Contract.Get(name)
    if not definition or not definition.hoverRadius then return 0 end
    local override = player:GetAttribute(Contract.HoverRadiusAttribute(name))
    return if typeof(override) == "number"
        then math.clamp(override, Contract.MinHoverRadius, Contract.MaxHoverRadius)
        else definition.hoverRadius
end

-- AIM sockets (elevator + chest) use the same client reticle path for both
-- character types; native prompts cannot bypass AIM visibility.
local function clientNativeDistance(name: string): number
    local definition = Contract.Get(name)
    return if definition and definition.hoverRadius then 0 else radius(name)
end

local function listen(instance: Instance)
    if not instance:IsA("ProximityPrompt") or (instance.Name ~= "Game1HouseInteraction"
        and instance.Name ~= "Game1HouseInteractionAlternate") or prompts[instance] then return end
    local name = instance:GetAttribute("Game1HouseSocketName")
    if typeof(name) ~= "string" or not Contract.Get(name) then return end
    local prompt: ProximityPrompt = instance
    prompt.MaxActivationDistance = clientNativeDistance(name)
    prompts[prompt] = prompt.AncestryChanged:Connect(function()
        if not prompt:IsDescendantOf(Workspace) then
            local connection = prompts[prompt]
            if connection then connection:Disconnect() end
            prompts[prompt] = nil
            nativeShown[prompt] = nil
            local socket = prompt.Parent
            if socket and socket:IsA("Attachment") then
                local gui = visible[socket]
                if gui then gui:Destroy(); visible[socket] = nil; visibleSignature[socket] = nil end
            end
        end
    end)
end

function Controller.SetRadius(name: string, value: number)
    for prompt in prompts do
        if prompt:GetAttribute("Game1HouseSocketName") == name then
            local definition = Contract.Get(name)
            prompt.MaxActivationDistance = if definition and definition.hoverRadius then 0 else value
        end
    end
end

local function rounded(parent: Instance, radiusPixels: number)
    local item = Instance.new("UICorner")
    item.CornerRadius = UDim.new(0, radiusPixels)
    item.Parent = parent
end

-- E and F at the same socket are represented as ONE panel. Both actions
-- remain individual server-authored ProximityPrompts for native activation.
local function availableActions(socket: Attachment): {ProximityPrompt}
    local actions: {ProximityPrompt} = {}
    for _, name in {"Game1HouseInteraction", "Game1HouseInteractionAlternate"} do
        local prompt = socket:FindFirstChild(name)
        if prompt and prompt:IsA("ProximityPrompt") and prompt.Enabled then
            table.insert(actions, prompt)
        end
    end
    return actions
end

local function keyOwned(): boolean
    return player:GetAttribute("Game1HouseTestKeyOwned") ~= false
end

local function actionLabel(action: string): string
    local escaped = action:gsub("&", "&amp;"):gsub("<", "&lt;"):gsub(">", "&gt;")
    local color = if keyOwned() then "#4DD8A8" else "#FF6E6E"
    -- Only the actual word key is colored, never the whole action.
    local colored = escaped:gsub("ключ", '<font color="' .. color .. '">ключ</font>')
    return colored
end

local function signature(actions: {ProximityPrompt}): string
    local parts = {if keyOwned() then "own" else "lost"}
    for _, prompt in actions do
        table.insert(parts, prompt.KeyboardKeyCode.Name .. "=" .. prompt.ActionText)
    end
    return table.concat(parts, "|")
end

local function makeGui(socket: Attachment, actions: {ProximityPrompt}): BillboardGui
    local gui = Instance.new("BillboardGui")
    gui.Name = "Game1HousePrompt"
    gui.Adornee = socket
    gui.Size = UDim2.fromOffset(272, 12 + #actions * 40)
    gui.StudsOffsetWorldSpace = Vector3.new(0, 1.45, 0)
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
    for index, prompt in actions do
        local y = 6 + (index - 1) * 40
        local key = Instance.new("TextLabel")
        key.Name = "Key"
        key.Position = UDim2.fromOffset(8, y)
        key.Size = UDim2.fromOffset(34, 34)
        key.BackgroundColor3 = Color3.fromRGB(41, 54, 65)
        key.TextColor3 = Color3.fromRGB(242, 246, 249)
        key.Font = Enum.Font.GothamBold
        key.TextSize = 16
        key.Text = prompt.KeyboardKeyCode.Name
        key.Parent = background
        rounded(key, 7)
        local keyStroke = Instance.new("UIStroke")
        keyStroke.Color = Color3.fromRGB(122, 141, 155)
        keyStroke.Transparency = 0.2
        keyStroke.Parent = key
        local text = Instance.new("TextLabel")
        text.Name = "Action"
        text.Position = UDim2.fromOffset(51, y)
        text.Size = UDim2.new(1, -61, 0, 34)
        text.BackgroundTransparency = 1
        text.TextColor3 = Color3.fromRGB(244, 246, 249)
        text.RichText = true
        text.TextXAlignment = Enum.TextXAlignment.Left
        text.TextYAlignment = Enum.TextYAlignment.Center
        text.Font = Enum.Font.GothamSemibold
        text.TextSize = 13
        text.TextTruncate = Enum.TextTruncate.AtEnd
        text.Text = actionLabel(prompt.ActionText)
        text.Parent = background
    end
    return gui
end

local function hideSocket(socket: Attachment)
    local gui = visible[socket]
    if gui then gui:Destroy(); visible[socket] = nil end
    visibleSignature[socket] = nil
end

local function renderSocket(socket: Attachment)
    local actions = availableActions(socket)
    if #actions == 0 then hideSocket(socket); return end
    local state = signature(actions)
    if visible[socket] and visibleSignature[socket] == state then return end
    hideSocket(socket)
    visible[socket] = makeGui(socket, actions)
    visibleSignature[socket] = state
end

local function nativeActive(socket: Attachment): boolean
    for prompt in nativeShown do
        if prompt.Parent == socket and prompt.Enabled then return true end
    end
    return false
end

-- The same reticle ray as headshot aim (viewport center) selects AIM-enabled
-- sockets. Do not raycast the camera/mouse cursor or spawn queryable aim Parts:
-- queryable proxies would interfere with combat rays. After the mathematical
-- ray/sphere contact, a real Workspace raycast rejects occluded targets.
-- Both custom and standard characters use this path for AIM sockets. Others
-- retain the existing proximity behavior on custom characters.
local function nearestCustomPrompt(root: BasePart, aimedOnly: boolean): ProximityPrompt?
    local camera = Workspace.CurrentCamera
    if not camera then return nil end
    local viewport = camera.ViewportSize
    local ray = camera:ViewportPointToRay(viewport.X * 0.5, viewport.Y * 0.5)
    local selectedAim: ProximityPrompt? = nil
    local aimEntry = math.huge
    local selectedOther: ProximityPrompt? = nil
    local otherDistance = math.huge
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
        -- USE always uses the character root, not the camera.
        if distance > radius(name) then continue end
        if definition.hoverRadius then
            local hit = Aim.RaySphereEntry(ray.Origin, ray.Direction, frame.Position, hoverRadius(name))
            if hit == nil then continue end
            if hit < aimEntry - 0.001 or (math.abs(hit - aimEntry) <= 0.001
                and prompt.KeyboardKeyCode == Enum.KeyCode.E
                and (not selectedAim or selectedAim.KeyboardKeyCode ~= Enum.KeyCode.E)) then
                selectedAim, aimEntry = prompt, hit
            end
        elseif not aimedOnly then
            local projected, onScreen = camera:WorldToViewportPoint(frame.Position)
            if not onScreen or projected.Z <= 0 then continue end
            if distance < otherDistance - 0.01 or (math.abs(distance - otherDistance) <= 0.01
                and prompt.KeyboardKeyCode == Enum.KeyCode.E
                and (not selectedOther or selectedOther.KeyboardKeyCode ~= Enum.KeyCode.E)) then
                selectedOther, otherDistance = prompt, distance
            end
        end
    end
    if selectedAim and Occlusion.IsClear(ray.Origin, ray.Direction, aimEntry, player.Character) then
        return selectedAim
    end
    return selectedOther
end

local function updateCustomPrompt()
    local custom = SpatialRoot.IsCustom(player)
    local root = SpatialRoot.Get(player)
    local nextPrompt = if root then nearestCustomPrompt(root, not custom) else nil
    selectedCustom = nextPrompt
    local anchor = if nextPrompt then nextPrompt.Parent else nil
    local selectedSocket = if anchor and anchor:IsA("Attachment") then anchor :: Attachment else nil
    for socket in visible do
        if socket == selectedSocket or (not custom and nativeActive(socket)) then
            renderSocket(socket)
        else
            hideSocket(socket)
        end
    end
    if selectedSocket then renderSocket(selectedSocket) end
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
    -- authoritatively validates E/F actions and player life state.
    local elapsed = 0
    RunService.Heartbeat:Connect(function(dt)
        elapsed += dt
        if elapsed < 0.1 then return end
        elapsed = 0
        updateCustomPrompt()
    end)
    UserInputService.InputBegan:Connect(function(input, processed)
        if processed or UserInputService:GetFocusedTextBox() then return end
        local key = input.KeyCode.Name
        if key ~= "E" and key ~= "F" then return end
        local root = SpatialRoot.Get(player)
        if not root then return end
        -- Re-evaluate AIM at key press: a stale 10 Hz badge must not activate
        -- an interaction after the camera turns away or an obstacle appears.
        local selected = nearestCustomPrompt(root, not SpatialRoot.IsCustom(player))
        if not selected or not selected:IsDescendantOf(Workspace) then return end
        local name = selected:GetAttribute("Game1HouseSocketName")
        local definition = if typeof(name) == "string" then Contract.Get(name) else nil
        if not definition or (not SpatialRoot.IsCustom(player) and not definition.hoverRadius) then return end
        local matching: ProximityPrompt? = nil
        for prompt in prompts do
            if prompt.Parent == selected.Parent and prompt.Enabled and prompt.KeyboardKeyCode == input.KeyCode then
                matching = prompt
                break
            end
        end
        if not matching then return end
        local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
        local remote = folder and folder:FindFirstChild("HouseSocketInteract")
        local socket = matching.Parent
        if remote and remote:IsA("RemoteEvent") and socket and socket:IsA("Attachment") then
            remote:FireServer(socket, key)
        end
    end)
    ProximityPromptService.PromptShown:Connect(function(prompt)
        if SpatialRoot.IsCustom(player) then return end
        local socketName = prompt:GetAttribute("Game1HouseSocketName")
        local definition = if typeof(socketName) == "string" then Contract.Get(socketName) else nil
        if definition and definition.hoverRadius then return end
        if prompt.Name ~= "Game1HouseInteraction" and prompt.Name ~= "Game1HouseInteractionAlternate" then return end
        local socket = prompt.Parent
        if not socket or not socket:IsA("Attachment") then return end
        nativeShown[prompt] = true
        renderSocket(socket)
    end)
    ProximityPromptService.PromptHidden:Connect(function(prompt)
        if SpatialRoot.IsCustom(player) then return end
        nativeShown[prompt] = nil
        local socket = prompt.Parent
        if socket and socket:IsA("Attachment") and not nativeActive(socket) then
            hideSocket(socket)
        end
    end)
end

return table.freeze(Controller)
