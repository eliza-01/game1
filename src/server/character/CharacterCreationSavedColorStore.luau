--!strict
-- Account-owned palette, independent of character creation / slot persistence.
local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Colors = require(Shared:WaitForChild("character"):WaitForChild("CharacterCreationSavedColors"))
local Store = {}
local cache: {[Player]: {string}} = {}
local persisted: {[Player]: boolean} = {}
local busy: {[Player]: boolean} = {}
local nextRequest: {[Player]: number} = {}
local available, database = pcall(function()
    return DataStoreService:GetDataStore("game1_account_colors_v1")
end)
local function key(player: Player): string return "player_" .. tostring(player.UserId) end
local function read(player: Player): any
    if cache[player] and persisted[player] then
        return {ok = true, colors = cache[player], persisted = true}
    end
    local ok, raw = pcall(function()
        if not available then error("DataStore unavailable") end
        return database:GetAsync(key(player))
    end)
    if player.Parent ~= Players then return {ok = false} end
    if ok then
        if raw ~= nil and (type(raw) ~= "table" or raw.schemaVersion ~= 1 or type(raw.colors) ~= "table") then
            return {ok = false}
        end
        cache[player] = Colors.Normalize(if raw then raw.colors else nil)
        persisted[player] = true
    elseif RunService:IsStudio() then
        cache[player] = cache[player] or {}
        persisted[player] = false
    else
        return {ok = false}
    end
    return {ok = true, colors = cache[player], persisted = persisted[player] == true}
end
local function save(player: Player, value: string): any
    local ok, raw = pcall(function()
        if not available then error("DataStore unavailable") end
        return database:UpdateAsync(key(player), function(previous)
            if previous ~= nil and (type(previous) ~= "table" or previous.schemaVersion ~= 1
                or type(previous.colors) ~= "table") then return nil end
            return {schemaVersion = 1, colors = Colors.Add(if previous then previous.colors else nil, value)}
        end)
    end)
    if player.Parent ~= Players then return {ok = false} end
    if ok and type(raw) == "table" and raw.schemaVersion == 1 then
        cache[player] = Colors.Normalize(raw.colors)
        persisted[player] = true
    elseif not ok and RunService:IsStudio() then
        cache[player] = Colors.Add(cache[player], value)
        persisted[player] = false
    else
        return {ok = false}
    end
    return {ok = true, colors = cache[player], persisted = persisted[player] == true}
end
function Store.Bind(remotes: Folder)
    local remote = Instance.new("RemoteFunction")
    remote.Name = "CharacterCreationSavedColors"
    remote.OnServerInvoke = function(player: Player, action: any, value: any)
        if player:GetAttribute("CharacterCreationStatus") ~= "creation" or busy[player] then return {ok = false} end
        if action ~= "read" and action ~= "save" then return {ok = false} end
        local color = Colors.Hex(value)
        if action == "save" and not color then return {ok = false} end
        if os.clock() < (nextRequest[player] or 0) then return {ok = false} end
        nextRequest[player] = os.clock() + 1
        busy[player] = true
        local ok, result = pcall(function()
            if action == "read" then return read(player) end
            return save(player, color :: string)
        end)
        busy[player] = nil
        return if ok then result else {ok = false}
    end
    remote.Parent = remotes
end
function Store.Forget(player: Player)
    cache[player] = nil; persisted[player] = nil; busy[player] = nil; nextRequest[player] = nil
end
return table.freeze(Store)
