-- Pure distance visual LOD policy. Client-only geometry, not Roblox Workspace Streaming.
-- All thresholds are authored in LOD Manager and embedded in Runtime manifest.
local Policy = {}
Policy.States = table.freeze({FULL = "FULL", LOD1 = "LOD1", LOD2 = "LOD2", UNLOADED = "UNLOADED"})
Policy.Defaults = table.freeze({lod1 = 120, lod2 = 260, hide = 400, hysteresis = 12})

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

function Policy.Resolve(distance, previousState, config, mode)
    config = config or Policy.Defaults
    assert(Policy.Valid(config), "invalid LOD distances / hysteresis")
    assert(type(distance) == "number" and distance == distance and distance >= 0,
        "distance must be nonnegative")
    assert(mode == nil or mode == "full" or mode == "lod1" or mode == "lod2", "invalid LOD mode")
    local states, cutoffs = tiers(config, mode)
    local index = nil
    for i, state in ipairs(states) do
        if previousState == state then index = i break end
    end
    if index == nil then
        index = 1
        while index < #states and distance >= cutoffs[index] do index += 1 end
        return states[index]
    end
    -- Hysteresis around EACH transition; allow skipping tiers when camera teleports.
    local h = config.hysteresis
    while index < #states and distance >= cutoffs[index] + h do index += 1 end
    while index > 1 and distance <= cutoffs[index - 1] - h do index -= 1 end
    return states[index]
end
return table.freeze(Policy)
