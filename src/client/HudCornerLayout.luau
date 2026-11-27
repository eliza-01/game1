-- Shared top-left launcher footprint (Core UI safe coordinates, pixels).
local Layout = {}
Layout.SettingsSize = 44
Layout.SettingsLeft = 12
Layout.SettingsTop = 8
Layout.DebugLeft = Layout.SettingsLeft + Layout.SettingsSize + 4
function Layout.DebugColumns(width, right, size, gap, count)
    if width <= 0 then return count end
    return math.clamp(math.floor((width - Layout.DebugLeft - right + gap) / (size + gap)), 1, count)
end
return table.freeze(Layout)
