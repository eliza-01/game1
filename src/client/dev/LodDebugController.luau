-- Authorized Studio / published DEV only. No collection until Start is pressed.
local Players = game:GetService("Players")
local HttpService = game:GetService("HttpService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Access = require(Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local Dock = require(script.Parent:WaitForChild("StudioDebugDock"))
local Streamer = require(script.Parent.Parent:WaitForChild("world"):WaitForChild("LocationWorldStreamer"))
local Controller = {}
local started = false

local function make(parent, class, fields)
    local obj = Instance.new(class)
    for key, value in pairs(fields) do obj[key] = value end
    obj.Parent = parent
    return obj
end
local function button(parent, name, size, position)
    local obj = make(parent, "TextButton", {Text=name, Size=size, Position=position,
        BackgroundColor3=Color3.fromRGB(32,44,56), TextColor3=Color3.fromRGB(240,247,250),
        Font=Enum.Font.GothamSemibold, TextSize=13, BorderSizePixel=0})
    make(obj,"UICorner",{CornerRadius=UDim.new(0,6)})
    return obj
end
local function reportText(report)
    local lines = {string.format("Capture %.1f s | snapshot %s", report.seconds, report.gauges.snapshot),
        "Heartbeat interval (ms; not CPU)", string.format("p50 %.2f | p95 %.2f | p99 %.2f | max %.2f", report.heartbeatMs.p50, report.heartbeatMs.p95, report.heartbeatMs.p99, report.heartbeatMs.max),
        string.format("Frames %d / sampled %d", report.heartbeatMs.count, report.heartbeatMs.sampled),
        string.format("LOD callback (ms) p50 %.2f | p95 %.2f | p99 %.2f", report.callbackElapsedMs.p50, report.callbackElapsedMs.p95, report.callbackElapsedMs.p99),
        string.format("Queue residence (ms) p95 %.2f | n=%d", report.queueResidenceMs.p95, report.queueResidenceMs.count),
        string.format("Desired to actual (ms) p95 %.2f | n=%d", report.desiredToActualMs.p95, report.desiredToActualMs.count)}
    for _, group in ipairs({{"END",report.gauges},{"COUNTERS",report.counters},{"PEAKS",report.peaks}}) do
        lines[#lines+1] = "\n" .. group[1]
        local keys = {}
        for key in pairs(group[2]) do keys[#keys+1] = key end
        table.sort(keys)
        for _, key in ipairs(keys) do
            local value = group[2][key]
            lines[#lines+1] = key .. ": " .. (if type(value)=="number" then string.format("%.2f",value) else tostring(value))
        end
    end
    return table.concat(lines,"\n")
end

function Controller.Start()
    if started or not Access.ClientAllowed() then return end
    started = true
    local playerGui = Players.LocalPlayer:WaitForChild("PlayerGui")
    local screen = make(playerGui,"ScreenGui",{
        Name="Game1LodDiagnostics", ResetOnSpawn=false})
    local launcher = button(screen,"LD",UDim2.fromOffset(44,44),Dock.ButtonPosition("LD"))
    local panel = make(screen,"Frame",{Visible=false, Size=UDim2.fromOffset(350,390),
        BackgroundColor3=Color3.fromRGB(17,23,31), BorderSizePixel=0})
    make(panel,"UICorner",{CornerRadius=UDim.new(0,8)})
    local toggle = button(panel,"Start capture",UDim2.new(1,-16,0,36),UDim2.fromOffset(8,8))
    local scroll = make(panel,"ScrollingFrame",{Position=UDim2.fromOffset(8,52),Size=UDim2.new(1,-16,1,-60),
        BackgroundTransparency=1, BorderSizePixel=0, ScrollBarThickness=5,
        CanvasSize=UDim2.fromOffset(0,0), AutomaticCanvasSize=Enum.AutomaticSize.Y})
    local text = make(scroll,"TextLabel",{Size=UDim2.new(1,-8,0,0),AutomaticSize=Enum.AutomaticSize.Y,
        BackgroundTransparency=1,TextColor3=Color3.fromRGB(240,247,250),Font=Enum.Font.Code,TextSize=13,
        TextWrapped=true,TextXAlignment=Enum.TextXAlignment.Left,TextYAlignment=Enum.TextYAlignment.Top,
        Text="Runtime LOD · start, close panel, run scenario, reopen and stop. Results are local; JSON in client Output."})
    local recording = false
    local function syncPanel()
        panel.Visible = playerGui:GetAttribute("Game1DebugPanelOpen") == "LD"
    end
    launcher.Activated:Connect(function()
        playerGui:SetAttribute("Game1DebugPanelOpen", if panel.Visible then "" else "LD")
    end)
    playerGui:GetAttributeChangedSignal("Game1DebugPanelOpen"):Connect(syncPanel)
    syncPanel()
    toggle.Activated:Connect(function()
        if recording then
            recording = false
            toggle.Text = "Start capture"
            local report = Streamer.FinishDiagnostics()
            if not report then text.Text = "Capture no longer active"; return end
            text.Text = reportText(report)
            print("[game1][LOD][capture] " .. HttpService:JSONEncode(report))
        else
            local ok, reason = Streamer.StartDiagnostics()
            if not ok then text.Text = tostring(reason); return end
            recording = true
            toggle.Text = "Stop capture"
            text.Text = "Recording. Close this panel to run the scenario. Reopen and stop to view results."
        end
    end)
    Dock.Bind("LD",launcher,panel,350,true,390)
end
return table.freeze(Controller)
