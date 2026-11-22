--!strict
-- One compact, consistent prompt for every authored house interaction.
-- The server owns prompt/action state; client groups E/F into one badge.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")
local TweenService = game:GetService("TweenService")
local CameraController = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("CameraController"))

local MobileLayout = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("mobile"):WaitForChild("MobileLayout"))

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Contract = require(Shared:WaitForChild("world"):WaitForChild("HouseSocketContract"))
local Aim = require(Shared:WaitForChild("world"):WaitForChild("HouseSocketAimPolicy"))
local FireplaceConfig = require(Shared:WaitForChild("world"):WaitForChild("FireplaceMechanicsConfig"))
local Occlusion = require(script.Parent:WaitForChild("HouseSocketAimOcclusion"))
local SpatialRoot = require(Shared:WaitForChild("character"):WaitForChild("CharacterSpatialRoot"))
local player = Players.LocalPlayer
local Controller = {}
local started = false
local prompts: {[ProximityPrompt]: RBXScriptConnection} = {}
-- One panel per selected socket: screen-right desktop dock / mobile thumb dock.
local visible: {[Attachment]: LayerCollector} = {}
local visibleSignature: {[Attachment]: string} = {}

-- Campfire interaction is a separate Location-domain contract; the House
-- registry must never treat fire_socket as a House socket.
local CAMPFIRE_DEFINITION = {
    name = "fire_socket", interact = true,
    radius = FireplaceConfig.CampfireInteractionRadius,
    hoverRadius = FireplaceConfig.CampfireAimRadius,
}
local function definitionFor(prompt: ProximityPrompt): any?
    if prompt:GetAttribute("Game1SocketDomain") == "campfire" then
        return if prompt:GetAttribute("Game1SocketName") == "fire_socket" then CAMPFIRE_DEFINITION else nil
    end
    local name = prompt:GetAttribute("Game1HouseSocketName")
    return if typeof(name) == "string" then Contract.Get(name) else nil
end

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
    local definition = definitionFor(instance)
    if not definition then return end
    local name = definition.name
    local prompt: ProximityPrompt = instance
    prompt.MaxActivationDistance = if definition == CAMPFIRE_DEFINITION then 0 else clientNativeDistance(name)
    prompts[prompt] = prompt.AncestryChanged:Connect(function()
        if not prompt:IsDescendantOf(Workspace) then
            local connection = prompts[prompt]
            if connection then connection:Disconnect() end
            prompts[prompt] = nil
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

local RESOURCE_ICONS = {
    wood = "🪵",
    carrot = "🥕",
    onion = "🧅",
    potato = "🥔",
}

local function showFloatingSpend(layer: ScreenGui, items: {any})
    local host = layer:FindFirstChild("SpendHost")
    if not host or not host:IsA("Frame") then return end
    for index, item in ipairs(items) do
        local label = Instance.new("TextLabel")
        label.AnchorPoint = Vector2.new(0.5, 1)
        label.Position = UDim2.new(0.5, 0, 0.78, -(index - 1) * 28)
        label.Size = UDim2.fromOffset(240, 24)
        label.BackgroundTransparency = 1
        label.TextColor3 = Color3.fromRGB(244, 246, 249)
        label.TextStrokeTransparency = 0.55
        label.Font = Enum.Font.GothamBold
        label.TextSize = 18
        local icon = RESOURCE_ICONS[tostring(item.icon or "")] or "•"
        local amount = tonumber(item.amount) or 0
        local amountText = if amount > 0 then "+" .. tostring(amount) else tostring(amount)
        label.Text = string.format("%s  %s  %s", icon, amountText, tostring(item.label or ""))
        label.Parent = host
        local tween = TweenService:Create(label, TweenInfo.new(0.9, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
            Position = label.Position - UDim2.fromOffset(0, 34),
            TextTransparency = 1,
            TextStrokeTransparency = 1,
        })
        tween:Play()
        tween.Completed:Connect(function() label:Destroy() end)
    end
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
    local parts = {if keyOwned() then "own" else "lost", if SpatialRoot.IsCustom(player) then "custom" else "native"}
    for _, prompt in actions do
        table.insert(parts, prompt.KeyboardKeyCode.Name .. "=" .. prompt.ActionText)
    end
    return table.concat(parts, "|")
end

-- Both keyboard shortcuts and mobile action buttons use the same server-owned
-- socket contract. The server checks distance, offered action and cooldown.
local function requestAction(prompt: ProximityPrompt)
    if not prompt.Enabled or not prompt:IsDescendantOf(Workspace) then return end
    local socket = prompt.Parent
    if not socket or not socket:IsA("Attachment") then return end
    local key = prompt.KeyboardKeyCode.Name
    if key ~= "E" and key ~= "F" then return end
    local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
    local remoteName = if prompt:GetAttribute("Game1SocketDomain") == "campfire"
        then "CampfireSocketInteract" else "HouseSocketInteract"
    local remote = folder and folder:FindFirstChild(remoteName)
    if remote and remote:IsA("RemoteEvent") then
        remote:FireServer(socket, key)
    end
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
    local cursor = CameraController.CursorPoint()
    local viewport = camera.ViewportSize
    local ray = camera:ViewportPointToRay(viewport.X * cursor.X, viewport.Y * cursor.Y)
    local selectedAim: ProximityPrompt? = nil
    local aimEntry = math.huge
    local selectedOther: ProximityPrompt? = nil
    local otherDistance = math.huge
    for prompt in prompts do
        if not prompt.Enabled or not prompt:IsDescendantOf(Workspace) then continue end
        local socket = prompt.Parent
        if not socket or not socket:IsA("Attachment") then continue end
        local definition = definitionFor(prompt)
        if not definition or not definition.interact then continue end
        local name = definition.name
        local frame = if socket:IsA("Bone") then socket.TransformedWorldCFrame else socket.WorldCFrame
        local distance = (frame.Position - root.Position).Magnitude
        -- USE always uses the character root, not the camera.
        local maxDistance = if definition == CAMPFIRE_DEFINITION then definition.radius else radius(name)
        if distance > maxDistance then continue end
        if definition.hoverRadius then
            local aimRadius = if definition == CAMPFIRE_DEFINITION then definition.hoverRadius else hoverRadius(name)
            local hit = Aim.RaySphereEntry(ray.Origin, ray.Direction, frame.Position, aimRadius)
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

local function makeGui(socket: Attachment, actions: {ProximityPrompt}): LayerCollector
    local touch = UserInputService.TouchEnabled
    -- One input layout for desktop and mobile. Unlike the old BillboardGui,
    -- this never overlaps the world reticle/camera at the socket position.
    local gui = Instance.new("ScreenGui")
    gui.Name = "Game1HousePrompt"
    gui.ScreenInsets = Enum.ScreenInsets.CoreUISafeInsets
    gui.SafeAreaCompatibility = Enum.SafeAreaCompatibility.None
    gui.DisplayOrder = 16
    gui.ResetOnSpawn = false
    gui.Parent = player:WaitForChild("PlayerGui")
    local panelHeight = 12 + #actions * (if touch then 52 else 44)
    local background = Instance.new("Frame")
    background.Name = "Panel"
    background.BackgroundColor3 = Color3.fromRGB(18, 24, 31)
    background.BackgroundTransparency = 0.06
    background.Parent = gui
    if touch then
        local function layout()
            local bounds = MobileLayout.Context(gui.AbsoluteSize.X, gui.AbsoluteSize.Y, panelHeight)
            background.AnchorPoint = Vector2.new(1, 1)
            background.Size = UDim2.fromOffset(bounds.width, panelHeight)
            background.Position = UDim2.new(1, -bounds.x, 1, -bounds.y)
        end
        gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(layout)
        layout()
    else
        background.AnchorPoint = Vector2.new(1, 0.5)
        background.Size = UDim2.fromOffset(272, panelHeight)
        background.Position = UDim2.new(1, -22, 0.5, 0)
    end
    rounded(background, 11)
    local stroke = Instance.new("UIStroke")
    stroke.Color = Color3.fromRGB(75, 91, 104)
    stroke.Thickness = 1
    stroke.Transparency = 0.12
    stroke.Parent = background
    for index, prompt in ipairs(actions) do
        local y = 6 + (index - 1) * (if touch then 52 else 44)
        local action = Instance.new("TextButton")
        action.Name = "InteractionAction_" .. prompt.KeyboardKeyCode.Name
        action.Position = UDim2.fromOffset(6, y)
        action.Size = UDim2.new(1, -12, 0, if touch then 46 else 38)
        action.BackgroundColor3 = Color3.fromRGB(37, 51, 62)
        action.TextColor3 = Color3.fromRGB(244, 246, 249)
        action.Font = Enum.Font.GothamSemibold
        action.TextSize = 14
        action.TextWrapped = true
        action.AutoButtonColor = true
        action.Active = true
        action.RichText = true
        action.Text = if touch then actionLabel(prompt.ActionText)
            else ("[" .. prompt.KeyboardKeyCode.Name .. "]   " .. actionLabel(prompt.ActionText))
        action.Parent = background
        rounded(action, 8)
        action.Activated:Connect(function()
            if not prompt.Enabled or not prompt:IsDescendantOf(Workspace) then return end
            local root = SpatialRoot.Get(player)
            local selected = if root then nearestCustomPrompt(root, false) else nil
            if not selected or selected.Parent ~= socket then return end
            requestAction(prompt)
        end)
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

local function updateCustomPrompt()
    local custom = SpatialRoot.IsCustom(player)
    local root = SpatialRoot.Get(player)
    local alive = not custom or (player.Character and player.Character:GetAttribute("LifeState") == "Alive")
    local nextPrompt = if root and alive then nearestCustomPrompt(root, false) else nil
    local anchor = if nextPrompt then nextPrompt.Parent else nil
    local selectedSocket = if anchor and anchor:IsA("Attachment") then anchor :: Attachment else nil
    for socket in pairs(visible) do
        if socket == selectedSocket then renderSocket(socket) else hideSocket(socket) end
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
        -- Decorative notification surface. UiInputGuard must not treat its
        -- full-screen transparent host as a world-input blocker (RMB orbit).
        gui:SetAttribute("WorldInputPassthrough", true)
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
        local spendHost = Instance.new("Frame")
        spendHost.Name = "SpendHost"
        spendHost.BackgroundTransparency = 1
        spendHost.Active = false
        spendHost.Size = UDim2.fromScale(1, 1)
        spendHost.Parent = gui
        local revision = 0
        local function showMessage(text: string)
            revision += 1
            local thisRevision = revision
            message.Text = text
            message.Visible = true
            task.delay(2.7, function()
                if revision == thisRevision then message.Visible = false end
            end)
        end
        feedbackRemote.OnClientEvent:Connect(function(payload)
            if typeof(payload) == "string" then
                showMessage(payload)
                return
            end
            if typeof(payload) ~= "table" then return end
            if payload.kind == "toast" and typeof(payload.text) == "string" then
                showMessage(payload.text)
            elseif payload.kind == "resource" and typeof(payload.items) == "table" then
                showFloatingSpend(gui, payload.items)
            end
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
        local definition = definitionFor(selected)
        if not definition or (not SpatialRoot.IsCustom(player) and not definition.hoverRadius) then return end
        local matching: ProximityPrompt? = nil
        for prompt in prompts do
            if prompt.Parent == selected.Parent and prompt.Enabled and prompt.KeyboardKeyCode == input.KeyCode then
                matching = prompt
                break
            end
        end
        if not matching then return end
        requestAction(matching)
    end)
    -- Native keyboard ProximityPrompt.Triggered remains connected on the
    -- server; the custom dock owns only presentation and direct-click actions.

end

return table.freeze(Controller)
