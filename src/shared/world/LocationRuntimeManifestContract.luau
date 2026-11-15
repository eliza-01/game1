-- Pure validation shared by server template staging and client streamer.
-- A runtime marker is compiler-owned data, never a user-controlled remote.
local Contract = {}
Contract.Kind = "game1-location-visual-stream-v1"
Contract.MarkerName = "Game1LocationRuntimeManifest"
Contract.TemplateFolder = "Game1LocationLodTemplates"
Contract.VisualFolder = "Game1LocationClientVisuals"
Contract.MaxPlacements = 5000
Contract.MaxTargets = 2 -- explicitly bounded pilot: stone_fence_02 / stone_pillar_03
Contract.EnabledSlugs = table.freeze({stone_fence_02 = true, stone_pillar_03 = true})

local function finite(value)
    return type(value) == "number" and value == value and math.abs(value) < 1000000000
end

local function numbers(values, count, positive)
    if type(values) ~= "table" or #values ~= count then return false end
    for _, v in ipairs(values) do
        if not finite(v) or (positive and v <= 0) then return false end
    end
    return true
end

function Contract.Validate(manifest, registry)
    if type(manifest) ~= "table" or manifest.kind ~= Contract.Kind
        or manifest.schemaVersion ~= 1 or manifest.publishAllowed ~= false
        or type(manifest.placements) ~= "table"
        or #manifest.placements < 1 or #manifest.placements > Contract.MaxPlacements
        or type(manifest.targets) ~= "table"
        or #manifest.targets < 1 or #manifest.targets > Contract.MaxTargets then
        return false, "invalid runtime manifest envelope"
    end
    local allowed = {}
    for _, slug in ipairs(manifest.targets) do
        if type(slug) ~= "string" or allowed[slug] or not Contract.EnabledSlugs[slug] then
            return false, "duplicate or invalid target"
        end
        local asset = registry.assets[slug]
        if not asset or tostring(asset.status) ~= "PUBLISHED"
            or tostring(asset.lod1Status) ~= "PUBLISHED"
            or tonumber(asset.modelAssetId) == nil or tonumber(asset.lod1ModelAssetId) == nil then
            return false, "missing published FULL / LOD1: " .. tostring(slug)
        end
        allowed[slug] = true
    end
    local ids = {}
    for _, row in ipairs(manifest.placements) do
        if type(row) ~= "table" or type(row.id) ~= "string" or row.id == ""
            or ids[row.id] or not allowed[row.slug]
            or not numbers(row.pivot, 12, false)
            or not numbers(row.cframe, 12, false)
            or not numbers(row.size, 3, true) then
            return false, "invalid/duplicate placement entry"
        end
        ids[row.id] = true
    end
    return true
end

return table.freeze(Contract)
