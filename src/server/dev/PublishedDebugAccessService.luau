-- Server-owned Roblox creator authorization for published debug tools.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Access = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
    :WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local Service = {}
local started = false

local function isCreator(player: Player): boolean
    if game.CreatorType == Enum.CreatorType.User then
        return player.UserId == game.CreatorId
    end
    if game.CreatorType == Enum.CreatorType.Group and game.CreatorId > 0 then
        local ok, rank = pcall(function()
            return player:GetRankInGroup(game.CreatorId)
        end)
        return ok and rank >= 200 -- group admin/developer role; no ordinary group members
    end
    return false
end

local function authorize(player: Player)
    local allowed = RunService:IsStudio() or (Access.ServerEnabled() and isCreator(player))
    player:SetAttribute("Game1PublishedDebugAuthorized", allowed)
end

function Service.Start()
    if started then return end
    started = true
    Players.PlayerAdded:Connect(authorize)
    for _, player in ipairs(Players:GetPlayers()) do task.spawn(authorize, player) end
end

return table.freeze(Service)
