--!strict
-- Published animation clip catalog for Studio-only character test stands.
-- Pure reader: does not load assets, choose gameplay states or mutate the registry.
local Catalog = {}

local function sortedKeys(dictionary: any): {string}
    local keys = {}
    for key in pairs(dictionary or {}) do
        table.insert(keys, tostring(key))
    end
    table.sort(keys)
    return keys
end

function Catalog.List(registry: any, profileId: string): {any}
    local profile = registry.profiles and registry.profiles[profileId]
    if type(profile) ~= "table" then
        return {}
    end
    local entries = {}
    local function appendRows(scope: string, weaponSet: string?, slot: string, rows: any)
        for _, clip in ipairs(rows or {}) do
            local animationId = tostring(clip.animationId or "")
            -- Procedural emotion documents are not Roblox animation assets.
            if animationId:match("^rbxassetid://[1-9]%d*$") then
                table.insert(entries, {
                    clipId = tostring(clip.clipId or ""),
                    animationId = animationId,
                    label = if weaponSet then scope .. "/" .. weaponSet .. "/" .. slot else scope .. "/" .. slot,
                    variant = tonumber(clip.variant) or 0,
                    priority = tostring(clip.priority or "Action"),
                    looped = clip.looped == true,
                })
            end
        end
    end
    for _, scope in {"base", "emotions"} do
        local groups = profile[scope] or {}
        for _, slot in sortedKeys(groups) do
            appendRows(scope, nil, slot, groups[slot])
        end
    end
    for _, weaponSet in sortedKeys(profile.weapons) do
        for _, slot in sortedKeys(profile.weapons[weaponSet]) do
            appendRows("weapon", weaponSet, slot, profile.weapons[weaponSet][slot])
        end
    end
    table.sort(entries, function(a, b)
        if a.label ~= b.label then return a.label < b.label end
        if a.variant ~= b.variant then return a.variant < b.variant end
        return a.clipId < b.clipId
    end)
    return entries
end

return table.freeze(Catalog)
