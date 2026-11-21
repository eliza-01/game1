-- Pure validation shared by server template staging and client visual ownership.
-- Runtime marker is compiler-authored, not supplied by clients/remotes.
local HttpService = game:GetService("HttpService")
local Contract = {}
Contract.Kind = "game1-location-visual-stream-v1"
Contract.MarkerName = "Game1LocationRuntimeManifest"
Contract.TemplateFolder = "Game1LocationLodTemplates"
Contract.VisualFolder = "Game1LocationClientVisuals"
Contract.MaxPlacements = 5000
Contract.MaxTargets = 64
Contract.MaxChunks = 64
Contract.ChunkBytes = 120000

-- One compiler-owned marker for both inline and chunked Runtime payloads.
-- Runs exactly once at startup; never rescans Workspace or duplicates a streamer.
local function decodeJson(value)
    local ok, decoded = pcall(HttpService.JSONDecode, HttpService, value)
    if not ok or type(decoded) ~= "table" then
        return nil, "invalid Runtime manifest JSON"
    end
    return decoded
end

function Contract.ReadManifest(marker)
    if not marker or not marker:IsA("StringValue") then
        return nil, "missing or invalid Runtime manifest marker"
    end
    local header, problem = decodeJson(marker.Value)
    if not header then return nil, problem end
    if header.transport == nil then
        if #marker:GetChildren() ~= 0 then return nil, "unexpected inline manifest children" end
        return header -- pre-M388a and small new Runtime drafts
    end
    local count = header.chunks
    if header.transport ~= "chunked-v1" or type(count) ~= "number"
        or count % 1 ~= 0 or count < 2 or count > Contract.MaxChunks
        or type(header.bytes) ~= "number" or header.bytes % 1 ~= 0
        or header.bytes <= 180000 or header.bytes > count * Contract.ChunkBytes
        or type(header.sha256) ~= "string" or #header.sha256 ~= 64 then
        return nil, "invalid Runtime manifest chunk descriptor"
    end
    local parts = table.create(count)
    local deadline = os.clock() + 10 -- bounded startup replication grace period
    for index = 1, count do
        local name = string.format("Chunk%03d", index)
        local valueObject = marker:FindFirstChild(name)
        if not valueObject then
            valueObject = marker:WaitForChild(name, math.max(0, deadline - os.clock()))
        end
        if not valueObject or not valueObject:IsA("StringValue") then
            return nil, "missing Runtime manifest chunk " .. name
        end
        local value = valueObject.Value
        while #value == 0 and os.clock() < deadline do
            task.wait()
            value = valueObject.Value
        end
        if #value == 0 or #value > Contract.ChunkBytes then
            return nil, "invalid Runtime manifest chunk size " .. name
        end
        parts[index] = value
    end
    if #marker:GetChildren() ~= count then
        return nil, "unexpected Runtime manifest chunk count"
    end
    local assembled = table.concat(parts)
    if #assembled ~= header.bytes then
        return nil, "Runtime manifest assembled byte length mismatch"
    end
    return decodeJson(assembled)
end


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


local function paths(value, limit)
    if type(value) ~= "table" or #value < 1 or #value > limit then return false end
    for _, name in ipairs(value) do
        if type(name) ~= "string" or #name == 0 or #name > 100 then return false end
    end
    return true
end
local function validHouseData(houses)
    if type(houses) ~= "table" or type(houses.types) ~= "table"
        or type(houses.placements) ~= "table" or #houses.placements < 1
        or #houses.placements > Contract.MaxPlacements then
        return false, "invalid house runtime data"
    end
    local profiles, count, ids = {}, 0, {}
    for slug, profile in houses.types do
        count += 1
        if count > Contract.MaxTargets or type(slug) ~= "string"
            or not slug:match("^house_level%d+_%d%d$") or type(profile) ~= "table"
            or not (profile.mode == "full" or profile.mode == "lod1")
            or type(profile.parts) ~= "table" or #profile.parts < 1 or #profile.parts > 100 then
            return false, "invalid house streaming profile: " .. tostring(slug)
        end
        local names = {}
        local lodParts = 0
        for _, part in ipairs(profile.parts) do
            if type(part) ~= "table" or type(part.name) ~= "string" or names[part.name]
                or not paths(part.path, 12) or not numbers(part.cframe, 12, false)
                or not numbers(part.size, 3, true) or not tonumber(part.meshId)
                or type(part.lod1From) ~= "number" or part.lod1From < 20
                or part.lod1From ~= math.floor(part.lod1From)
                or type(part.hideFrom) ~= "number" or part.hideFrom > 10000
                or part.hideFrom ~= math.floor(part.hideFrom)
                or part.hideFrom - part.lod1From <= 20
                or type(part.moving) ~= "boolean" or type(part.alpha) ~= "boolean"
                or type(part.doubleSided) ~= "boolean"
                or type(part.lod1ModelAssetId) ~= "string"
                or (part.lod1ModelAssetId ~= "" and (not tonumber(part.lod1ModelAssetId)
                    or tonumber(part.lod1ModelAssetId) <= 0))
                or not (part.mode == "material" or part.mode == "atlas"
                    or part.mode == "material_atlas")
                or type(part.material) ~= "string" or type(part.color) ~= "string"
                or (part.mode ~= "material" and not tonumber(part.textureId)) then
                return false, "invalid house visual descriptor"
            end
            names[part.name] = true
            if part.lod1ModelAssetId ~= "" then lodParts += 1 end
        end
        if profile.mode == "lod1" and lodParts == 0 then
            return false, "house has no published LOD1 parts: " .. tostring(slug)
        end
        profiles[slug] = true
    end
    if count == 0 then return false, "empty house type selection" end
    for _, house in ipairs(houses.placements) do
        if type(house) ~= "table" or not profiles[house.slug]
            or type(house.plotIndex) ~= "number" or house.plotIndex % 1 ~= 0
            or house.plotIndex < 1 or house.plotIndex > 50
            or not paths(house.path, 12) or not numbers(house.pivot, 12, false)
            or not finite(house.scale) or house.scale <= 0 or house.scale > 1000 then
            return false, "invalid house placement"
        end
        local identity = house.slug .. ":" .. tostring(house.plotIndex)
        if ids[identity] then return false, "duplicate house Plot placement" end
        ids[identity] = true
    end
    return true
end
function Contract.Validate(manifest, registry)
    if type(manifest) ~= "table" or manifest.kind ~= Contract.Kind
        or (manifest.schemaVersion ~= 2 and manifest.schemaVersion ~= 3) or manifest.publishAllowed ~= false
        or type(manifest.placements) ~= "table" or not distancesValid(manifest.distances)
        or #manifest.placements > Contract.MaxPlacements
        or type(manifest.targets) ~= "table"
        or #manifest.targets > Contract.MaxTargets
        or type(manifest.modes) ~= "table" then
        return false, "invalid runtime manifest envelope"
    end
    if manifest.schemaVersion == 3 then
        local okay, why = validHouseData(manifest.houses)
        if not okay then return false, why end
    elseif #manifest.targets == 0 or #manifest.placements == 0 or manifest.houses ~= nil then
        return false, "legacy runtime manifest needs Location placements only"
    end
    if #manifest.targets == 0 and #manifest.placements > 0 then
        return false, "Location placements without Location targets"
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
        if row.components ~= nil then
            if type(row.components) ~= "table" or #row.components < 1
                or #row.components > 64 or not paths(row.modelPath, 16) then
                return false, "invalid composite Location model path"
            end
            local names = {}
            for _, component in ipairs(row.components) do
                if type(component) ~= "table" or type(component.name) ~= "string"
                    or #component.name == 0 or names[component.name]
                    or type(component.meshId) ~= "string"
                    or not component.meshId:match("^[1-9]%d*$")
                    or not numbers(component.cframe,12,false)
                    or not numbers(component.size,3,true)
                    or type(component.collidable) ~= "boolean" then
                    return false, "invalid composite Location visual"
                end
                names[component.name] = true
            end
        elseif row.modelPath ~= nil then
            return false, "Location model path without components"
        end
        ids[row.id], used[row.slug] = true, true
    end
    for slug in pairs(allowed) do
        if not used[slug] then return false, "empty selected target: " .. slug end
    end
    return true
end
return table.freeze(Contract)
