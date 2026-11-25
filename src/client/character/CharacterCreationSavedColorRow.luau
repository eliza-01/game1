--!strict
-- Compact shared horizontal swatches, safe on narrow touch layouts.
local Row = {}
function Row.Create(parent: Instance, zIndex: number): ScrollingFrame
    local row = Instance.new("ScrollingFrame")
    row.Name = "SavedColors"
    row.BackgroundTransparency = 1
    row.BorderSizePixel = 0
    row.ScrollingDirection = Enum.ScrollingDirection.X
    row.ScrollBarThickness = 3
    row.CanvasSize = UDim2.fromOffset(0, 0)
    row.Size = UDim2.new(1, 0, 0, 46)
    row.ZIndex = zIndex
    row.Parent = parent
    return row
end
function Row.Render(row: ScrollingFrame, colors: {string}, current: string?, pick: (string) -> ())
    local scroll = row.CanvasPosition
    for _, child in ipairs(row:GetChildren()) do child:Destroy() end
    for i, value in ipairs(colors) do
        local color = Color3.fromHex(value)
        local swatch = Instance.new("TextButton")
        swatch.Name = "SavedColor" .. tostring(i)
        swatch:SetAttribute("Hex", value)
        swatch.Size = UDim2.fromOffset(40, 40)
        swatch.Position = UDim2.fromOffset(2 + (i - 1) * 47, 2)
        swatch.BackgroundColor3 = color
        swatch.Text = if current and string.upper(current) == value then "✓" else ""
        swatch.TextColor3 = if color.R + color.G + color.B > 1.6 then Color3.fromRGB(22, 27, 30) else Color3.fromRGB(243, 235, 218)
        swatch.Font = Enum.Font.GothamBold
        swatch.TextSize = 19
        swatch.ZIndex = row.ZIndex + 1
        swatch.Parent = row
        local corner = Instance.new("UICorner")
        corner.CornerRadius = UDim.new(0, 8); corner.Parent = swatch
        local border = Instance.new("UIStroke")
        border.Color = if swatch.Text == "✓" then Color3.fromRGB(215, 179, 115) else Color3.fromRGB(166, 169, 165)
        border.Thickness = if swatch.Text == "✓" then 2 else 1
        border.Parent = swatch
        swatch.Activated:Connect(function() pick(value) end)
    end
    row.CanvasSize = UDim2.fromOffset(#colors * 47, 0)
    row.CanvasPosition = scroll
end
function Row.Select(row: ScrollingFrame, current: string)
    for _, child in ipairs(row:GetChildren()) do
        if child:IsA("TextButton") then
            local selected = child:GetAttribute("Hex") == current
            child.Text = if selected then "✓" else ""
            local border = child:FindFirstChildOfClass("UIStroke")
            if border then
                border.Color = if selected then Color3.fromRGB(215, 179, 115) else Color3.fromRGB(166, 169, 165)
                border.Thickness = if selected then 2 else 1
            end
        end
    end
end
return table.freeze(Row)
