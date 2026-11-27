-- DEV-only on-demand synchronized read-only measurement; no gameplay authority.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Dev = Shared:WaitForChild("dev")
local Access = require(Dev:WaitForChild("PublishedDebugAccess"))
local Capture = require(Dev:WaitForChild("NetworkMotionCapture"))
local Statistics = require(Dev:WaitForChild("NetworkMotionStatistics"))
local Service = {}
local started = false
local active = {}
local last = {}
local connection
local serial = 0
local LIMIT = 2
local COOLDOWN = 12
function Service.Start()
    if started or not Access.ServerEnabled() then return end
    started = true
    local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if not folder then folder = Instance.new("Folder"); folder.Name = "Game1Remotes"; folder.Parent = ReplicatedStorage end
    local event = Instance.new("RemoteEvent")
    event.Name = "NetworkMotionDiagnostic"
    event.Parent = folder
    local function stopIfIdle()
        if not next(active) and connection then connection:Disconnect(); connection = nil end
    end
    local function tick()
        local now = workspace:GetServerTimeNow()
        for player, session in pairs(active) do
            if not session.serverDone then
                local done, reason = Capture.Step(session.capture, now)
                if done then
                    session.serverDone = true
                    if player.Parent == Players and Access.ServerAllowed(player) then
                        event:FireClient(player, "result", session.token, Capture.Finish(session.capture, reason))
                    end
                end
            end
            if session.serverDone and (not session.waitOwner or now >= session.capture.endAt + 2) then
                active[player] = nil
                if session.waitOwner and player.Parent == Players and Access.ServerAllowed(player) then
                    event:FireClient(player, "ownerUnavailable", session.token)
                end
            end
        end
        stopIfIdle()
    end
    event.OnServerEvent:Connect(function(player, token, userId, report)
        if not Access.ServerAllowed(player) then return end
        if token == "owner" then
            for requester, session in pairs(active) do
                if session.waitOwner and session.ownerId == userId and session.capture.player == player
                    and workspace:GetServerTimeNow() >= session.capture.endAt - 0.5 then
                    local clean = Statistics.ValidateOwner(report, session.capture.startAt)
                    session.waitOwner = false
                    if requester.Parent == Players and Access.ServerAllowed(requester) then
                        if clean then event:FireClient(requester, "owner", session.token, clean)
                        else event:FireClient(requester, "ownerUnavailable", session.token) end
                    end
                    break
                end
            end
            return
        end
        if type(token) ~= "number" or token ~= math.floor(token) or token < 1 or token > 1000000000 then return end
        if type(userId) ~= "number" or userId ~= math.floor(userId) or math.abs(userId) > 1e15 then return end
        local now = workspace:GetServerTimeNow()
        if now - (last[player] or -100) < COOLDOWN then return end
        last[player] = now
        local count = 0
        for _ in pairs(active) do count += 1 end
        local target = Players:GetPlayerByUserId(userId)
        local ownRoot = Capture.Root(player)
        local targetRoot = target and Capture.Root(target)
        if active[player] or count >= LIMIT or not ownRoot or not targetRoot
            or (targetRoot.Position - ownRoot.Position).Magnitude > 160 then
            event:FireClient(player, "error", token, "Target unavailable / busy / outside 160 studs")
            return
        end
        local startAt = now + 2.5
        local capture = Capture.New(target, startAt, false)
        if not capture then event:FireClient(player, "error", token, "Target root unavailable"); return end
        -- At most one simultaneous recording for any target (including owner capture).
        for _, session in pairs(active) do
            if session.capture.player == target then
                event:FireClient(player, "error", token, "Target already being recorded")
                return
            end
        end
        serial += 1
        local waitOwner = target ~= player and Access.ServerAllowed(target)
        active[player] = {capture = capture, token = token, waitOwner = waitOwner, ownerId = serial}
        if not connection then connection = RunService.Heartbeat:Connect(tick) end
        event:FireClient(player, "start", token, startAt)
        if waitOwner then event:FireClient(target, "ownerStart", serial, startAt)
        elseif target ~= player then event:FireClient(player, "ownerUnavailable", token) end
    end)
    Players.PlayerRemoving:Connect(function(player)
        active[player] = nil; last[player] = nil
        for requester, session in pairs(active) do
            if session.capture.player == player then
                active[requester] = nil
                if requester.Parent == Players then event:FireClient(requester, "error", session.token, "Target left") end
            end
        end
        stopIfIdle()
    end)
end
return table.freeze(Service)
