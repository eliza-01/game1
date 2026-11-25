-- Studio server stages the same immutable LOD prototypes as Runtime.
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local World = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("world")
local Contract = require(World:WaitForChild("StudioLodPreviewContract"))
local Runtime = require(World:WaitForChild("LocationRuntimeManifestContract"))
local Service = {}
function Service.Start(loadPrototype)
    if not RunService:IsStudio() or ReplicatedStorage:FindFirstChild(Runtime.MarkerName) then return end
    local cache = Instance.new("Folder")
    cache.Name = Contract.Cache
    cache.Parent = ReplicatedStorage
    local attempted = {}
    local wanted = {}
    local loading = false
    local function pump()
        if loading then return end
        loading = true
        task.spawn(function()
            while true do
                local nextId = nil
                for id in pairs(wanted) do
                    if not attempted[id] then nextId = id; break end
                end
                if not nextId then break end
                attempted[nextId] = true
                local ok, prototype = pcall(loadPrototype, tonumber(nextId), nextId, nil, true)
                if ok and prototype then
                    if wanted[nextId] then prototype.Parent = cache else prototype:Destroy() end
                else
                    warn("[game1][LOD preview] template unavailable " .. nextId)
                end
            end
            loading = false
        end)
    end
    local function refresh()
        local _, ids = Contract.Read(ReplicatedStorage:FindFirstChild(Contract.Marker))
        wanted = ids or {}
        for _, child in ipairs(cache:GetChildren()) do
            if not wanted[child.Name] then child:Destroy() end
        end
        for id in pairs(attempted) do
            if not wanted[id] then attempted[id] = nil end
        end
        pump()
    end
    local connection = nil
    local function attach()
        if connection then connection:Disconnect(); connection = nil end
        local marker = ReplicatedStorage:FindFirstChild(Contract.Marker)
        if marker and marker:IsA("StringValue") then
            connection = marker:GetPropertyChangedSignal("Value"):Connect(refresh)
        end
        refresh()
    end
    ReplicatedStorage.ChildAdded:Connect(function(child) if child.Name == Contract.Marker then attach() end end)
    ReplicatedStorage.ChildRemoved:Connect(function(child) if child.Name == Contract.Marker then attach() end end)
    attach()
end
return table.freeze(Service)
