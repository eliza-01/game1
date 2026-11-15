-- Pure validation shared by server template staging and client visual ownership.
-- Runtime marker is compiler-authored, not supplied by clients/remotes.
local Contract = {}
Contract.Kind = "game1-location-visual-stream-v1"
Contract.MarkerName = "Game1LocationRuntimeManifest"
Contract.TemplateFolder = "Game1LocationLodTemplates"
Contract.VisualFolder = "Game1LocationClientVisuals"
Contract.MaxPlacements = 5000
Contract.MaxTargets = 64

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
local function distancesValid(value)
    if type(value) ~= "table" then return false end
    local a, b, c, h = value.lod1, value.lod2, value.hide, value.hysteresis
    return finite(a) and finite(b) and finite(c) and finite(h)
        and a >= 16 and a < b and b < c and c <= 10000
        and h >= 0 and h <= 100 and a > h and b-a > 2*h and c-b > 2*h
end

function Contract.Variants(mode)
    if mode == "full" then return {"FULL"} end
    if mode == "lod1" then return {"FULL", "LOD1"} end
    if mode == "lod2" then return {"FULL", "LOD1", "LOD2"} end
    return nil
end

function Contract.Validate(manifest, registry)
    if type(manifest) ~= "table" or manifest.kind ~= Contract.Kind
        or manifest.schemaVersion ~= 2 or manifest.publishAllowed ~= false
        or type(manifest.placements) ~= "table" or not distancesValid(manifest.distances)
        or #manifest.placements < 1 or #manifest.placements > Contract.MaxPlacements
        or type(manifest.targets) ~= "table"
        or #manifest.targets < 1 or #manifest.targets > Contract.MaxTargets
        or type(manifest.modes) ~= "table" then
        return false, "invalid runtime manifest envelope"
    end
    local allowed = {}
    for _, slug in ipairs(manifest.targets) do
        if type(slug) ~= "string" or allowed[slug] then
            return false, "duplicate or invalid target"
        end
        local mode = manifest.modes[slug]
        if not Contract.Variants(mode) then return false, "unsupported target mode: " .. tostring(slug) end
        local asset = registry.assets[slug]
        if not asset or asset.status ~= "PUBLISHED" or tonumber(asset.modelAssetId) == nil then
            return false, "missing published FULL: " .. tostring(slug)
        end
        if (mode == "lod1" or mode == "lod2")
            and (asset.lod1Status ~= "PUBLISHED" or tonumber(asset.lod1ModelAssetId) == nil) then
            return false, "missing published LOD1: " .. slug
        end
        if mode == "lod2" and (asset.lod2Status ~= "PUBLISHED"
            or tonumber(asset.lod2ModelAssetId) == nil) then
            return false, "missing published LOD2: " .. slug
        end
        allowed[slug] = true
    end
    local ids, used = {}, {}
    for _, row in ipairs(manifest.placements) do
        if type(row) ~= "table" or type(row.id) ~= "string" or row.id == ""
            or ids[row.id] or not allowed[row.slug]
            or not numbers(row.pivot, 12, false)
            or not numbers(row.cframe, 12, false)
            or not numbers(row.size, 3, true) then
            return false, "invalid/duplicate placement entry"
        end
        ids[row.id], used[row.slug] = true, true
    end
    for slug in pairs(allowed) do
        if not used[slug] then return false, "empty selected target: " .. slug end
    end
    return true
end
return table.freeze(Contract)
