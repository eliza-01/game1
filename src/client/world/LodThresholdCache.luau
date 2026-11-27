-- Conservative cache for immutable Location pivot distances. Policy owns all
-- decisions; the triangle inequality only proves when a resolve is redundant.
local Cache = {}

local function clearance(distance, config, mode)
    local h = config.hysteresis
    local gap = math.huge
    local function consider(cutoff)
        gap = math.min(gap, math.abs(distance - cutoff - h), math.abs(distance - cutoff + h))
    end
    if mode ~= "full" then consider(config.lod1) end
    if mode == "lod2" then consider(config.lod2) end
    consider(config.hide)
    return gap
end

function Cache.Measure(record, position, policy)
    if record.house then return policy.SurfaceDistance(position, record.worldFrame, record.worldSize) end
    return (position - record.pivot).Magnitude
end

function Cache.Distance(record, position, policy)
    if record.distancePosition ~= position then
        record.distance = Cache.Measure(record, position, policy)
        record.distancePosition = position
    end
    return record.distance
end

function Cache.ResolveAt(record, distance, policy, previous)
    if record.house then return policy.ResolveHouse(distance, previous, record.distances) end
    return policy.Resolve(distance, previous, record.distances, record.mode)
end

function Cache.Resolve(record, position, policy, force)
    local sample = record.thresholdSample
    if sample and not force and sample.result == record.desired then
        -- At an exact boundary with zero hysteresis, the first nil-state
        -- resolve can differ from the next resolve. Prove a fixed point before
        -- skipping a stationary sample there.
        if sample.position == position then
            if sample.fixed or sample.gap > 0 then return false end
        else
            local displacement = (position - sample.position).Magnitude
            -- Conservative guard for Vector3 single precision arithmetic.
            local guard = 0.05 + (sample.distance + displacement) * 0.000001
            if sample.gap > displacement + guard then return false end
        end
    end
    local distance = Cache.Distance(record, position, policy)
    local previous = record.desired
    local result = Cache.ResolveAt(record, distance, policy, previous)
    record.desired = result
    record.thresholdSample = {position=position, distance=distance, result=result,
        gap=clearance(distance, record.distances, record.mode), fixed=previous == result}
    return true
end

return Cache
