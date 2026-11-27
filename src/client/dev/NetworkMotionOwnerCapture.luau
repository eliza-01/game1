-- DEV listener only. Capture the moving player's own root in the same window.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Dev = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("dev")
local Capture = require(Dev:WaitForChild("NetworkMotionCapture"))
local Owner = {}
local started = false
function Owner.Start()
    if started then return end
    started = true
    task.spawn(function()
        local folder = ReplicatedStorage:WaitForChild("Game1Remotes", 15)
        local event = folder and folder:WaitForChild("NetworkMotionDiagnostic", 15)
        if not event or not event:IsA("RemoteEvent") then return end
        local connection
        local function stop()
            if connection then connection:Disconnect(); connection = nil end
        end
        event.OnClientEvent:Connect(function(kind, id, startAt)
            if kind ~= "ownerStart" or connection then return end
            local capture = Capture.New(Players.LocalPlayer, startAt, true)
            if not capture then return end
            connection = RunService.RenderStepped:Connect(function()
                local done, reason = Capture.Step(capture, workspace:GetServerTimeNow())
                if done then
                    stop()
                    event:FireServer("owner", id, Capture.Finish(capture, reason))
                end
            end)
            local thisConnection = connection
            task.delay(13, function()
                if connection == thisConnection then stop() end
            end)
        end)
    end)
end
return table.freeze(Owner)
