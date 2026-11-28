-- One detached static MeshPart per requested asset identity, bounded async
-- slots/retry borrowed from house LOD. No per-instance cloud requests.
local InsertService = game:GetService("InsertService")
local Requests = require(script.Parent.Parent:WaitForChild("world"):WaitForChild("HouseMeshRequests"))
local Cache = {}
Cache.__index = Cache
function Cache.new()
    local self = setmetatable({records = {}, stopped = false}, Cache)
    self.requests = Requests.new(os.clock, task.spawn, function(record)
        local asset = record.asset
        local mesh = InsertService:CreateMeshPartAsync("rbxassetid://" .. asset.meshId,
            Enum.CollisionFidelity.Box, Enum.RenderFidelity.Performance)
        if not mesh or not mesh:IsA("MeshPart") then
            if mesh then mesh:Destroy() end
            return nil
        end
        mesh.Size = Vector3.new(table.unpack(asset.size))
        mesh.TextureID = "rbxassetid://" .. asset.imageId
        mesh.Color = Color3.new(1, 1, 1)
        mesh.Material = Enum.Material.SmoothPlastic
        return mesh
    end, function(mesh) mesh:Destroy() end, function(record, reason)
        warn("[game1][MNPC LOD] using red dummy: " .. record.key .. " · " .. tostring(reason))
    end)
    return self
end
function Cache:Get(key, asset)
    if self.stopped or not asset then return nil end
    local record = self.records[key]
    if not record then
        record = {key = key, asset = asset, generation = 1}
        self.records[key] = record
    end
    if record.prototype then return record.prototype end
    record.prototype = self.requests:TakeOrStart(record, function(ticket)
        return not self.stopped and self.records[key] == record and ticket == record.generation
    end)
    return record.prototype
end
function Cache:YieldOutside(keys)
    self.requests:YieldReadyOutside(function(record) return keys[record.key] == true end)
end
function Cache:Destroy()
    self.stopped = true
    self.requests:Destroy()
    for _, record in pairs(self.records) do
        if record.prototype then record.prototype:Destroy() end
    end
    table.clear(self.records)
end
return Cache
