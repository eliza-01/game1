-- Deterministic fallback for a type with no previously equipped weapon.
-- Only server-provided, non-empty slugs can be returned.
local Catalog = {}
function Catalog.Pick(rows, kind, preferred)
    local first = nil
    for _, row in ipairs(rows) do
        if row.weaponType == kind and type(row.slug) == "string" and row.slug ~= "" then
            if row.slug == preferred then return row.slug end
            if not first or row.slug < first then first = row.slug end
        end
    end
    return first
end
return table.freeze(Catalog)
