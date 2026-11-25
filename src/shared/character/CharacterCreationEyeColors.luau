--!strict
-- Canonical per-eye color payload. Scalar v1 profiles migrate on validation.
local EyeColors = {}
export type Pair = {l: string, r: string}

function EyeColors.Parse(value: any): string?
    if type(value) ~= "string" or not string.match(value, "^#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]$") then
        return nil
    end
    return string.upper(value)
end

function EyeColors.Defaults(parts: any): Pair
    return {l = EyeColors.Parse((parts.eye_l or {}).color) or "#000000",
        r = EyeColors.Parse((parts.eye_r or {}).color) or "#000000"}
end

function EyeColors.Normalize(value: any, defaults: Pair): Pair?
    if value == nil then return table.clone(defaults) end
    if type(value) == "string" then
        local color = EyeColors.Parse(value)
        if not color then return nil end
        return {l = color, r = color}
    end
    if type(value) ~= "table" then return nil end
    local result = table.clone(defaults)
    for side, raw in pairs(value) do
        if side ~= "l" and side ~= "r" then return nil end
        local color = EyeColors.Parse(raw)
        if not color then return nil end
        if side == "l" then result.l = color else result.r = color end
    end
    return result
end

return table.freeze(EyeColors)
