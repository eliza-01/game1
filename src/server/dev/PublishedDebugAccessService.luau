-- Server-owned authorization for every admitted player when published debug is enabled.
local Players = game:GetService("Players")
local Access = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
    :WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local Service = {}
local started = false

local function authorize(player: Player)
    local allowed = Access.ServerEnabled()
    player:SetAttribute("Game1PublishedDebugAuthorized", allowed)
end

function Service.Start()
    if started or not Access.ServerEnabled() then return end
    started = true
    Players.PlayerAdded:Connect(authorize)
    for _, player in ipairs(Players:GetPlayers()) do task.spawn(authorize, player) end
end

return table.freeze(Service)
