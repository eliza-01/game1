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
    spec: any, desired: string?, part: MeshPart?, lodPart: MeshPart?,
    templateName: string, fetching: boolean,
    generation: number, retryAt: number, proxy: BasePart?,
    worldFrame: CFrame, worldSize: Vector3,
}
type House = {
    slug: string, plotIndex: number, path: {string}, pivot: CFrame,
    mode: string, config: any, state: string, scale: number,
    visual: {Visual}, distance: number, root: Model?,
}

local function fromComponents(values): CFrame
    return CFrame.new(table.unpack(values))
end
local surfaceDistance = Policy.SurfaceDistance
local function resolvePath(start: Instance, path: {string}): Instance?
    local node: Instance? = start
    for _, key in ipairs(path) do
        if not node then return nil end
        node = node:FindFirstChild(key)
    end
    return node
end

function Adapter.new(houses: any, cache: Instance, hysteresis: number)
    local self = setmetatable({}, Adapter)
    self.cache = cache
    self.hysteresis = hysteresis
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
            table.insert(entries, {spec = spec, desired = nil, part = nil,
                lodPart = nil, templateName = "__HOUSE_PART_LOD1__" .. tostring(spec.lod1ModelAssetId),
                fetching = false, generation = 0, retryAt = 0, proxy = nil,
                worldFrame = worldFrame,
                worldSize = Vector3.new(table.unpack(spec.size)) * row.scale})
        end
        table.insert(self.records, {
            slug = row.slug, plotIndex = row.plotIndex, path = row.path,
            pivot = fromComponents(row.pivot), scale = row.scale,
            mode = config.mode, config = config,
            state = "UNLOADED", visual = entries,
            distance = math.huge, root = nil,
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
        house.distance = math.huge
        for _, visual: Visual in ipairs(house.visual) do
            local spec = visual.spec
            local distance = surfaceDistance(cameraPosition, visual.worldFrame, visual.worldSize)
            house.distance = math.min(house.distance, distance)
            -- No published per-part LOD1: FULL stays until THIS part's unload
            -- distance. Never create a visibility gap before a group LOD switch.
            local mode = if house.mode == "lod1" and spec.lod1ModelAssetId ~= ""
                then "lod1" else "full"
            local nextState = Policy.ResolveHouse(distance, visual.desired, {
                mode = mode, lod1 = spec.lod1From, hide = spec.hideFrom,
                hysteresis = self.hysteresis,
            })
            if nextState ~= visual.desired then
                visual.desired = nextState
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
                -- Custom colors belong to the player's house proxy, not to
                -- the potentially shared published LOD geometry.
                if proxy and visual.spec.mode ~= "atlas" then
                    part.Color = proxy.Color
                    part.Material = proxy.Material
                end
            end)
            if not success then
                warn("[game1][HouseLOD] appearance rejected " .. tostring(reason))
                part:Destroy()
                part = nil
            end
        end
        visual.fetching = false
        self.pending -= 1
        if part and visual.desired == "FULL"
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

-- The existing LocationWorldStreamer grants this adapter its shared budget.
-- Every part transitions independently; no group-wide render gate.
function Adapter:Step(budget: number): number
    local operations = 0
    table.sort(self.records, function(a: House, b: House)
        return a.distance < b.distance
    end)
    for _, house: House in ipairs(self.records) do
        if operations >= budget then break end
        local hasFull, hasLod = false, false
        for _, visual: Visual in ipairs(house.visual) do
            if operations >= budget then break end
            local desired = visual.desired
            if desired ~= "FULL" and self:_removeVisual(visual) then
                operations += 1
            end
            if desired ~= "LOD1" and visual.lodPart then
                visual.lodPart:Destroy()
                visual.lodPart = nil
                operations += 1
            end
            -- Never show FULL and LOD together, including under low budget.
            if operations < budget and desired == "LOD1"
                and not visual.part and not visual.fetching and not visual.lodPart then
                local prototype = self.cache:FindFirstChild(visual.templateName)
                if prototype and prototype:IsA("MeshPart") then
                    local lod = prototype:Clone()
                    lod.Name = visual.spec.name .. "__LOD1"
                    lod.Anchored = true
                    lod.CanCollide = false
                    lod.CanTouch = false
                    lod.CanQuery = false
                    lod.Size = visual.worldSize
                    lod.CFrame = visual.worldFrame
                    local ok = Appearance.Apply(lod, {
                        mode = visual.spec.mode, material = visual.spec.material,
                        color = visual.spec.color, textureId = visual.spec.textureId,
                        alpha = visual.spec.alpha,
                    })
                    if ok then
                        local proxy = self:_proxy(house, visual)
                        if proxy and visual.spec.mode ~= "atlas" then
                            lod.Color = proxy.Color
                            lod.Material = proxy.Material
                        end
                        lod.Parent = self.folder
                        visual.lodPart = lod
                        operations += 1
                    else
                        lod:Destroy()
                    end
                end
            end
            if operations < budget and desired == "FULL" and not visual.lodPart
                and not visual.part and self:_startVisual(house, visual) then
                operations += 1
            end
            -- Preserve player-specific material/color on both representations.
            if visual.part or visual.lodPart then
                local proxy = self:_proxy(house, visual)
                if proxy and visual.spec.mode ~= "atlas" then
                    if visual.part and (visual.part.Color ~= proxy.Color or visual.part.Material ~= proxy.Material) then
                        visual.part.Color = proxy.Color
                        visual.part.Material = proxy.Material
                    end
                    if visual.lodPart and (visual.lodPart.Color ~= proxy.Color or visual.lodPart.Material ~= proxy.Material) then
                        visual.lodPart.Color = proxy.Color
                        visual.lodPart.Material = proxy.Material
                    end
                end
            end
            if desired == "FULL" then hasFull = true
            elseif desired == "LOD1" then hasLod = true end
        end
        house.state = if hasFull then "FULL" elseif hasLod then "LOD1" else "UNLOADED"
    end
    return operations
end

function Adapter:FollowMoving()
    -- No independent RenderStepped or Heartbeat subscription. Only the few
    -- nearby animated door visuals need a transform while their server proxies move.
    for _, house: House in ipairs(self.records) do
        for _, visual: Visual in ipairs(house.visual) do
            if visual.desired == "FULL" and visual.spec.moving and visual.part and visual.proxy and
               visual.proxy:IsDescendantOf(Workspace) then
                if visual.part.CFrame ~= visual.proxy.CFrame then
                    visual.part.CFrame = visual.proxy.CFrame
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
