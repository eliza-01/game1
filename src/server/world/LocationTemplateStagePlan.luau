-- Immutable one-time server staging plan. No per-client requests or placement clones.
local Plan = {}
local function distance(anchors, frame, size, surfaceDistance)
    local result = math.huge
    for _, anchor in ipairs(anchors) do
        result = math.min(result, surfaceDistance(anchor, frame, size))
    end
    return result
end

function Plan.Build(manifest, registry, variants, anchors, surfaceDistance)
    local rows, nearest, components = {}, {}, {}
    for _, row in ipairs(manifest.placements) do
        local d = math.huge
        for _, bound in ipairs(row.components or {row}) do
            d = math.min(d, distance(anchors, CFrame.new(table.unpack(bound.cframe)),
                Vector3.new(table.unpack(bound.size)), surfaceDistance))
        end
        nearest[row.slug] = math.min(nearest[row.slug] or math.huge, d)
        if row.components and not components[row.slug] then components[row.slug] = row.components end
    end
    local function add(name, id, d, tier, parts, assembly)
        rows[#rows+1] = {name=name, id=tonumber(id), distance=d, band=math.floor(d/32),
            tier=tier, parts=parts, assembly=assembly}
    end
    for _, slug in ipairs(manifest.targets) do
        local asset = registry.assets[slug]
        for tier, variant in ipairs(variants(manifest.modes[slug])) do
            local id, parts
            if variant == "FULL" then id, parts = asset.modelAssetId, components[slug]
            elseif variant == "LOD1" then id = asset.lod1ModelAssetId
            else id = asset.lod2ModelAssetId end
            add(slug .. "__" .. variant, id, nearest[slug] or math.huge, tier, parts, variant ~= "FULL")
        end
    end
    if manifest.houses then
        local houseDistances = {}
        for _, row in ipairs(manifest.houses.placements) do
            local profile = manifest.houses.types[row.slug]
            if profile.mode == "lod1" then
                local pivot = CFrame.new(table.unpack(row.pivot))
                for _, spec in ipairs(profile.parts) do
                    if spec.lod1ModelAssetId ~= "" then
                        local localFrame = CFrame.new(table.unpack(spec.cframe))
                        local frame = pivot * CFrame.new(localFrame.Position * row.scale) * localFrame.Rotation
                        local d = distance(anchors, frame, Vector3.new(table.unpack(spec.size))*row.scale, surfaceDistance)
                        local id = spec.lod1ModelAssetId
                        houseDistances[id] = math.min(houseDistances[id] or math.huge, d)
                    end
                end
            end
        end
        -- Include profiles without a placement, preserving the manifest contract.
        local partIdsAttempted = {}
        for _, profile in pairs(manifest.houses.types) do
            if profile.mode == "lod1" then
                for _, spec in ipairs(profile.parts) do
                    if spec.lod1ModelAssetId ~= "" then
                        local name = "__HOUSE_PART_LOD1__" .. tostring(spec.lod1ModelAssetId)
                        if not partIdsAttempted[name] then
                            partIdsAttempted[name] = true
                            add(name, spec.lod1ModelAssetId, houseDistances[spec.lod1ModelAssetId] or math.huge, 1, nil, false)
                        end
                    end
                end
            end
        end
    end
    table.sort(rows, function(a,b)
        if a.band ~= b.band then return a.band < b.band end
        if a.tier ~= b.tier then return a.tier < b.tier end
        if a.distance ~= b.distance then return a.distance < b.distance end
        return a.name < b.name
    end)
    return rows
end
return Plan
