-- Studio Play-only debug window. Changes affect the running simulation only.
local RunService = game:GetService("RunService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
local Scaling = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("animation"):WaitForChild("AnimationSpeedScaling"))
local StudioDebugDock = require(script.Parent:WaitForChild("StudioDebugDock"))
local Controller = {}
local palette = {
    background = Color3.fromRGB(16, 22, 31),
    input = Color3.fromRGB(31, 43, 55),
    text = Color3.fromRGB(241, 247, 249),
    muted = Color3.fromRGB(164, 184, 194),
    accent = Color3.fromRGB(65, 201, 172),
}

local function new(class: string, properties: any, parent: Instance): Instance
    local widget = Instance.new(class)
    for key, value in pairs(properties) do widget[key] = value end
    widget.Parent = parent
    return widget
end

local function caption(parent: Instance, value: string, y: number, height: number?): TextLabel
    return new("TextLabel", {
        BackgroundTransparency = 1, TextColor3 = palette.text, Text = value,
        Font = Enum.Font.Gotham, TextSize = 12, TextXAlignment = Enum.TextXAlignment.Left,
        TextYAlignment = Enum.TextYAlignment.Center,
        Position = UDim2.fromOffset(12, y), Size = UDim2.new(1, -24, 0, height or 22),
    }, parent) :: TextLabel
end

local function input(parent: Instance, y: number, placeholder: string): TextBox
    return new("TextBox", {
        BackgroundColor3 = palette.input, TextColor3 = palette.text, PlaceholderColor3 = palette.muted,
        PlaceholderText = placeholder, Text = "", BorderSizePixel = 0, TextSize = 13,
        TextXAlignment = Enum.TextXAlignment.Left, ClearTextOnFocus = false,
        Position = UDim2.fromOffset(12, y), Size = UDim2.new(1, -24, 0, 31),
        Font = Enum.Font.Gotham,
    }, parent) :: TextBox
end

local function button(parent: Instance, label: string, position: UDim2, size: UDim2): TextButton
    return new("TextButton", {
        BackgroundColor3 = palette.input, TextColor3 = palette.text, Text = label,
        TextSize = 12, Font = Enum.Font.GothamSemibold, BorderSizePixel = 0,
        Position = position, Size = size,
    }, parent) :: TextButton
end

local function refreshLocally(assetId: string)
    for _, player in ipairs(Players:GetPlayers()) do
        if player.Character then Scaling.RefreshPlaying(player.Character, assetId) end
    end
    for _, name in ipairs({"NPCs", "Monsters"}) do
        local folder = Workspace:FindFirstChild(name)
        if folder then
            for _, actor in ipairs(folder:GetChildren()) do
                if actor:IsA("Model") then Scaling.RefreshPlaying(actor, assetId) end
            end
        end
    end
end

function Controller.Start()
    if not RunService:IsStudio() then return end
    local player = Players.LocalPlayer
    if not player then return end
    local playerGui = player:WaitForChild("PlayerGui")
    local previous = playerGui:FindFirstChild("CustomScaling")
    if previous then previous:Destroy() end
    -- Build the debug UI immediately. Do not silently hide it while waiting
    -- for a server remote, and never use a fixed Y that may fall off-screen.
    local gui = new("ScreenGui", {Name = "CustomScaling", ResetOnSpawn = false, DisplayOrder = 135}, playerGui)
    local toggle = button(gui, "CS", StudioDebugDock.ButtonPosition("CS"), UDim2.fromOffset(44, 44))
    toggle.BackgroundColor3 = palette.accent
    local panel = new("Frame", {BackgroundColor3 = palette.background, BorderSizePixel = 0,
        Position = StudioDebugDock.WindowPosition("CS", 350), Size = UDim2.fromOffset(350, 395), Visible = false}, gui)
    caption(panel, "CustomScaling · Studio Play", 6, 28)
    caption(panel, "Temporary overrides, not saved to Asset Manager", 34, 18).TextColor3 = palette.muted
    local search = input(panel, 58, "Search animation / NPC / monster / ID")
    local results = new("ScrollingFrame", {BackgroundColor3 = palette.input, BorderSizePixel = 0,
        Position = UDim2.fromOffset(12, 94), Size = UDim2.new(1, -24, 0, 132),
        ScrollBarThickness = 4, CanvasSize = UDim2.fromOffset(0, 0)}, panel)
    local selected = caption(panel, "Select a published animation", 231, 20)
    selected.TextTruncate = Enum.TextTruncate.AtEnd
    local statButton = button(panel, "Stat: AttackSpeed", UDim2.fromOffset(12, 263), UDim2.fromOffset(158, 31))
    local units = input(panel, 300, "Stat units for +1% playback")
    local applyButton = button(panel, "Apply live", UDim2.fromOffset(12, 344), UDim2.fromOffset(156, 32))
    applyButton.BackgroundColor3 = palette.accent
    local resetButton = button(panel, "Reset live", UDim2.fromOffset(178, 344), UDim2.fromOffset(160, 32))
    local applyRemote: RemoteFunction? = nil
    local OPEN_ATTRIBUTE = "Game1DebugPanelOpen"
    local PANEL_ID = "CS"
    local function refreshPanelVisibility()
        local open = playerGui:GetAttribute(OPEN_ATTRIBUTE) == PANEL_ID
        panel.Visible = open
        toggle.Text = "CS"
        toggle.BackgroundColor3 = if open then palette.background else palette.accent
    end
    toggle.Activated:Connect(function()
        playerGui:SetAttribute(OPEN_ATTRIBUTE, if panel.Visible then "" else PANEL_ID)
    end)
    playerGui:GetAttributeChangedSignal(OPEN_ATTRIBUTE):Connect(refreshPanelVisibility)
    refreshPanelVisibility()

    -- Remote initialization is asynchronous so a missing server service still
    -- leaves a visible, diagnosable CS control instead of disappearing.
    task.spawn(function()
        local remote = ReplicatedStorage:WaitForChild("Game1CustomScalingDebug", 20)
        if not remote then
            selected.Text = "Server CustomScaling service unavailable"
            warn("[game1][custom-scaling] Studio server debug service was not found")
            return
        end
        local apply = remote:WaitForChild("Apply", 10)
        local refresh = remote:WaitForChild("Refresh", 10)
        if not apply or not refresh then
            selected.Text = "CustomScaling debug remotes incomplete"
            warn("[game1][custom-scaling] Apply/Refresh remotes missing")
            return
        end
        applyRemote = apply :: RemoteFunction
        local refreshRemote = refresh :: RemoteEvent
        refreshRemote.OnClientEvent:Connect(function(assetId, expectedUnits, expectedStat)
            task.spawn(function()
                local key = Scaling.CustomDebugPrefix .. tostring(assetId)
                local deadline = os.clock() + 1.5
                while os.clock() < deadline do
                    if Workspace:GetAttribute(key) == expectedUnits
                        and Workspace:GetAttribute(key .. "_Stat") == expectedStat then
                        break
                    end
                    RunService.Heartbeat:Wait()
                end
                refreshLocally(assetId)
            end)
        end)
        print("[game1][custom-scaling] Studio live controls ready")
    end)
    local rows = {}
    for id, entry in pairs(Scaling.Catalog()) do
        table.insert(rows, {id = id, label = tostring(entry.label), channel = tostring(entry.channel)})
    end
    table.sort(rows, function(a, b) return a.label < b.label end)
    local selectedId: string? = nil
    local stat = "AttackSpeed"
    local function draw()
        for _, child in ipairs(results:GetChildren()) do child:Destroy() end
        local term = string.lower(search.Text)
        local y = 0
        local count = 0
        for _, row in ipairs(rows) do
            if term == "" or string.find(string.lower(row.label .. " " .. row.id), term, 1, true) then
                local option = button(results, row.label, UDim2.fromOffset(2, y), UDim2.new(1, -8, 0, 25))
                option.TextSize = 10
                option.TextTruncate = Enum.TextTruncate.AtEnd
                option.MouseButton1Click:Connect(function()
                    selectedId = row.id
                    selected.Text = row.label
                    local override = Scaling.RuleForAnimation(player.Character or Workspace, row.channel, row.id)
                    stat = override and override.stat or (if row.channel == "run" or row.channel == "walk" then "RunSpeed" else "AttackSpeed")
                    statButton.Text = "Stat: " .. stat
                    units.Text = tostring(override and override.unitsPerPercent or 1)
                end)
                y += 27
                count += 1
                if count >= 40 then break end
            end
        end
        results.CanvasSize = UDim2.fromOffset(0, y)
    end
    search:GetPropertyChangedSignal("Text"):Connect(draw)
    draw()
    print("[game1][custom-scaling] CS button visible · catalog entries:", #rows)
    statButton.MouseButton1Click:Connect(function()
        stat = if stat == "AttackSpeed" then "RunSpeed" else "AttackSpeed"
        statButton.Text = "Stat: " .. stat
    end)
    local function update(clear: boolean)
        if not selectedId then selected.Text = "Choose an animation first"; return end
        if not applyRemote then
            selected.Text = "Waiting for Studio server CustomScaling service"
            return
        end
        local success, result = pcall(function()
            return applyRemote:InvokeServer(selectedId, stat, tonumber(units.Text), clear)
        end)
        if not success or type(result) ~= "table" or result.ok ~= true then
            selected.Text = "Error: " .. tostring(if success and type(result) == "table" then result.error else result)
        else
            refreshLocally(selectedId)
            local metadata = Scaling.Catalog()[selectedId]
            selected.Text = (metadata and metadata.label or selectedId) .. (if clear then " · reset" else " · live")
        end
    end
    applyButton.MouseButton1Click:Connect(function() update(false) end)
    resetButton.MouseButton1Click:Connect(function() update(true) end)
end
return Controller
