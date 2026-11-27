-- House parts are ordinary records of the single LocationWorldStreamer index,
-- threshold cache, transition queue and work scheduler. Only acquisition and
-- proxy-specific appearance/interaction belong to this adapter.
local InsertService = game:GetService("InsertService")
local Workspace = game:GetService("Workspace")
local Appearance = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
    :WaitForChild("world"):WaitForChild("RuntimeVisualAppearance"))
local DoorRaycast = require(script.Parent:WaitForChild("DoorInteractionRaycast"))
local Job = require(script.Parent:WaitForChild("LodAssemblyJob"))
local Requests = require(script.Parent:WaitForChild("HouseMeshRequests"))

local Adapter = {}
Adapter.__index = Adapter

local function resolvePath(start, path)
    local node = start
    for _, key in ipairs(path) do
        if not node then return nil end
        node = node:FindFirstChild(key)
    end
    return node
end

function Adapter.new(houses, prototypeCache, hysteresis, records)
    local self = setmetatable({prototypeCache=prototypeCache, records={}, moving={},
        templateDependents={}, destroyed=false, errors=0}, Adapter)
    self.folder = Instance.new("Folder")
    self.folder.Name = "Game1HouseClientVisuals"
    self.folder.Parent = Workspace
    self.requests = Requests.new(os.clock, task.spawn, function(visual)
        local part = InsertService:CreateMeshPartAsync("rbxassetid://" .. visual.spec.meshId,
            if visual.spec.moving then Enum.CollisionFidelity.Default else Enum.CollisionFidelity.Box,
            Enum.RenderFidelity.Performance)
        if part and part:IsA("MeshPart") then return part end
        if part then part:Destroy() end
        error("FULL acquisition did not return MeshPart")
    end, function(part) part:Destroy() end, function(visual, reason)
        self:_warn(visual, reason)
    end)
    for _, row in ipairs(houses.placements) do
        local config = houses.types[row.slug]
        local pivot = CFrame.new(table.unpack(row.pivot))
        for _, spec in ipairs(config.parts) do
            local localFrame = CFrame.new(table.unpack(spec.cframe))
            local worldFrame = pivot * CFrame.new(localFrame.Position * row.scale) * localFrame.Rotation
            local mode = if config.mode == "lod1" and spec.lod1ModelAssetId ~= "" then "lod1" else "full"
            local visual = {house=true, order=#records+1, slug=row.slug, path=row.path, spec=spec,
                pivot=worldFrame.Position, worldFrame=worldFrame,
                worldSize=Vector3.new(table.unpack(spec.size))*row.scale,
                mode=mode, distances={mode=mode, lod1=spec.lod1From, hide=spec.hideFrom, hysteresis=hysteresis},
                actual="UNLOADED", generation=0, retryAt=0, prototypeDirty=true,
                templateName="__HOUSE_PART_LOD1__" .. tostring(spec.lod1ModelAssetId), distance=math.huge}
            records[#records+1] = visual
            self.records[#self.records+1] = visual
            if mode == "lod1" then
                local dependents = self.templateDependents[visual.templateName] or {}
                self.templateDependents[visual.templateName] = dependents
                dependents[#dependents+1] = visual
            end
        end
    end
    self.cacheChangedConnection = prototypeCache:ConnectChanged(function(name)
        for _, visual in ipairs(self.templateDependents[name] or {}) do
            visual.prototypeDirty = true
            visual.prototypeEpoch = (visual.prototypeEpoch or 0) + 1
        end
    end)
    return self
end

function Adapter:_warn(visual, reason)
    self.errors += 1
    if self.errors <= 8 then warn("[game1][HouseLOD] " .. visual.slug .. "/" .. visual.spec.name .. ": " .. tostring(reason)) end
end

function Adapter:_proxy(visual)
    local root = resolvePath(Workspace, visual.path)
    local proxy = root and root:IsA("Model") and resolvePath(root, visual.spec.path)
    if proxy and proxy:IsA("Part") and proxy:IsDescendantOf(Workspace) then return proxy end
    return nil
end

local function customAppearance(visual, part, proxy)
    if proxy and visual.spec.mode ~= "atlas" then
        if part.Color ~= proxy.Color then part.Color = proxy.Color end
        if part.Material ~= proxy.Material then part.Material = proxy.Material end
    end
end

function Adapter:_unbind(visual)
    if visual.boundProxy and visual.part then DoorRaycast.Unbind(visual.boundProxy, visual.part) end
    visual.boundProxy = nil
end

-- Moving meshes remain owned while their proxy streams out, but are detached
-- and unbound; stream-in reuses the mesh with the new live proxy identity.
function Adapter:_refresh(visual)
    local part = visual.part
    if not part then return end
    local proxy = self:_proxy(visual)
    customAppearance(visual, part, proxy)
    if not visual.spec.moving then return end
    if proxy ~= visual.boundProxy then self:_unbind(visual) end
    if not proxy then
        if part.Parent then part.Parent = nil end
        return
    end
    if part.CFrame ~= proxy.CFrame then part.CFrame = proxy.CFrame end
    if part.Parent ~= self.folder then part.Parent = self.folder end
    if visual.boundProxy ~= proxy then
        DoorRaycast.Bind(proxy, part)
        visual.boundProxy = proxy
    end
end

-- Called only for shared spatial candidates/retained records at observation.
function Adapter:Observe(visual, previousDesired, queue)
    if visual.desired ~= previousDesired then
        visual.generation += 1
        self.requests:Invalidate(visual)
        visual.prototypeDirty = true
    end
    self.requests:Prune(visual)
    if visual.part and not visual.spec.moving then self:_refresh(visual) end
    if visual.desired == "UNLOADED" then
        queue:Set(visual, "UNLOADED", nil, nil, false)
        return
    end
    if visual.desired == "FULL" then
        queue:Set(visual, "FULL", nil, nil, false)
        return
    end
    if not visual.prototypeDirty then return end
    local status, prototype, metadata = self.prototypeCache:Resolve(visual.templateName, "LOD1")
    visual.prototypeDirty = status == "incomplete" or (status == "missing" and self.prototypeCache:FolderReady() == false)
    if status ~= "ready" or not prototype or not prototype:IsA("MeshPart") then
        -- A missing LOD must never remove an existing representation. On a
        -- cold entry fall back to FULL until the prototype becomes available.
        if visual.part then queue:Remove(visual) else queue:Set(visual, "FULL", nil, nil, false) end
        return
    end
    self.requests:Invalidate(visual) -- preferred LOD ready; release any fallback FULL ticket
    local force = visual.actual == "LOD1" and (visual.actualPrototype ~= prototype
        or visual.actualPrototypeGeneration ~= metadata.generation)
    queue:Set(visual, "LOD1", prototype, metadata, force)
    if queue.entries[visual] then queue.entries[visual].epoch = visual.prototypeEpoch or 0 end
end

function Adapter:Valid(transition, job)
    local visual = transition.record
    if transition.prototype and transition.epoch ~= (visual.prototypeEpoch or 0) then return false end
    if job and visual.spec.moving and self:_proxy(visual) ~= job.proxy then return false end
    return true
end

function Adapter:Prepare(transition)
    local visual = transition.record
    if transition.variant == "LOD1" and os.clock() < (visual.lodRetryAt or 0) then
        return nil, "retry backoff", true
    end
    local proxy = self:_proxy(visual)
    if visual.spec.moving and not proxy then return nil, "proxy unavailable", true end
    local acquired
    if transition.variant == "FULL" then
        acquired = self.requests:TakeOrStart(visual, function(ticket)
            return not self.destroyed and visual.generation == ticket
                and visual.desired == transition.desired
                and (not visual.spec.moving or self:_proxy(visual) == proxy)
        end)
        if not acquired then return nil, "FULL pending", true end
    end
    local job = Job.new(function(build)
        local part = acquired or build:Own(transition.prototype:Clone(), "meshClones")
        build.bundle = part
        build:Unit()
        part.Name = visual.spec.name .. (if transition.variant == "LOD1" then "__LOD1" else "")
        part.Anchored = true
        part.CanCollide = false
        part.CanTouch = false
        part.CanQuery = false
        if transition.variant == "FULL" then part.CastShadow = true end
        part.Size = visual.worldSize
        part.CFrame = visual.worldFrame
        if not Appearance.Apply(part, {mode=visual.spec.mode, material=visual.spec.material,
            color=visual.spec.color, textureId=visual.spec.textureId, alpha=visual.spec.alpha}) then
            error("unsupported visual appearance")
        end
    end)
    -- Own the async result immediately, even if cancelled before first Advance.
    if acquired then job:Own(acquired) end
    job.proxy = proxy
    return job
end

function Adapter:Failed(transition, reason, retryable)
    if retryable then return end
    if transition.variant == "LOD1" then transition.record.lodRetryAt = os.clock() + Requests.RetrySeconds
    else self.requests:Backoff(transition.record) end
    self:_warn(transition.record, reason)
end

function Adapter:Commit(transition, job, work)
    local visual = transition.record
    local part = job and job.bundle
    local proxy = part and self:_proxy(visual)
    if part and visual.spec.moving and (not proxy or proxy ~= job.proxy) then
        return false, "proxy changed at commit", true
    end
    if part then
        local ok, reason = pcall(function()
            customAppearance(visual, part, proxy)
            if proxy and (visual.spec.moving or transition.variant == "FULL") then part.CFrame = proxy.CFrame end
            part.Parent = self.folder
        end)
        if not ok then return false, reason, false end
        job:Release()
    end
    self:_unbind(visual)
    if visual.part then work:Retire(visual.part) end
    visual.part = part
    visual.actual = if part then transition.variant else "UNLOADED"
    visual.actualPrototype = if part then transition.prototype else nil
    visual.actualPrototypeGeneration = if part and transition.metadata then transition.metadata.generation else nil
    self.moving[visual] = nil
    if part and visual.spec.moving then
        DoorRaycast.Bind(proxy, part)
        visual.boundProxy = proxy
        self.moving[visual] = true
    end
    -- A fallback FULL may complete while desired is LOD1; retry readiness
    -- on the next observation, not by dropping the usable fallback.
    if visual.actual ~= visual.desired then visual.prototypeDirty = true end
    return true
end

function Adapter:FollowMoving()
    if self.destroyed then return end
    for visual in pairs(self.moving) do self:_refresh(visual) end
end

function Adapter:Destroy()
    if self.destroyed then return end
    self.destroyed = true
    self.cacheChangedConnection:Disconnect()
    self.requests:Destroy()
    for _, visual in ipairs(self.records) do
        self:_unbind(visual)
        if visual.part then visual.part:Destroy(); visual.part = nil end
    end
    self.moving = {}
    self.folder:Destroy()
end

return table.freeze(Adapter)
