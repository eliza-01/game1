-- Pure distance visual LOD policy. Client-only geometry, not Roblox Workspace Streaming.
-- All thresholds are authored in LOD Manager and embedded in Runtime manifest.
local Policy = {}
Policy.States = table.freeze({FULL = "FULL", LOD1 = "LOD1", LOD2 = "LOD2", UNLOADED = "UNLOADED"})
Policy.Defaults = table.freeze({lod1 = 120, lod2 = 260, hide = 400, hysteresis = 12})
Policy.HouseHysteresis = 10 -- shared technical hysteresis for every house MeshPart

function Policy.Valid(config)
    if type(config) ~= "table" then return false end
    local a, b, c, h = config.lod1, config.lod2, config.hide, config.hysteresis
    if type(a) ~= "number" or type(b) ~= "number" or type(c) ~= "number" or type(h) ~= "number" then
        return false
    end
    return a == a and b == b and c == c and h == h and a >= 16 and a < b and b < c
        and c <= 10000 and h >= 0 and h <= 100 and a > h and b - a > 2 * h and c - b > 2 * h
end

local function tiers(config, mode)
    if mode == "full" then
        return {"FULL", "UNLOADED"}, {config.hide}
    elseif mode == "lod2" then
        return {"FULL", "LOD1", "LOD2", "UNLOADED"}, {config.lod1, config.lod2, config.hide}
    end
    -- Default to the LOD1 mode used by the original independent Studio probe.
    return {"FULL", "LOD1", "UNLOADED"}, {config.lod1, config.hide}
end

local function resolveBands(distance, previousState, states, cutoffs, h)
    local index = nil
    for i, state in ipairs(states) do
        if previousState == state then index = i break end
    end
    if index == nil then
        index = 1
        while index < #states and distance >= cutoffs[index] do index += 1 end
        return states[index]
    end
    while index < #states and distance >= cutoffs[index] + h do index += 1 end
    while index > 1 and distance <= cutoffs[index - 1] - h do index -= 1 end
    return states[index]
end

function Policy.Resolve(distance, previousState, config, mode)
    config = config or Policy.Defaults
    assert(Policy.Valid(config), "invalid LOD distances / hysteresis")
    assert(type(distance) == "number" and distance == distance and distance >= 0,
        "distance must be nonnegative")
    assert(mode == nil or mode == "full" or mode == "lod1" or mode == "lod2", "invalid LOD mode")
    local states, cutoffs = tiers(config, mode)
    return resolveBands(distance, previousState, states, cutoffs, config.hysteresis)
end

-- Distance to the rotated visual bounds, independent of an authored pivot.
function Policy.SurfaceDistance(point, frame, size)
    local localPoint = frame:PointToObjectSpace(point)
    local half = size * 0.5
    return Vector3.new(math.max(0, math.abs(localPoint.X) - half.X),
        math.max(0, math.abs(localPoint.Y) - half.Y),
        math.max(0, math.abs(localPoint.Z) - half.Z)).Magnitude
end

-- Real Estate reuses the same hysteresis resolver independently per MeshPart.
-- Distances are authored exclusively in LOD Manager; no whole-house boundary.
function Policy.ResolveHouse(distance, previousState, config)
    assert(type(config) == "table" and (config.mode == "full" or config.mode == "lod1"),
        "invalid house streaming mode")
    local a,b,h = config.lod1, config.hide, config.hysteresis
    assert(type(a)=="number" and type(b)=="number" and type(h)=="number"
        and a>=20 and a<b and b<=10000 and h>=0 and h<=100
        and a>h and b-a>2*h, "invalid house LOD distances")
    local states = if config.mode == "lod1"
        then {"FULL", "LOD1", "UNLOADED"} else {"FULL", "UNLOADED"}
    local thresholds = if config.mode == "lod1" then {a,b} else {b}
    return resolveBands(distance, previousState, states, thresholds, h)
end
-- Single-mesh visibility tier. Unlike multi-LOD assets, the one cut-off
-- needs a small dead band to avoid repeated toggles near the camera.
function Policy.WithinRange(distance, previous, range, band)
    assert(type(distance) == "number" and distance == distance and distance >= 0,
        "invalid visual distance")
    assert(type(range) == "number" and range >= 20 and range <= 10000,
        "invalid visual range")
    assert(type(band) == "number" and band >= 0 and band <= 100,
        "invalid hysteresis")
    if previous == nil then return distance <= range end
    if previous then return distance < range + band end
    return distance <= range
end
function Policy.VisualWithin(distance, previous, range)
    assert(type(range) == "number" and range <= 1000, "invalid visual range")
    return Policy.WithinRange(distance, previous, range, 10)
end

return table.freeze(Policy)
