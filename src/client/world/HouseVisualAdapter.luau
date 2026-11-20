--!strict
-- House-specific geometry adapter for the ONE LocationWorldStreamer scheduler.
-- No heartbeat, Workspace scans, per-house polling, or client-submitted IDs.
-- FULL meshes are created on demand from compiler-authorized published Mesh IDs.
-- Server keeps only tiny invisible physics/socket proxies and the original Plot.
local InsertService = game:GetService("InsertService")
local Appearance = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
    :WaitForChild("world"):WaitForChild("RuntimeVisualAppearance"))
local Workspace = game:GetService("Workspace")
local Policy = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
    :WaitForChild("world"):WaitForChild("LocationLodDistancePolicy"))

local Adapter = {}
Adapter.__index = Adapter
local MAX_PENDING = 4
local RETRY_SECONDS = 15

type Visual = {
    spec: any, desired: boolean, part: MeshPart?, fetching: boolean,
    generation: number, retryAt: number, proxy: BasePart?,
    worldFrame: CFrame, worldSize: Vector3,
}
type House = {
    slug: string, plotIndex: number, path: {string}, pivot: CFrame,
    mode: string, config: any, desired: string?, state: string, scale: number,
    visual: {Visual}, lod: MeshPart?, distance: number, root: Model?,
}

local function fromComponents(values): CFrame
    return CFrame.new(table.unpack(values))
end
local function surfaceDistance(point: Vector3, frame: CFrame, size: Vector3): number
    local localPoint = frame:PointToObjectSpace(point)
    local half = size * 0.5
    return Vector3.new(math.max(0, math.abs(localPoint.X) - half.X),
        math.max(0, math.abs(localPoint.Y) - half.Y),
        math.max(0, math.abs(localPoint.Z) - half.Z)).Magnitude
end
local function resolvePath(start: Instance, path: {string}): Instance?
    local node: Instance? = start
    for _, key in ipairs(path) do
        if not node then return nil end
        node = node:FindFirstChild(key)
    end
    return node
end

function Adapter.new(houses: any, cache: Instance)
    local self = setmetatable({}, Adapter)
    self.cache = cache
    self.folder = Instance.new("Folder")
    self.folder.Name = "Game1HouseClientVisuals"
    self.folder.Parent = Workspace
    self.records = {} :: {House}
    self.pending = 0
    self.errors = 0
    self.failed = false
    for _, row in ipairs(houses.placements) do
        local config = houses.types[row.slug]
        local entries = {} :: {Visual}
        local pivot = fromComponents(row.pivot)
        for _, spec in ipairs(config.parts) do
            local localFrame = fromComponents(spec.cframe)
            local worldFrame = pivot * CFrame.new(localFrame.Position * row.scale)
                * localFrame.Rotation
            table.insert(entries, {spec = spec, desired = false, part = nil,
                fetching = false, generation = 0, retryAt = 0, proxy = nil,
                worldFrame = worldFrame,
                worldSize = Vector3.new(table.unpack(spec.size)) * row.scale})
        end
        table.insert(self.records, {
            slug = row.slug, plotIndex = row.plotIndex, path = row.path,
            pivot = fromComponents(row.pivot), scale = row.scale,
            mode = config.mode, config = config,
            desired = nil, state = "UNLOADED", visual = entries,
            lod = nil, distance = math.huge, root = nil,
        })
    end
    return self
end

function Adapter:_root(record: House): Model?
    if record.root and record.root:IsDescendantOf(Workspace) then return record.root end
    local candidate = resolvePath(Workspace, record.path)
    if candidate and candidate:IsA("Model") then
        record.root = candidate
        return candidate
    end
    record.root = nil
    return nil
end

function Adapter:_proxy(record: House, visual: Visual): BasePart?
    if visual.proxy and visual.proxy:IsDescendantOf(Workspace) then return visual.proxy end
    local root = self:_root(record)
    if not root then return nil end
    local proxy = resolvePath(root, visual.spec.path)
    if proxy and proxy:IsA("Part") then
        visual.proxy = proxy
        return proxy
    end
    visual.proxy = nil
    return nil
end

function Adapter:Resolve(cameraPosition: Vector3)
    for _, house: House in ipairs(self.records) do
        local origin = house.pivot.Position
        -- House group LOD has priority over EVERY individual mesh radius.
        house.distance = (cameraPosition - origin).Magnitude
        house.desired = Policy.ResolveHouse(house.distance, house.desired, house.config)
        for _, visual: Visual in ipairs(house.visual) do
            local spec = visual.spec
            local distance = surfaceDistance(cameraPosition, visual.worldFrame,
                visual.worldSize)
            local wanted = house.desired == "FULL" and
                Policy.WithinRange(distance, visual.desired, spec.distance, 10)
            if wanted ~= visual.desired then
                visual.desired = wanted
                visual.generation += 1
            end
        end
    end
end

function Adapter:_removeVisual(visual: Visual): boolean
    if visual.part then
        visual.part:Destroy()
        visual.part = nil
        return true
    end
    return false
end

function Adapter:_startVisual(house: House, visual: Visual)
    if self.pending >= MAX_PENDING or visual.fetching then return false end
    if os.clock() < visual.retryAt then return false end
    -- Static visuals can be created from immutable authored CFrames even if
    -- Roblox's own Instance Streaming has not yet replicated distant proxies.
    -- A moving door must wait for its server-owned proxy transform.
    local proxy = self:_proxy(house, visual)
    if visual.spec.moving and not proxy then return false end
    visual.fetching = true
    self.pending += 1
    local ticket = visual.generation
    local meshId = visual.spec.meshId
    task.spawn(function()
        local ok, result = pcall(InsertService.CreateMeshPartAsync,
            InsertService, "rbxassetid://" .. meshId,
            Enum.CollisionFidelity.Box, Enum.RenderFidelity.Performance)
        local part = if ok and typeof(result) == "Instance" and result:IsA("MeshPart")
            then result else nil
        if part then
            local success, reason = pcall(function()
                part.Name = visual.spec.name
                part.Anchored = true
                part.CanCollide = false
                part.CanTouch = false
                part.CanQuery = false
                part.CastShadow = true
                part.Size = visual.worldSize
                part.CFrame = if proxy then proxy.CFrame else visual.worldFrame
                if not Appearance.Apply(part, {
                    mode = visual.spec.mode, material = visual.spec.material,
                    color = visual.spec.color, textureId = visual.spec.textureId,
                    alpha = visual.spec.alpha,
                }) then error("unsupported visual appearance") end
            end)
            if not success then
                warn("[game1][HouseLOD] appearance rejected " .. tostring(reason))
                part:Destroy()
                part = nil
            end
        end
        visual.fetching = false
        self.pending -= 1
        if part and visual.desired and house.desired == "FULL"
            and visual.generation == ticket
            and (not visual.spec.moving or (proxy ~= nil and proxy:IsDescendantOf(Workspace))) then
            visual.part = part
            part.Parent = self.folder
        else
            if part then part:Destroy() end
            if not ok then
                self.errors += 1
                if self.errors <= 8 then
                    warn("[game1][HouseLOD] mesh load failed " .. meshId .. ": " .. tostring(result))
                end
                visual.retryAt = os.clock() + RETRY_SECONDS
            end
        end
    end)
    return true
end

-- Caller allocates the very same budget used for Location FULL/LOD updates.
function Adapter:Step(budget: number): number
    local operations = 0
    table.sort(self.records, function(a: House, b: House)
        local unloadA = a.desired ~= "FULL" and a.state == "FULL"
        local unloadB = b.desired ~= "FULL" and b.state == "FULL"
        if unloadA ~= unloadB then return unloadA end
        return a.distance < b.distance
    end)
    for _, house: House in ipairs(self.records) do
        if operations >= budget then break end
        if house.desired ~= "FULL" then
            for _, visual: Visual in ipairs(house.visual) do
                if operations >= budget then break end
                if self:_removeVisual(visual) then operations += 1 end
            end
        end
        if house.desired ~= "LOD1" and house.lod and operations < budget then
            house.lod:Destroy()
            house.lod = nil
            operations += 1
        end
        if house.desired == "LOD1" and not house.lod and operations < budget then
            local anyFull = false
            for _, visual: Visual in ipairs(house.visual) do
                if visual.part or visual.fetching then anyFull = true break end
            end
            if not anyFull then
                local prototype = self.cache:FindFirstChild(house.slug .. "__HOUSE_LOD1")
                if prototype and prototype:IsA("MeshPart") then
                    local lod = prototype:Clone()
                    lod.Anchored = true
                    lod.CanCollide = false
                    lod.CanTouch = false
                    lod.CanQuery = false
                    lod:PivotTo(house.pivot)
                    if house.scale ~= 1 then lod.Size *= house.scale end
                    lod.Parent = self.folder
                    house.lod = lod
                    operations += 1
                end
            end
        end
        if house.desired == "FULL" and not house.lod then
            for _, visual: Visual in ipairs(house.visual) do
                if operations >= budget then break end
                if not visual.desired then
                    if self:_removeVisual(visual) then operations += 1 end
                elseif not visual.part and self:_startVisual(house, visual) then
                    operations += 1
                end
            end
        end
        if house.desired == "UNLOADED" then
            house.state = "UNLOADED"
        elseif house.lod then
            house.state = "LOD1"
        else
            house.state = "FULL"
        end
    end
    return operations
end

function Adapter:FollowMoving()
    -- No independent RenderStepped or Heartbeat subscription. Only the few
    -- nearby animated door visuals need a transform while their server proxies move.
    for _, house: House in ipairs(self.records) do
        if house.desired == "FULL" then
            for _, visual: Visual in ipairs(house.visual) do
                if visual.spec.moving and visual.part and visual.proxy and
                   visual.proxy:IsDescendantOf(Workspace) then
                    if visual.part.CFrame ~= visual.proxy.CFrame then
                        visual.part.CFrame = visual.proxy.CFrame
                    end
                end
            end
        end
    end
end

function Adapter:Stats(): (number, number, number)
    local full, lod, unloaded = 0, 0, 0
    for _, record: House in ipairs(self.records) do
        if record.state == "FULL" then full += 1
        elseif record.state == "LOD1" then lod += 1
        else unloaded += 1 end
    end
    return full, lod, unloaded
end

return table.freeze(Adapter)
