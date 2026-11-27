--!strict
local Formatter = {}
function Formatter.Format(text: string): string
    return (text:gsub("%d+", ""):gsub("%s+", " "):gsub("^%s+", ""):gsub("%s+$", ""))
end
return table.freeze(Formatter)
