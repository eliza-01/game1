--!strict
-- Authoritative, bounded catalog of optional component publications. Default
-- resources are already requested by the two real bootstrap previews.
local Plan = {}
local MAX_COMPONENTS = 24
local GROUPS = {"hair", "head", "eyes", "eyebrows"}
local HUMANS = {"human_male", "human_female"}

function Plan.Build(registry: any, catalog: any)
    local defaults = {}
    local ready = {}
    local function atlas(part: any, group: string): string
        if group == "eyes" or group == "eyebrows" then return "" end
        return tostring(part.atlas_image_id or "")
    end
    local function key(part: any, group: string): string
        return tostring(part.asset_id) .. ":" .. atlas(part, group)
    end
    for _, row in ipairs(registry.archetypes or {}) do
        if table.find(HUMANS, row.id) and row.status == "ASSEMBLY_READY" and row.assembly and row.assembly.ready then
            ready[row.id] = row.assembly.parts
            for slot, part in pairs(row.assembly.parts) do
                local group = slot
                if slot == "eye_l" or slot == "eye_r" then group = "eyes" end
                if slot == "eyebrow_l" or slot == "eyebrow_r" then group = "eyebrows" end
                defaults[key(part, group)] = true
            end
        end
    end
    local result, byAsset = {}, {}
    local function add(part: any, group: string)
        if not part or defaults[key(part, group)] then return end
        local id = tostring(part.asset_id or "")
        if not id:match("^[1-9]%d*$") then return end
        local record = byAsset[id]
        if not record then
            if #result >= MAX_COMPONENTS then return end
            record = {assetId = assert(tonumber(id)), atlases = {}}
            byAsset[id] = record
            table.insert(result, record)
        end
        local image = atlas(part, group)
        if image:match("^[1-9]%d*$") then record.atlases[image] = true end
    end
    -- Interleave the two archetypes within each slot to avoid gender starvation.
    for _, group in ipairs(GROUPS) do
        local lists = {}
        local longest = 0
        for _, id in ipairs(HUMANS) do
            local options = (catalog.archetypes or {})[id]
            local rows = ready[id] and options and options[group] or {}
            lists[id] = rows
            longest = math.max(longest, #rows)
        end
        for index = 1, longest do
            for _, id in ipairs(HUMANS) do
                local entry = lists[id][index]
                if entry then
                    if group == "head" or group == "hair" then
                        local base = ready[id][group]
                        -- The default head uses the canonical assembly atlas,
                        -- not the catalog's generic head record.
                        if not base or entry.id ~= base.id then add(entry.part, group) end
                    else
                        add(entry.left, group)
                        add(entry.right, group)
                    end
                end
            end
        end
    end
    return result
end

return table.freeze(Plan)
