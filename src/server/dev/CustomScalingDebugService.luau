-- Studio-only transient clip scaling. Persistent authoring belongs to Asset Manager.
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")
local Scaling = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("animation"):WaitForChild("AnimationSpeedScaling"))

local Service = {}
local started = false

local function actors(): {Model}
    local result = {}
    for _, player in ipairs(Players:GetPlayers()) do
        if player.Character then table.insert(result, player.Character) end
    end
    for _, folderName in ipairs({"NPCs", "Monsters"}) do
        local folder = Workspace:FindFirstChild(folderName)
        if folder then
            for _, child in ipairs(folder:GetChildren()) do
                if child:IsA("Model") then table.insert(result, child) end
            end
        end
    end
    return result
end

function Service.Start()
    if started or not RunService:IsStudio() then return end
    started = true
    local folder = ReplicatedStorage:FindFirstChild("Game1CustomScalingDebug")
    if not folder then
        folder = Instance.new("Folder")
        folder.Name = "Game1CustomScalingDebug"
        folder.Parent = ReplicatedStorage
    end
    local apply = Instance.new("RemoteFunction")
    apply.Name = "Apply"
    apply.Parent = folder
    local refresh = Instance.new("RemoteEvent")
    refresh.Name = "Refresh"
    refresh.Parent = folder
    apply.OnServerInvoke = function(_player: Player, assetId: any, stat: any, units: any, clear: any)
        local id = Scaling.AssetId(assetId)
        if id == "" or not Scaling.Catalog()[id] then
            return {ok = false, error = "Animation ID is not in the published registry"}
        end
        local key = Scaling.CustomDebugPrefix .. id
        if clear == true then
            Workspace:SetAttribute(key, nil)
            Workspace:SetAttribute(key .. "_Stat", nil)
        else
            local number = tonumber(units)
            if (stat ~= "AttackSpeed" and stat ~= "RunSpeed") or not number
                or number ~= number or number < 0.001 or number > 1000 then
                return {ok = false, error = "Select RunSpeed/AttackSpeed and units 0.001..1000"}
            end
            Workspace:SetAttribute(key .. "_Stat", stat)
            Workspace:SetAttribute(key, number)
        end
        for _, model in ipairs(actors()) do
            Scaling.RefreshPlaying(model, id)
        end
        refresh:FireAllClients(id, Workspace:GetAttribute(key), Workspace:GetAttribute(key .. "_Stat"))
        return {ok = true, assetId = id, debugUnits = Workspace:GetAttribute(key)}
    end
end
return table.freeze(Service)
