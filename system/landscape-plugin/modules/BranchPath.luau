-- Pure recursive surface-follow subdivision. Geometry and Studio UI depend on this,
-- not the other way around. Each level doubles the number of segments.
local BranchPath = {}

local function midpointNormal(a: Vector3, b: Vector3): Vector3
    local combined = a + b
    if combined.Magnitude < 0.001 then
        return a
    end
    return combined.Unit
end

-- Anchors are {position: Vector3, normal: Vector3} in world space.
-- project(position, expectedNormal, spanLength) -> {position, normal}?;
-- a projection is only accepted if the face points toward the same side.
function BranchPath.Build(startAnchor, endAnchor, levels: number, project)
    assert(typeof(startAnchor.position) == "Vector3", "start position required")
    assert(typeof(endAnchor.position) == "Vector3", "end position required")
    assert(typeof(startAnchor.normal) == "Vector3", "start normal required")
    assert(typeof(endAnchor.normal) == "Vector3", "end normal required")
    assert(type(project) == "function", "surface projection callback required")
    assert(type(levels) == "number" and levels >= 0 and levels <= 4 and levels % 1 == 0,
        "follow level must be 0..4")

    local stats = { snapped = 0, missed = 0 }
    local function divide(a, b, remaining)
        if remaining == 0 then
            return {a, b}
        end
        local midpoint = (a.position + b.position) * 0.5
        local normal = midpointNormal(a.normal, b.normal)
        local found = project(midpoint, normal, (b.position - a.position).Magnitude)
        local middle
        if found and typeof(found.position) == "Vector3"
            and typeof(found.normal) == "Vector3"
            and found.normal.Magnitude > 0.001
            and found.normal.Unit:Dot(normal) >= 0.25 then
            middle = {position = found.position, normal = found.normal.Unit}
            stats.snapped += 1
        else
            middle = {position = midpoint, normal = normal}
            stats.missed += 1
        end
        local first = divide(a, middle, remaining - 1)
        local second = divide(middle, b, remaining - 1)
        table.remove(first) -- midpoint appears only once
        for _, item in ipairs(second) do
            table.insert(first, item)
        end
        return first
    end
    return divide(startAnchor, endAnchor, levels), stats
end

return BranchPath
