-- M358 · Pure horizontal sector / target OBB intersection. No Workspace or remotes.
-- A target counts when its projected OBB actually intersects the finite sector,
-- not merely when its center is inside. Vertical overlap is tested independently.
local MeleeArcGeometry = {}

local EPS = 1e-5

local function cross(a: Vector2, b: Vector2): number
    return a.X * b.Y - a.Y * b.X
end

local function projectedHull(frame: CFrame, size: Vector3): ({Vector2}, number, number)
    local half = size * 0.5
    local points = {}
    local bottom, top = math.huge, -math.huge
    for _, x in ipairs({-1, 1}) do
        for _, y in ipairs({-1, 1}) do
            for _, z in ipairs({-1, 1}) do
                local point = frame:PointToWorldSpace(Vector3.new(x * half.X, y * half.Y, z * half.Z))
                table.insert(points, Vector2.new(point.X, point.Z))
                bottom = math.min(bottom, point.Y)
                top = math.max(top, point.Y)
            end
        end
    end
    table.sort(points, function(a, b)
        return a.X < b.X or (a.X == b.X and a.Y < b.Y)
    end)
    local lower, upper = {}, {}
    for _, p in ipairs(points) do
        while #lower > 1 and cross(lower[#lower] - lower[#lower - 1], p - lower[#lower]) <= EPS do
            table.remove(lower)
        end
        table.insert(lower, p)
    end
    for i = #points, 1, -1 do
        local p = points[i]
        while #upper > 1 and cross(upper[#upper] - upper[#upper - 1], p - upper[#upper]) <= EPS do
            table.remove(upper)
        end
        table.insert(upper, p)
    end
    table.remove(lower)
    table.remove(upper)
    for _, p in ipairs(upper) do table.insert(lower, p) end
    return lower, bottom, top
end

local function insideSector(relative: Vector2, forward: Vector2, reach: number, halfAngle: number): boolean
    local squared = relative:Dot(relative)
    if squared > (reach + EPS) ^ 2 then return false end
    if squared <= EPS or halfAngle >= math.pi - EPS then return true end
    return relative:Dot(forward) >= math.sqrt(squared) * math.cos(halfAngle) - EPS
end

local function onSegment(a: Vector2, b: Vector2, p: Vector2): boolean
    local direction = b - a
    local lengthSq = direction:Dot(direction)
    if lengthSq <= EPS then return (p - a).Magnitude <= EPS end
    local t = (p - a):Dot(direction) / lengthSq
    return t >= -EPS and t <= 1 + EPS and math.abs(cross(direction, p - a)) < EPS * math.max(1, direction.Magnitude)
end

local function pointInPolygon(point: Vector2, poly: {Vector2}): boolean
    local inside = false
    for i = 1, #poly do
        local a, b = poly[i], poly[i % #poly + 1]
        if onSegment(a, b, point) then return true end
        if (a.Y > point.Y) ~= (b.Y > point.Y) then
            local x = a.X + (point.Y - a.Y) * (b.X - a.X) / (b.Y - a.Y)
            if x > point.X then inside = not inside end
        end
    end
    return inside
end

local function segmentContactInSector(a: Vector2, b: Vector2, forward: Vector2, reach: number, halfAngle: number): Vector2?
    if insideSector(a, forward, reach, halfAngle) then return a end
    if insideSector(b, forward, reach, halfAngle) then return b end
    local delta = b - a
    local denom = delta:Dot(delta)
    if denom < EPS then return nil end

    -- Circle boundary: the segment may cross the rounded arc while all its
    -- corners stay outside (including full-circle 360-degree melee).
    local discriminant = (a:Dot(delta)) ^ 2 - denom * (a:Dot(a) - reach * reach)
    if discriminant >= 0 then
        local root = math.sqrt(discriminant)
        for _, t in ipairs({(-a:Dot(delta) - root) / denom, (-a:Dot(delta) + root) / denom}) do
            if t >= 0 and t <= 1 and insideSector(a + delta * t, forward, reach, halfAngle) then
                return a + delta * t
            end
        end
    end
    if halfAngle >= math.pi - EPS then return nil end

    -- The two radial boundaries of the sector are finite segments from zero
    -- to reach. Their intersection with each projected OBB edge is exact.
    for _, angle in ipairs({-halfAngle, halfAngle}) do
        local cosine, sine = math.cos(angle), math.sin(angle)
        local ray = Vector2.new(forward.X * cosine - forward.Y * sine, forward.X * sine + forward.Y * cosine)
        local denominator = cross(ray, delta)
        if math.abs(denominator) > EPS then
            local distance = cross(a, delta) / denominator
            local t = cross(a, ray) / denominator
            if distance >= -EPS and distance <= reach + EPS and t >= -EPS and t <= 1 + EPS then
                return a + delta * t
            end
        end
    end
    return nil
end

function MeleeArcGeometry.Contact(
    boxFrame: CFrame, boxSize: Vector3, rootPosition: Vector3, lookVector: Vector3,
    reach: number, arcAngleDegrees: number, minY: number, maxY: number
): Vector3?
    local hull, bottom, top = projectedHull(boxFrame, boxSize)
    if bottom > maxY + EPS or top < minY - EPS or #hull == 0 then return nil end
    local projectedFacing = Vector2.new(lookVector.X, lookVector.Z)
    if projectedFacing.Magnitude <= EPS then return nil end
    local facing = projectedFacing.Unit
    local origin = Vector2.new(rootPosition.X, rootPosition.Z)
    local halfAngle = math.rad(math.clamp(arcAngleDegrees, 1, 360)) * 0.5
    local localHull = {}
    for _, p in ipairs(hull) do
        local v = p - origin
        table.insert(localHull, v)
        if insideSector(v, facing, reach, halfAngle) then
            return Vector3.new(p.X, math.clamp(boxFrame.Position.Y, minY, maxY), p.Y)
        end
    end
    if pointInPolygon(origin, localHull) then
        return Vector3.new(rootPosition.X, math.clamp(boxFrame.Position.Y, minY, maxY), rootPosition.Z)
    end
    for i = 1, #localHull do
        local a, b = localHull[i], localHull[i % #localHull + 1]
        local onEdge = segmentContactInSector(a, b, facing, reach, halfAngle)
        if onEdge then
            local contact = onEdge + origin
            return Vector3.new(contact.X, math.clamp(boxFrame.Position.Y, minY, maxY), contact.Y)
        end
    end
    return nil
end

return table.freeze(MeleeArcGeometry)
