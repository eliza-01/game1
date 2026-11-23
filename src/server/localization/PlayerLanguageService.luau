--!strict
-- Optional per-player preference. Never blocks character spawning/combat when
-- DataStore is unavailable (e.g. Studio without API access).
local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Contract = require(Shared:WaitForChild("localization"):WaitForChild("LanguageContract"))

local Service = {}
local started = false
local lastRequest: {[Player]: number} = {}
local selectedDuringLoad: {[Player]: boolean} = {}
local store = DataStoreService:GetDataStore("Game1PlayerLanguage_v1")
local ATTRIBUTE = "Game1LanguageChoice"
local READY = "Game1LanguageReady"

local function keyFor(player: Player): string
    return "u:" .. tostring(player.UserId)
end

local function load(player: Player)
    local ok, value = pcall(function()
        return store:GetAsync(keyFor(player))
    end)
    if player.Parent ~= Players then return end
    if not selectedDuringLoad[player] and ok and Contract.IsSupported(value) then
        player:SetAttribute(ATTRIBUTE, value)
    end
    if not ok then
        warn("[game1][language] preference load unavailable:", tostring(value))
    end
    player:SetAttribute(READY, true)
end

local function save(player: Player, value: any)
    if not Contract.IsSupported(value) then
        return {ok = false, error = "unsupported_locale"}
    end
    local now = os.clock()
    if now - (lastRequest[player] or -math.huge) < 0.75 then
        return {ok = false, error = "rate_limited"}
    end
    lastRequest[player] = now
    selectedDuringLoad[player] = true
    -- Per-session preference is applied even if persistence fails.
    player:SetAttribute(ATTRIBUTE, value)
    player:SetAttribute(READY, true)
    local ok, reason = pcall(function()
        store:SetAsync(keyFor(player), value)
    end)
    if not ok then
        warn("[game1][language] preference save unavailable:", tostring(reason))
        return {ok = false, error = "save_unavailable", locale = value}
    end
    return {ok = true, locale = value}
end

function Service.Start()
    if started then return end
    started = true
    local remotes = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if not remotes then
        remotes = Instance.new("Folder")
        remotes.Name = "Game1Remotes"
        remotes.Parent = ReplicatedStorage
    end
    local remote = remotes:FindFirstChild("SetPlayerLanguage")
    if remote and not remote:IsA("RemoteFunction") then error("Invalid SetPlayerLanguage remote") end
    if not remote then
        remote = Instance.new("RemoteFunction")
        remote.Name = "SetPlayerLanguage"
        remote.Parent = remotes
    end
    (remote :: RemoteFunction).OnServerInvoke = save
    Players.PlayerAdded:Connect(function(player)
        task.spawn(load, player)
    end)
    Players.PlayerRemoving:Connect(function(player)
        lastRequest[player] = nil
        selectedDuringLoad[player] = nil
    end)
    for _, player in ipairs(Players:GetPlayers()) do task.spawn(load, player) end
end

return table.freeze(Service)
