-- Wallet and touch buttons share one material; selection changes the outline, not the fill.
local Theme = {}
function Theme.Apply(object: GuiObject)
    object.BackgroundColor3 = Color3.fromRGB(24,26,31)
    object.BackgroundTransparency = 0.18
    object.BorderSizePixel = 0
end
return table.freeze(Theme)
