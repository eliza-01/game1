-- Studio-only transport. Validation and ownership live in HouseSocketService.
local RunService = game:GetService("RunService")
local PublishedDebugAccess = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared"):WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Service = require(script.Parent.Parent:WaitForChild("world"):WaitForChild("HouseSocketService"))
local Debug = {}
local started = false
-- Campfire is optional. Its failure cannot disable the House debug panel.
local function campfireService(): any?
    local module = script.Parent.Parent:WaitForChild("world"):FindFirstChild("LocationCampfireService")
    if not module then return nil end
    local ok, service = pcall(require, module)
    return if ok then service else nil
end

local function remote(folder: Instance, name: string): RemoteFunction
    local current = folder:FindFirstChild(name)
    if current and current:IsA("RemoteFunction") then return current end
    if current then current:Destroy() end
    local item = Instance.new("RemoteFunction")
    item.Name = name
    item.Parent = folder
    return item
end

function Debug.Start()
    if started or not PublishedDebugAccess.ServerEnabled() then return end
    started = true
    local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if not folder then
        folder = Instance.new("Folder")
        folder.Name = "Game1Remotes"
        folder.Parent = ReplicatedStorage
    end
    remote(folder, "GetTestHouseSockets").OnServerInvoke = function(player)
        if not PublishedDebugAccess.ServerAllowed(player) then return {ok=false, error="Developer debug access denied"} end
        local metrics = Service.Reconcile()
        return {ok = true, sockets = Service.GetDebugStatus(player), metrics = metrics,
            keyOwned = Service.GetDebugKey(player)}
    end
    remote(folder, "GetTestCampfireSockets").OnServerInvoke = function(player)
        if not PublishedDebugAccess.ServerAllowed(player) then return {ok=false, error="Developer debug access denied"} end
        local campfire = campfireService()
        if not campfire then return {ok = false, error = "Campfire debug service unavailable"} end
        local result = campfire.GetDebugStatus(player)
        return {ok = true, sockets = result.sockets, total = result.total, bound = result.bound}
    end
    remote(folder, "SetTestCampfireSocketRadius").OnServerInvoke = function(player, name, radius)
        if not PublishedDebugAccess.ServerAllowed(player) then return {ok=false, error="Developer debug access denied"} end
        local campfire = campfireService()
        return if campfire then campfire.SetDebugRadius(player, name, radius)
            else {ok = false, error = "Campfire debug service unavailable"}
    end
    remote(folder, "SetTestCampfireSocketHoverRadius").OnServerInvoke = function(player, name, radius)
        if not PublishedDebugAccess.ServerAllowed(player) then return {ok=false, error="Developer debug access denied"} end
        local campfire = campfireService()
        return if campfire then campfire.SetDebugHoverRadius(player, name, radius)
            else {ok = false, error = "Campfire debug service unavailable"}
    end
    remote(folder, "SetTestHouseKeyOwned").OnServerInvoke = function(player, owned)
        if not PublishedDebugAccess.ServerAllowed(player) then return {ok=false, error="Developer debug access denied"} end
        return Service.SetDebugKey(player, owned)
    end
    remote(folder, "SetTestHouseSocketRadius").OnServerInvoke = function(player, name, radius)
        if not PublishedDebugAccess.ServerAllowed(player) then return {ok=false, error="Developer debug access denied"} end
        return Service.SetDebugRadius(player, name, radius)
    end
    remote(folder, "SetTestHouseSocketHoverRadius").OnServerInvoke = function(player, name, radius)
        if not PublishedDebugAccess.ServerAllowed(player) then return {ok=false, error="Developer debug access denied"} end
        return Service.SetDebugHoverRadius(player, name, radius)
    end
    remote(folder, "TeleportTestHouseSpawn").OnServerInvoke = function(player, name)
        if not PublishedDebugAccess.ServerAllowed(player) then return {ok=false, error="Developer debug access denied"} end
        return Service.TeleportDebug(player, name)
    end
end

return table.freeze(Debug)
