--!strict
-- Shared buff tile renderer for receipts, active strip and shop.
local View={}
function View.Create(parent: Instance,row: any,size: number,zIndex: number?): Frame
    local frame=Instance.new("Frame"); frame.Name=row.name; frame.Size=UDim2.fromOffset(size,size); frame.BackgroundColor3=Color3.fromRGB(26,29,37); frame.BorderSizePixel=0; frame.ZIndex=zIndex or 1; frame.Parent=parent
    local corner=Instance.new("UICorner"); corner.CornerRadius=UDim.new(0,4); corner.Parent=frame
    local stroke=Instance.new("UIStroke"); stroke.Color=row.color; stroke.Thickness=1.5; stroke.Parent=frame
    for y,line in ipairs(row.iconMask) do
        local x=1
        while x<=9 do
            if line:sub(x,x)=="#" then
                local first=x
                while x<=9 and line:sub(x,x)=="#" do x+=1 end
                local pixel=Instance.new("Frame"); pixel.BorderSizePixel=0; pixel.BackgroundColor3=row.color; pixel.ZIndex=frame.ZIndex+1
                pixel.Position=UDim2.fromScale(.14+(first-1)*.08,.14+(y-1)*.08); pixel.Size=UDim2.fromScale((x-first)*.08,.08); pixel.Parent=frame
            else x+=1 end
        end
    end
    return frame
end
return table.freeze(View)
