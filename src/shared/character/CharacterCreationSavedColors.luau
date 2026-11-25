--!strict
-- One bounded, ordered palette for the account, independent of appearance slots.
local Colors = {}
Colors.Limit = 24
function Colors.Hex(value: any): string?
    if type(value) ~= "string" or not string.match(value, "^#%x%x%x%x%x%x$") then return nil end
    return string.upper(value)
end
function Colors.Normalize(raw: any): {string}
    local result: {string} = {}
    if type(raw) ~= "table" then return result end
    for _, value in ipairs(raw) do
        local color = Colors.Hex(value)
        if color and not table.find(result, color) then table.insert(result, color) end
        if #result >= Colors.Limit then break end
    end
    return result
end
function Colors.Add(raw: any, value: string): {string}
    local result = Colors.Normalize(raw)
    local color = Colors.Hex(value)
    if not color or table.find(result, color) then return result end
    table.insert(result, 1, color)
    if #result > Colors.Limit then table.remove(result) end
    return result
end
return table.freeze(Colors)
