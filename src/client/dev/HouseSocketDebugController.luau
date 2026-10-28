--!strict
-- Studio-only Test Loadout extension: per-socket interaction radii, visual
-- range previews and server-validated spawn teleport. No gameplay state owned.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local StudioDebugDock = require(script.Parent:WaitForChild("StudioDebugDock"))
local Contract = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("world"):WaitForChild("HouseSocketContract"))
local PromptController = require(script.Parent.Parent:WaitForChild("world"):WaitForChild("HouseSocketPromptController"))

local Debug = {}
local player = Players.LocalPlayer
local previews: {[Attachment]: Part} = {}
local visualize = false
local updateConnection: RBXScriptConnection? = nil
local MAX_PREVIEWS = 100
local tracked: {[Attachment]: boolean} = {}
local trackingStarted = false
local started = false
local togglePanel: (() -> ())? = nil
local COLORS = {bg = Color3.fromRGB(15, 20, 27), line = Color3.fromRGB(60, 74, 88),
    panel = Color3.fromRGB(25, 34, 44), text = Color3.fromRGB(238, 243, 246),
    muted = Color3.fromRGB(151, 167, 180), accent = Color3.fromRGB(76, 217, 184)}

local function control(parent: Instance, label: string, w: number, h: number): TextButton
    local b = Instance.new("TextButton")
    b.Size = UDim2.fromOffset(w, h)
    b.BackgroundColor3 = COLORS.panel
    b.TextColor3 = COLORS.text
    b.Text = label
    b.TextSize = 11
    b.Font = Enum.Font.GothamSemibold
    b.Parent = parent
    local c = Instance.new("UICorner"); c.CornerRadius = UDim.new(0, 6); c.Parent = b
    return b
end

local function label(parent: Instance, txt: string, w: number, h: number): TextLabel
    local t = Instance.new("TextLabel")
    t.Size = UDim2.fromOffset(w, h)
    t.Text = txt
    t.TextSize = 11
    t.Font = Enum.Font.Gotham
    t.TextColor3 = COLORS.text
    t.BackgroundTransparency = 1
    t.TextXAlignment = Enum.TextXAlignment.Left
    t.Parent = parent
    return t
end

local function clearPreview()
    if updateConnection then updateConnection:Disconnect(); updateConnection = nil end
    for socket, part in previews do part:Destroy(); previews[socket] = nil end
end

local function isManaged(socket: Attachment): boolean
    local ancestor: Instance? = socket.Parent
    while ancestor and ancestor ~= Workspace do
        if ancestor:IsA("Model") then
            if ancestor:GetAttribute("Game1RealEstateTemplate") ~= true
                and ancestor:GetAttribute("Game1RealEstateSlug") ~= nil then return true end
            -- In Studio an authored house copy may still carry a template tag.
            -- Match the server's preview policy by checking a real HouseRig.
            if RunService:IsStudio() and ancestor:FindFirstChild("HouseRig") ~= nil then
                return true
            end
        end
        ancestor = ancestor.Parent
    end
    return false
end

local function track(instance: Instance)
    if not instance:IsA("Attachment") or not Contract.Get(instance.Name) then return end
    if isManaged(instance) then tracked[instance] = true end
end

local function startTracking()
    if trackingStarted then return end
    trackingStarted = true
    for _, descendant in Workspace:GetDescendants() do track(descendant) end
    Workspace.DescendantAdded:Connect(track)
    Workspace.DescendantRemoving:Connect(function(instance)
        if instance:IsA("Attachment") then tracked[instance] = nil end
    end)
end

local function updatePreview()
    local count = 0
    local active: {[Attachment]: boolean} = {}
    for socket in tracked do
        if count >= MAX_PREVIEWS then break end
        local spec = Contract.Get(socket.Name)
        if spec and socket:IsDescendantOf(Workspace) and isManaged(socket) then
            active[socket] = true
            count += 1
            local part = previews[socket]
            if not part then
                part = Instance.new("Part")
                part.Name = "Game1SocketRadiusPreview"
                part.Shape = Enum.PartType.Ball
                part.Anchored = true
                part.CanCollide = false
                part.CanQuery = false
                part.CanTouch = false
                part.CastShadow = false
                part.Material = Enum.Material.Neon
                part.Transparency = 0.9
                part.Color = if spec.interact then COLORS.accent else COLORS.muted
                part.Parent = Workspace.CurrentCamera
                previews[socket] = part
            end
            local override = player:GetAttribute(Contract.RadiusAttribute(spec.name))
            local r = if typeof(override) == "number" then override else spec.radius
            part.Size = Vector3.new(r * 2, r * 2, r * 2)
            part.CFrame = if socket:IsA("Bone") then socket.TransformedWorldCFrame else socket.WorldCFrame
        end
    end
    for socket, part in previews do
        if not active[socket] then part:Destroy(); previews[socket] = nil end
    end
end

local function mountPanel(gui: ScreenGui)
    local opener = control(gui, "HS", 44, 44)
    opener.Position = StudioDebugDock.ButtonPosition("HS")
    local panel = Instance.new("Frame")
    panel.Name = "Game1HouseSocketDebug"
    local camera = Workspace.CurrentCamera
    local viewportHeight = if camera then camera.ViewportSize.Y else 550
    panel.Size = UDim2.fromOffset(390, math.min(455, math.max(220, viewportHeight - 92)))
    panel.Position = StudioDebugDock.WindowPosition("HS", 390)
    panel.BackgroundColor3 = COLORS.bg
    panel.Visible = false
    panel.ZIndex = 80
    panel.Parent = gui
    local corner = Instance.new("UICorner"); corner.CornerRadius = UDim.new(0, 10); corner.Parent = panel
    local border = Instance.new("UIStroke"); border.Color = COLORS.line; border.Parent = panel
    local title = label(panel, "HOUSE SOCKETS · STUDIO", 245, 30)
    title.Position = UDim2.fromOffset(12, 7)
    title.ZIndex = 81
    local close = control(panel, "×", 30, 27)
    close.Position = UDim2.fromOffset(348, 9)
    close.ZIndex = 81
    local previewButton = control(panel, "RANGES: OFF", 130, 26)
    previewButton.Position = UDim2.fromOffset(12, 42)
    previewButton.ZIndex = 81
    local refresh = control(panel, "REFRESH", 90, 26)
    refresh.Position = UDim2.fromOffset(156, 42)
    refresh.ZIndex = 81
    local info = label(panel, "", 365, 20)
    info.Position = UDim2.fromOffset(12, 74)
    info.TextColor3 = COLORS.muted
    info.TextTruncate = Enum.TextTruncate.AtEnd
    info.ZIndex = 81
    local scroll = Instance.new("ScrollingFrame")
    scroll.Size = UDim2.new(1, -24, 1, -114)
    scroll.Position = UDim2.fromOffset(12, 103)
    scroll.BackgroundTransparency = 1
    scroll.ScrollBarThickness = 4
    scroll.AutomaticCanvasSize = Enum.AutomaticSize.Y
    scroll.CanvasSize = UDim2.new()
    scroll.ZIndex = 81
    scroll.Parent = panel
    local layout = Instance.new("UIListLayout")
    layout.Padding = UDim.new(0, 6)
    layout.SortOrder = Enum.SortOrder.LayoutOrder
    layout.Parent = scroll
    -- Resolve remotes at the moment of interaction. A missing/late server
    -- remote must never stop the debug panel itself from appearing.
    local function invoke(remoteName: string, ...: any): any
        local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes")
        local remote = remotes and remotes:FindFirstChild(remoteName)
        if not remote or not remote:IsA("RemoteFunction") then
            return {ok = false, error = "Server debug service unavailable: " .. remoteName}
        end
        local ok, result = pcall(function(...) return remote:InvokeServer(...) end, ...)
        return if ok and typeof(result) == "table" then result else {ok = false, error = tostring(result)}
    end

    local function draw()
        for _, child in scroll:GetChildren() do
            if child:IsA("Frame") then child:Destroy() end
        end
        local result = invoke("GetTestHouseSockets")
        if not result.ok then info.Text = tostring(result.error); return end
        local missing = 0
        for index, row in result.sockets do
            local spec = Contract.Get(row.name)
            if not spec then continue end
            if not row.found then missing += 1 end
            local entry = Instance.new("Frame")
            entry.Size = UDim2.new(1, -6, 0, 51)
            entry.BackgroundColor3 = COLORS.panel
            entry.LayoutOrder = index
            entry.ZIndex = 82
            entry.Parent = scroll
            local c = Instance.new("UICorner"); c.CornerRadius = UDim.new(0, 7); c.Parent = entry
            local titleText = label(entry, (if row.found then "● " else "○ ") .. row.name, 340, 22)
            titleText.Position = UDim2.fromOffset(8, 2)
            titleText.TextSize = 10
            titleText.TextColor3 = if row.found then COLORS.accent else COLORS.muted
            titleText.ZIndex = 83
            local minus = control(entry, "−", 30, 23)
            minus.Position = UDim2.fromOffset(8, 26)
            minus.ZIndex = 83
            local valueLabel = label(entry, tostring(row.radius) .. " studs", 65, 23)
            valueLabel.Position = UDim2.fromOffset(46, 26)
            valueLabel.ZIndex = 83
            local plus = control(entry, "+", 30, 23)
            plus.Position = UDim2.fromOffset(119, 26)
            plus.ZIndex = 83
            local function set(delta: number)
                local current = tonumber(valueLabel.Text:match("[%d%.]+")) or spec.radius
                local response = invoke("SetTestHouseSocketRadius", row.name, current + delta)
                if not response.ok then info.Text = tostring(response.error); return end
                valueLabel.Text = tostring(response.radius) .. " studs"
                PromptController.SetRadius(row.name, response.radius)
                if visualize then updatePreview() end
            end
            minus.Activated:Connect(function() set(-1) end)
            plus.Activated:Connect(function() set(1) end)
            if spec.role == "spawn" then
                local tp = control(entry, "TP", 50, 23)
                tp.Position = UDim2.fromOffset(295, 26)
                tp.ZIndex = 83
                tp.Activated:Connect(function()
                    local response = invoke("TeleportTestHouseSpawn", row.name)
                    info.Text = if response.ok then "TP · " .. tostring(response.house) else tostring(response.error)
                end)
            end
        end
        local metrics = result.metrics
        if typeof(metrics) == "table" then
            info.Text = ("%d/%d types · %d homes · %d prompts · %d authored")
                :format(#result.sockets - missing, #result.sockets,
                    metrics.houses or 0, metrics.prompts or 0, metrics.authored or 0)
        else
            info.Text = tostring(#result.sockets - missing) .. "/" .. tostring(#result.sockets) .. " socket types present in placed houses"
        end
    end
    local function hide()
        panel.Visible = false
        visualize = false
        previewButton.Text = "RANGES: OFF"
        clearPreview()
    end
    togglePanel = function()
        if panel.Visible then
            hide()
            player:WaitForChild("PlayerGui"):SetAttribute("Game1DebugPanelOpen", "")
        else
            player:WaitForChild("PlayerGui"):SetAttribute("Game1DebugPanelOpen", "HS")
            panel.Visible = true
            draw()
        end
    end
    opener.Activated:Connect(function()
        if togglePanel then togglePanel() end
    end)
    player:WaitForChild("PlayerGui"):GetAttributeChangedSignal("Game1DebugPanelOpen"):Connect(function()
        if player.PlayerGui:GetAttribute("Game1DebugPanelOpen") ~= "HS" then hide() end
    end)
    close.Activated:Connect(function()
        hide()
        if player.PlayerGui:GetAttribute("Game1DebugPanelOpen") == "HS" then
            player.PlayerGui:SetAttribute("Game1DebugPanelOpen", "")
        end
    end)
    refresh.Activated:Connect(draw)
    previewButton.Activated:Connect(function()
        visualize = not visualize
        previewButton.Text = if visualize then "RANGES: ON" else "RANGES: OFF"
        clearPreview()
        if visualize then
            startTracking()
            updatePreview()
            local elapsed = 0
            updateConnection = RunService.Heartbeat:Connect(function(dt)
                elapsed += dt
                if elapsed >= 0.25 then elapsed = 0; updatePreview() end
            end)
        end
    end)
    gui.Destroying:Connect(clearPreview)
end

function Debug.Start()
    if started or not RunService:IsStudio() then return end
    started = true
    local gui = Instance.new("ScreenGui")
    gui.Name = "Game1HouseSocketDebugGui"
    gui.ResetOnSpawn = false
    gui.DisplayOrder = 40
    gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
    gui.Parent = player:WaitForChild("PlayerGui")
    mountPanel(gui)
    print("[game1][house-socket] Studio debug HS launcher ready")
end

-- A second entry point in the existing Test Loadout; only ONE panel owns state.
function Debug.AttachLauncher(body: Frame, y: number)
    if not RunService:IsStudio() then return end
    local opener = control(body, "HOUSE SOCKETS  ·  DEBUG", 288, 32)
    opener.Position = UDim2.fromOffset(0, y)
    opener.Activated:Connect(function()
        if togglePanel then togglePanel() else warn("[game1][house-socket] HS launcher not ready") end
    end)
end

return table.freeze(Debug)
