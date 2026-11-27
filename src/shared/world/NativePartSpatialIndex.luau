-- Native broadphase for existing queryable root parts. Each consumer owns its
-- own instance. Radius is a conservative envelope about the registered center;
-- exact contact and gameplay eligibility belong to the consumer.
local Index = {}
Index.__index = Index
local EPSILON = 0.01

function Index.new(world)
    local params = OverlapParams.new()
    params.FilterType = Enum.RaycastFilterType.Include
    params.MaxParts = 0 -- never truncate multi-hit or nearest-ray candidates
    params.RespectCanCollide = false
    return setmetatable({world = world, params = params, byOwner = {}, byPart = {},
        dirty = true, maxRadius = 0, count = 0}, Index)
end

function Index:_invalidate()
    -- Drop the old engine filter immediately; rebuild once before the next query.
    if not self.dirty then self.params.FilterDescendantsInstances = {} end
    self.dirty = true
end

function Index:Remove(owner)
    local record = self.byOwner[owner]
    if not record then return end
    self.byOwner[owner] = nil
    self.byPart[record.part] = nil
    record.ownerDestroyed:Disconnect()
    record.partDestroyed:Disconnect()
    self.count = self.count - 1
    self:_invalidate()
end

function Index:Register(owner, part, radius, value)
    assert(part.CanQuery, "Spatial index requires a queryable root")
    assert(radius >= 0 and radius < math.huge, "Invalid spatial radius")
    self:Remove(owner)
    assert(not self.byPart[part], "Spatial root already registered")
    local record = {owner = owner, part = part, radius = radius, value = value}
    self.byOwner[owner] = record
    self.byPart[part] = record
    self.count = self.count + 1
    self:_invalidate()
    local function destroyed()
        if self.byOwner[owner] == record then self:Remove(owner) end
    end
    record.ownerDestroyed = owner.Destroying:Connect(destroyed)
    record.partDestroyed = part.Destroying:Connect(destroyed)
end

function Index:_refreshFilter()
    if not self.dirty then return end
    local parts, radius = {}, 0
    for part, record in pairs(self.byPart) do
        table.insert(parts, part)
        radius = math.max(radius, record.radius)
    end
    self.params.FilterDescendantsInstances = parts
    self.maxRadius = radius
    self.dirty = false
end

function Index:QueryBox(frame, size)
    if self.count == 0 then return {} end
    self:_refreshFilter()
    local padding = 2 * (self.maxRadius + EPSILON)
    local parts = self.world:GetPartBoundsInBox(frame, size + Vector3.new(padding, padding, padding), self.params)
    local results, seen = {}, {}
    for _, part in ipairs(parts) do
        local record = self.byPart[part]
        if record and not seen[record] then
            seen[record] = true
            table.insert(results, record.value)
        end
    end
    return results
end

function Index:QueryRadius(center, radius)
    local diameter = 2 * radius
    return self:QueryBox(CFrame.new(center), Vector3.new(diameter, diameter, diameter))
end

-- The padded oriented box encloses the entire swept sphere around the ray
-- segment, including both ends. Choose a non-parallel up for vertical shots.
function Index:QueryRay(origin, unitDirection, distance)
    local center = origin + unitDirection * (distance * 0.5)
    local up = Vector3.yAxis
    if math.abs(unitDirection:Dot(up)) > 0.99 then up = Vector3.xAxis end
    local frame = CFrame.lookAt(center, center + unitDirection, up)
    return self:QueryBox(frame, Vector3.new(0, 0, distance))
end

return Index
