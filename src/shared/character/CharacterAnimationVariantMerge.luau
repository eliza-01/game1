--!strict
-- Single semantic animation slot may contain independent numbered variants.
-- Explicit human_common ownership wins only for its own variant, never
-- hiding different male/female variants or silently copying Asset IDs.
local Merge = {}

function Merge.Rows(personal: any, shared: any): {any}
    local keyed = {}
    for _, row in ipairs(personal or {}) do
        keyed[tonumber(row.variant) or 1] = row
    end
    for _, row in ipairs(shared or {}) do
        local version = tonumber(row.variant) or 1
        if row.authoritative == true or keyed[version] == nil then
            keyed[version] = row
        end
    end
    local keys = {}
    for version in pairs(keyed) do table.insert(keys, version) end
    table.sort(keys)
    local result = {}
    for _, version in ipairs(keys) do table.insert(result, keyed[version]) end
    return result
end

function Merge.Version(rows: {any}, variant: number?): {any}
    if variant == nil then return rows end
    local matched = {}
    for _, row in ipairs(rows) do
        if (tonumber(row.variant) or 1) == variant then
            table.insert(matched, row)
        end
    end
    return matched
end

return table.freeze(Merge)
