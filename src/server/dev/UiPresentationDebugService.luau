--!strict
-- Studio-only transport for live UI layout drafts. No gameplay mutation.
-- The local Studio plugin forwards this attribute to OptionsStore; saving is
-- exclusively a Control Center action.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local HttpService = game:GetService("HttpService")
local Access = require(ReplicatedStorage:WaitForChild("Game1Shared")
    :WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local Contract = require(ReplicatedStorage:WaitForChild("Game1Shared")
    :WaitForChild("world"):WaitForChild("UiPresentationContract"))

local Service = {}
local started = false
local lastSent: {[Player]: number} = {}

function Service.Start()
    if started or not Access.ServerEnabled() then return end
    started = true
    local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if not remotes then
        remotes = Instance.new("Folder")
        remotes.Name = "Game1Remotes"
        remotes.Parent = ReplicatedStorage
    end
    local remote = remotes:FindFirstChild("UiPresentationDebugChanged")
    if not remote then
        remote = Instance.new("RemoteEvent")
        remote.Name = "UiPresentationDebugChanged"
        remote.Parent = remotes
    end
    if not remote:IsA("RemoteEvent") then return end
    local folder = ReplicatedStorage:FindFirstChild("Game1UiPresentationDebug")
    if not folder then
        folder = Instance.new("Folder")
        folder.Name = "Game1UiPresentationDebug"
        folder.Parent = ReplicatedStorage
    end
    if not folder:IsA("Folder") then return end

    remote.OnServerEvent:Connect(function(player: Player, input: any)
        if not Access.ServerAllowed(player) or type(input) ~= "table" then return end
        if input.device ~= "desktop" and input.device ~= "mobile" then return end
        local now = os.clock()
        if now - (lastSent[player] or -100) < 0.12 then return end
        local profile = Contract.Validate(input.device, input.settings)
        if not profile then return end
        lastSent[player] = now
        local payload = HttpService:JSONEncode({device=input.device, settings=profile})
        if #payload <= 8000 then
            folder:SetAttribute("Payload", payload)
            folder:SetAttribute("ChangedBy", player.UserId)
        end
    end)
    Players.PlayerRemoving:Connect(function(player)
        lastSent[player] = nil
    end)
end

return table.freeze(Service)
