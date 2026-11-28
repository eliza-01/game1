-- Pure three-stage policy shared by MNPC presentation and server demand.
local Policy = {}
local function validNumber(n, lo, hi)
    return type(n) == "number" and n % 1 == 0 and n >= lo and n <= hi
end
function Policy.Valid(p)
    return type(p) == "table" and type(p.enabled) == "boolean"
        and validNumber(p.full, 1, 10000) and validNumber(p.hide, 1, 10000)
        and validNumber(p.hysteresis, 0, 100) and p.full > p.hysteresis
        and p.hide - p.full > 2 * p.hysteresis
end
function Policy.Resolve(distance, previous, p, pinned)
    if not p.enabled or pinned then return "FULL" end
    local h = p.hysteresis
    if previous == "FULL" then
        if distance >= p.hide + h then return "UNLOADED" end
        if distance >= p.full + h then return "LOD1" end
        return "FULL"
    elseif previous == "LOD1" then
        if distance <= p.full - h then return "FULL" end
        if distance >= p.hide + h then return "UNLOADED" end
        return "LOD1"
    elseif previous == "UNLOADED" then
        if distance <= p.full - h then return "FULL" end
        if distance <= p.hide - h then return "LOD1" end
        return "UNLOADED"
    end
    if distance < p.full then return "FULL" end
    if distance < p.hide then return "LOD1" end
    return "UNLOADED"
end
function Policy.Key(kind, slug)
    if type(slug) ~= "string" or slug == "" then return nil end
    if kind == "NPC" then return "npc:" .. slug end
    if kind == "Monster" then return "monster:" .. slug end
    return nil
end
return table.freeze(Policy)
