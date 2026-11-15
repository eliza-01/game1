-- Location Assets: distance-only desired visual state. No instances, rendering or networking.
-- This is a pure policy and can be tested in Studio without a published LOD model.
local Policy = {}

Policy.States = table.freeze({ FULL = "FULL", LOD1 = "LOD1", UNLOADED = "UNLOADED" })
Policy.Defaults = table.freeze({ fullDistance = 120, unloadDistance = 280, hysteresis = 12 })

local function validate(config)
    local full = config.fullDistance
    local unload = config.unloadDistance
    local hysteresis = config.hysteresis
    assert(type(full) == "number" and full == full and full > 0, "invalid fullDistance")
    assert(type(unload) == "number" and unload == unload and unload > full, "invalid unloadDistance")
    assert(type(hysteresis) == "number" and hysteresis == hysteresis and hysteresis >= 0,
        "invalid hysteresis")
    assert(full > hysteresis and unload - full > hysteresis * 2,
        "LOD distances must leave room for hysteresis")
end

function Policy.Resolve(distance, previousState, config)
    config = config or Policy.Defaults
    validate(config)
    assert(type(distance) == "number" and distance == distance and distance >= 0,
        "distance must be nonnegative")
    local full = config.fullDistance
    local unload = config.unloadDistance
    local h = config.hysteresis
    if previousState == "FULL" then
        if distance >= unload + h then return "UNLOADED" end
        if distance >= full + h then return "LOD1" end
        return "FULL"
    elseif previousState == "LOD1" then
        if distance >= unload + h then return "UNLOADED" end
        if distance <= full - h then return "FULL" end
        return "LOD1"
    elseif previousState == "UNLOADED" then
        if distance <= full - h then return "FULL" end
        if distance <= unload - h then return "LOD1" end
        return "UNLOADED"
    end
    -- Initial selection has no hysteresis; only subsequent transitions do.
    if distance < full then return "FULL" end
    if distance < unload then return "LOD1" end
    return "UNLOADED"
end

return table.freeze(Policy)
