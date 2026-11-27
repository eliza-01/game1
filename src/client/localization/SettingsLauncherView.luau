--!strict
-- Asset-free black gear on a white circular launcher.
local View = {}
function View.Decorate(button: TextButton, touch: boolean?)
    button.Text = ""
    local black = if touch then Color3.fromRGB(235,239,243) else Color3.fromRGB(0, 0, 0)
    local white = if touch then button.BackgroundColor3 else Color3.fromRGB(255, 255, 255)
    local function piece(name: string, x: number, y: number, w: number, h: number, color: Color3, rotation: number, rounded: boolean)
        local frame = Instance.new("Frame")
        frame.Name = name
        frame.AnchorPoint = Vector2.new(.5, .5)
        frame.Position = UDim2.fromScale(x, y)
        frame.Size = UDim2.fromOffset(w, h)
        frame.BackgroundColor3 = color
        frame.BorderSizePixel = 0
        frame.Rotation = rotation
        frame.Active = false
        frame.Parent = button
        if rounded then
            local corner = Instance.new("UICorner")
            corner.CornerRadius = UDim.new(1, 0)
            corner.Parent = frame
        end
    end
    for i = 0, 7 do
        local angle = i * math.pi / 4
        piece("Tooth"..i, .5 + math.cos(angle)*.21, .5 + math.sin(angle)*.21,
            8, 5, black, math.deg(angle), false)
    end
    piece("GearBody", .5, .5, 22, 22, black, 0, true)
    piece("GearHole", .5, .5, 9, 9, white, 0, true)
end
return table.freeze(View)
