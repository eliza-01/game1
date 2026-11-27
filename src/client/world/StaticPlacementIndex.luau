-- Immutable broad phase over snapshot pivots. Per-placement influence bounds
-- avoid a global max radius or enumerating empty cells in a sparse world.
-- This module does not decide LOD or inspect live Instances.
local Index = {}
Index.__index = Index
local LEAF_SIZE = 8
local AXES = {"X", "Y", "Z"}

local function build(entries)
    if #entries == 0 then return nil end
    local lo, hi, centerLo, centerHi = {}, {}, {}, {}
    for i, axis in ipairs(AXES) do
        lo[i], hi[i], centerLo[i], centerHi[i] = math.huge, -math.huge, math.huge, -math.huge
        for _, entry in ipairs(entries) do
            local c = entry.pivot[axis]
            lo[i] = math.min(lo[i], c - entry.radius)
            hi[i] = math.max(hi[i], c + entry.radius)
            centerLo[i] = math.min(centerLo[i], c)
            centerHi[i] = math.max(centerHi[i], c)
        end
    end
    local node = {lo=lo, hi=hi}
    if #entries <= LEAF_SIZE then
        node.entries = entries
        return node
    end
    local split = 1
    for i=2,3 do
        if centerHi[i]-centerLo[i] > centerHi[split]-centerLo[split] then split = i end
    end
    local axis = AXES[split]
    table.sort(entries, function(a,b)
        return a.pivot[axis] < b.pivot[axis]
    end)
    local left, right = {}, {}
    local mid = math.floor(#entries / 2)
    for i, entry in ipairs(entries) do
        local side = i <= mid and left or right
        side[#side+1] = entry
    end
    node.left, node.right = build(left), build(right)
    return node
end

local function query(node, position, out)
    if not node then return end
    for i, axis in ipairs(AXES) do
        local c = position[axis]
        if c < node.lo[i] or c > node.hi[i] then return end
    end
    if node.entries then
        for _, entry in ipairs(node.entries) do
            local p, r = entry.pivot, entry.radius
            if math.abs(position.X-p.X) <= r and math.abs(position.Y-p.Y) <= r
                and math.abs(position.Z-p.Z) <= r then
                out[#out+1] = entry.record
            end
        end
    else
        query(node.left, position, out)
        query(node.right, position, out)
    end
end

function Index.new(records)
    local entries = {}
    for _, record in ipairs(records) do
        -- Include the entire hysteresis band, even at equality. Small numeric
        -- margin makes scalar bounds conservative versus Vector3 float math.
        local radius = record.distances.hide + record.distances.hysteresis
        entries[#entries+1] = {record=record, pivot=record.pivot, radius=radius+0.05}
    end
    return setmetatable({root=build(entries)}, Index)
end

function Index:Query(position)
    local out = {}
    query(self.root, position, out)
    return out
end

return Index
