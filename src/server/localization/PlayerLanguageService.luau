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
-- GetDataStore itself throws in an unpublished Studio Place. Preference is
-- optional: keep the game/UI usable when cloud persistence is unavailable.
local storeOk, store = pcall(function()
    return DataStoreService:GetDataStore("Game1PlayerLanguage_v1")
end)
if not storeOk then
    warn("[game1][language] DataStore unavailable; using per-session language")
    store = nil
end
local ATTRIBUTE = "Game1LanguageChoice"
local READY = "Game1LanguageReady"

local function keyFor(player: Player): string
    return "u:" .. tostring(player.UserId)
end

local function load(player: Player)
    if not store then
        if player.Parent == Players then player:SetAttribute(READY, true) end
        return
    end
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
    if not store then
        return {ok = true, persisted = false, locale = value}
    end
    local ok, reason = pcall(function()
        store:SetAsync(keyFor(player), value)
    end)
    if not ok then
        warn("[game1][language] preference save unavailable:", tostring(reason))
        return {ok = true, persisted = false, locale = value}
    end
    return {ok = true, persisted = true, locale = value}
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
