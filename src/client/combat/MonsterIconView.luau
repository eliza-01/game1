--!strict
-- One client-side atlas. Pixel runs share the source of the local PNG atlas,
-- avoiding uploaded-image permissions and per-monster textures in Studio.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Atlas = require(Shared:WaitForChild("interface"):WaitForChild("MonsterIconAtlas"))
local View = {}
function View.DangerColor(delta: number): Color3
    if delta >= 10 then return Color3.fromRGB(224, 57, 58) end
    if delta <= 0 then return Color3.fromRGB(155, 161, 169) end
    return Color3.fromRGB(155, 161, 169):Lerp(Color3.fromRGB(224, 57, 58), delta/10)
end
function View.Create(parent: Instance, model: Model): (Frame, UIStroke)
    local key = tostring(model:GetAttribute("MonsterNameEn") or "")
    local runs = Atlas[key] or Atlas.Unknown
    local plate = Instance.new("Frame")
    plate.Name = "MonsterPortrait"
    plate.AnchorPoint = Vector2.new(0.5, 0)
    plate.Position = UDim2.new(0.5, 0, 0, 2)
    plate.Size = UDim2.fromOffset(40, 40)
    plate.BackgroundColor3 = Color3.fromRGB(23, 27, 35)
    plate.BorderSizePixel = 0
    plate.Parent = parent
    local border = Instance.new("UIStroke")
    border.Thickness = 2; border.Parent = plate
    local canvas = Instance.new("Frame")
    canvas.Name = "AtlasTile"; canvas.BackgroundTransparency = 1
    canvas.Position = UDim2.fromOffset(4,4); canvas.Size = UDim2.fromOffset(32,32)
    canvas.Parent = plate
    for _, run in ipairs(runs) do
        local pixel = Instance.new("Frame")
        pixel.BorderSizePixel = 0
        pixel.BackgroundColor3 = Color3.fromHex(run[4])
        pixel.Position = UDim2.fromOffset(run[1]*2,run[2]*2)
        pixel.Size = UDim2.fromOffset(run[3]*2,2)
        pixel.Parent = canvas
    end
    return plate, border
end
return table.freeze(View)
