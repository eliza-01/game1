-- Studio-only transport. Validation and ownership live in HouseSocketService.
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Service = require(script.Parent.Parent:WaitForChild("world"):WaitForChild("HouseSocketService"))
local Debug = {}
local started = false

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
    if started or not RunService:IsStudio() then return end
    started = true
    local folder = ReplicatedStorage:FindFirstChild("Game1Remotes")
    if not folder then
        folder = Instance.new("Folder")
        folder.Name = "Game1Remotes"
        folder.Parent = ReplicatedStorage
    end
    remote(folder, "GetTestHouseSockets").OnServerInvoke = function(player)
        local metrics = Service.Reconcile()
        return {ok = true, sockets = Service.GetDebugStatus(player), metrics = metrics}
    end
    remote(folder, "SetTestHouseSocketRadius").OnServerInvoke = function(player, name, radius)
        return Service.SetDebugRadius(player, name, radius)
    end
    remote(folder, "TeleportTestHouseSpawn").OnServerInvoke = function(player, name)
        return Service.TeleportDebug(player, name)
    end
end

return table.freeze(Debug)
