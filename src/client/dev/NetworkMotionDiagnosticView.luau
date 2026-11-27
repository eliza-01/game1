-- On-demand diagnostics in the existing Camera debug panel (no new dock icon).
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local HttpService = game:GetService("HttpService")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Capture = require(Shared:WaitForChild("dev"):WaitForChild("NetworkMotionCapture"))
local Version = require(Shared:WaitForChild("RuntimeVersion"))
local View = {}
local player = Players.LocalPlayer
local TEXT = Color3.fromRGB(238,243,246)
local function button(parent, caption, x, y, w)
    local b = Instance.new("TextButton")
    b.Size = UDim2.fromOffset(w, 30); b.Position = UDim2.fromOffset(x,y)
    b.Text = caption; b.Font = Enum.Font.GothamSemibold; b.TextSize = 12
    b.TextColor3 = TEXT; b.BackgroundColor3 = Color3.fromRGB(40,52,65); b.BorderSizePixel = 0
    b.ZIndex = 92; b.Parent = parent
    local corner = Instance.new("UICorner"); corner.CornerRadius = UDim.new(0,6); corner.Parent = b
    return b
end
local function label(parent, y, h)
    local text = Instance.new("TextLabel")
    text.Size = UDim2.new(1,-24,0,h); text.Position = UDim2.fromOffset(12,y)
    text.BackgroundTransparency = 1; text.TextColor3 = TEXT; text.Font = Enum.Font.Code
    text.TextSize = 12; text.TextXAlignment = Enum.TextXAlignment.Left
    text.TextYAlignment = Enum.TextYAlignment.Top; text.TextWrapped = true
    text.ZIndex = 92; text.Parent = parent
    return text
end
local function line(title, channel)
    if not channel then return "" end
    return string.format("%s %.1f [%.1f–%.1f]", title, channel.mean, channel.p05, channel.p95)
end
local function describe(title, report)
    if not report then return title .. " · waiting" end
    return string.format("%s · %.1fs / %.0f Hz\n%s\n%s%s\nFrame p95/max %.1f/%.1f ms%s",
        title, report.seconds, report.fps, line("Position", report.physical), line("Velocity", report.velocity),
        report.render and "\n" .. line("Render", report.render) or "", report.frame.p95, report.frame.max,
        report.reason ~= "complete" and " · " .. report.reason or "")
end
function View.Mount(cameraPanel)
    local opener = button(cameraPanel, "Network motion", 177, 8, 132)
    opener.ZIndex = 86
    local panel = Instance.new("Frame")
    panel.Name = "NetworkMotionDiagnosticPanel"; panel.Size = UDim2.fromScale(1,1)
    panel.BackgroundColor3 = Color3.fromRGB(15,20,27); panel.BorderSizePixel = 0
    panel.ZIndex = 90; panel.Visible = false; panel.Parent = cameraPanel
    local heading = label(panel,12,22); heading.Text = "NETWORK MOTION · " .. Version.Version
    local close = button(panel,"×",320,8,30)
    local targetButton = button(panel,"Target",12,42,200)
    local start = button(panel,"Record 8s",220,42,130)
    local status = label(panel,80,42)
    local result = label(panel,116,324)
    local target, token, busy = nil, 0, false
    local connection, capture, clientReport, serverReport, ownerReport, ownerDone
    local eventConnection
    local function disconnect()
        if connection then connection:Disconnect(); connection = nil end
    end
    local function finishUI(message)
        disconnect(); busy = false; start.Text = "Record 8s"; status.Text = message
    end
    local function cancel()
        token += 1; capture = nil; clientReport = nil; serverReport = nil; ownerReport = nil; ownerDone = false
        if eventConnection then eventConnection:Disconnect(); eventConnection = nil end
        finishUI("Select target and record. Run straight at constant speed.")
    end
    local function choose(advance)
        local candidates = {}
        for _, candidate in ipairs(Players:GetPlayers()) do
            if Capture.Root(candidate) then table.insert(candidates,candidate) end
        end
        table.sort(candidates,function(a,b) return a.UserId < b.UserId end)
        local index = table.find(candidates,target)
        if advance and index then target = candidates[index % #candidates + 1]
        elseif not index then
            target = nil
            for _, candidate in ipairs(candidates) do if candidate ~= player then target = candidate; break end end
            target = target or candidates[1]
        end
        targetButton.Text = target and (target.Name .. (target == player and " · self" or " · remote")) or "No target"
    end
    local function updateReport()
        local selfTarget = target == player
        local ownerText = if selfTarget then "OWNER = CLIENT (self)"
            elseif ownerDone and not ownerReport then "OWNER · unavailable"
            else describe("OWNER",ownerReport)
        result.Text = "Speed studs/s · mean [p05–p95]\n" .. describe("CLIENT",clientReport) .. "\n\n" .. describe("SERVER",serverReport) .. "\n\n" .. ownerText
        if clientReport and serverReport and (selfTarget or ownerDone) then
            local report = {version = Version.Version, observer = player.Name, target = clientReport.target,
                client = clientReport, server = serverReport, owner = selfTarget and clientReport or ownerReport,
                ownerAvailable = selfTarget or ownerReport ~= nil}
            print("[NETMOTION] " .. HttpService:JSONEncode(report))
            finishUI("Complete · screenshot or [NETMOTION] in Output")
            if eventConnection then eventConnection:Disconnect(); eventConnection = nil end
        end
    end
    targetButton.Activated:Connect(function() if not busy then choose(true) end end)
    start.Activated:Connect(function()
        if busy then return end
        choose(false)
        if not target then status.Text = "No character ready"; return end
        local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
        local event = folder and folder:FindFirstChild("NetworkMotionDiagnostic")
        if not event or not event:IsA("RemoteEvent") then status.Text = "DEV diagnostic service unavailable"; return end
        cancel(); busy = true; start.Text = "Recording…"; status.Text = "Waiting for server…"; result.Text = ""
        local request = token
        local selected = target
        eventConnection = event.OnClientEvent:Connect(function(kind, replyToken, payload)
            if replyToken ~= request or token ~= request then return end
            if kind == "error" then cancel(); status.Text = tostring(payload); return end
            if kind == "start" and not capture then
                capture = Capture.New(selected,payload,true)
                if not capture then cancel(); status.Text = "Target root unavailable"; return end
                status.Text = "Start running now · capture begins in ~2s"
                connection = RunService.RenderStepped:Connect(function()
                    local now = workspace:GetServerTimeNow()
                    local done, reason = Capture.Step(capture,now)
                    if done then
                        disconnect(); clientReport = Capture.Finish(capture,reason); updateReport()
                    end
                end)
            elseif kind == "result" then
                serverReport = payload; updateReport()
            elseif kind == "owner" or kind == "ownerUnavailable" then
                ownerReport = if kind == "owner" then payload else nil
                ownerDone = true; updateReport()
            end
        end)
        event:FireServer(request,selected.UserId)
        task.delay(17,function()
            if token == request and busy then cancel(); status.Text = "Timed out / cooldown · retry" end
        end)
    end)
    opener.Activated:Connect(function()
        panel.Visible = true; cancel(); choose(false); result.Text = ""
    end)
    close.Activated:Connect(function() cancel(); panel.Visible = false end)
    cameraPanel:GetPropertyChangedSignal("Visible"):Connect(function()
        if not cameraPanel.Visible then cancel(); panel.Visible = false end
    end)
    cameraPanel.Destroying:Connect(cancel)
end
return table.freeze(View)
