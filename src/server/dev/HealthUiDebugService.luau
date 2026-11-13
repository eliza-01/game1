--!strict
-- Studio-only transport of client HP appearance drafts; gameplay state is untouched.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local PublishedDebugAccess = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared"):WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Options = require(Shared:WaitForChild("GameOptions"))

local Service = {}
local started = false
local cooldown: {[Player]: number} = {}
local limits = {
    width={60,560}, height={6,60}, border={0,8},
    textSize={8,36}, nameSize={8,40}, levelSize={8,40},
    offsetStuds={0,12}, top={0,160}, maxDistanceStuds={20,800},
}

local function validated(device: any, data: any): {[string]: any}?
    if device ~= "desktop" and device ~= "mobile" or type(data) ~= "table" then return nil end
    local expected = Options.HealthUiSettings(device)
    local result = {}
    for group, fields in pairs(expected) do
        if type(data[group]) ~= "table" then return nil end
        result[group] = {}
        for key, _ in pairs(fields) do
            local value = data[group][key]
            if key == "enabled" then
                if type(value) ~= "boolean" then return nil end
            elseif group == "colors" then
                if type(value) ~= "string" or not value:match("^#%x%x%x%x%x%x$") then return nil end
            else
                local range = limits[key]
                if not range or type(value) ~= "number" or value ~= value
                    or value < range[1] or value > range[2] then return nil end
            end
            result[group][key] = value
        end
        for key in pairs(data[group]) do
            if fields[key] == nil then return nil end
        end
    end
    for key in pairs(data) do
        if expected[key] == nil then return nil end
    end
    return result
end

function Service.Start()
    if started or not PublishedDebugAccess.ServerEnabled() then return end
    started = true
    local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if not remotes then
        remotes = Instance.new("Folder")
        remotes.Name = "Game1Remotes"
        remotes.Parent = ReplicatedStorage
    end
    local remote = remotes:FindFirstChild("HealthUiDebugChanged")
    if not remote then
        remote = Instance.new("RemoteEvent")
        remote.Name = "HealthUiDebugChanged"
        remote.Parent = remotes
    end
    if not remote:IsA("RemoteEvent") then return end
    local folder = Instance.new("Folder")
    folder.Name = "Game1HealthUiDebug"
    folder.Parent = ReplicatedStorage
    remote.OnServerEvent:Connect(function(player: Player, request: any)
    if not PublishedDebugAccess.ServerAllowed(player) then return end
        if type(request) ~= "table" then return end
        local now = os.clock()
        if now - (cooldown[player] or -100) < 0.12 then return end
        local checked = validated(request.device, request.settings)
        if not checked then return end
        cooldown[player] = now
        folder:SetAttribute("Payload", HttpService:JSONEncode({device=request.device, settings=checked}))
    end)
    Players.PlayerRemoving:Connect(function(player) cooldown[player] = nil end)
end

return table.freeze(Service)
