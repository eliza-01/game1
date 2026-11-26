--!strict
-- Read-only projection of the server's existing Gold attribute.
local Players=game:GetService("Players")
local Input=game:GetService("UserInputService")
local Layout=require(script.Parent.Parent:WaitForChild("character"):WaitForChild("mobile"):WaitForChild("MobileLayout"))
local View={}
function View.Start()
    local player=Players.LocalPlayer
    local gui=Instance.new("ScreenGui"); gui.Name="Game1Wallet"; gui.ResetOnSpawn=false; gui.DisplayOrder=20; gui.Enabled=false
    gui.ScreenInsets=Enum.ScreenInsets.CoreUISafeInsets; gui.Parent=player:WaitForChild("PlayerGui")
    local plate=Instance.new("Frame"); plate.Name="Gold"; plate.AnchorPoint=Vector2.new(0,1); plate.Size=UDim2.fromOffset(116,32)
    plate.BackgroundColor3=Color3.fromRGB(24,26,31); plate.BackgroundTransparency=.18; plate.BorderSizePixel=0; plate.Active=false
    plate:SetAttribute("WorldInputPassthrough",true); plate.Parent=gui
    local corner=Instance.new("UICorner"); corner.CornerRadius=UDim.new(0,8); corner.Parent=plate
    local coin=Instance.new("Frame"); coin.Size=UDim2.fromOffset(20,20); coin.Position=UDim2.fromOffset(8,6); coin.BackgroundColor3=Color3.fromRGB(230,168,48); coin.BorderSizePixel=0; coin.Parent=plate
    local round=Instance.new("UICorner"); round.CornerRadius=UDim.new(1,0); round.Parent=coin
    local ring=Instance.new("UIStroke"); ring.Color=Color3.fromRGB(255,219,119); ring.Thickness=2; ring.Parent=coin
    local inner=Instance.new("Frame"); inner.Size=UDim2.fromOffset(8,12); inner.Position=UDim2.fromOffset(6,4); inner.BackgroundColor3=Color3.fromRGB(255,221,129); inner.BorderSizePixel=0; inner.Parent=coin
    local number=Instance.new("TextLabel"); number.BackgroundTransparency=1; number.Position=UDim2.fromOffset(36,0); number.Size=UDim2.new(1,-42,1,0); number.Font=Enum.Font.GothamBold; number.TextSize=17; number.TextXAlignment=Enum.TextXAlignment.Left; number.TextColor3=Color3.fromRGB(255,222,135); number.TextTruncate=Enum.TextTruncate.AtEnd; number.Parent=plate
    local function resize()
        local bounds=Layout.Resolve(gui.AbsoluteSize.X,gui.AbsoluteSize.Y)
        plate.Position=UDim2.new(0,bounds.margin,1,-(if Input.TouchEnabled then bounds.margin+bounds.stick+bounds.gap else bounds.margin))
    end
    gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(resize); resize()
    local connections: {RBXScriptConnection}={}
    local watched: Model?=nil
    local function bind(character: Model?)
        for _,c in ipairs(connections) do c:Disconnect() end; table.clear(connections); watched=character
        local function update()
            local gold=if character then tonumber(character:GetAttribute("Gold")) else nil
            gui.Enabled=character~=nil and character:GetAttribute("LifeState")=="Alive" and gold~=nil
            number.Text=string.format("%d",gold or 0)
        end
        if character then
            for _,key in ipairs({"Gold","LifeState"}) do table.insert(connections,character:GetAttributeChangedSignal(key):Connect(update)) end
        end
        update()
    end
    player.CharacterAdded:Connect(bind); player.CharacterRemoving:Connect(function(c) if watched==c then bind(nil) end end); bind(player.Character)
end
return table.freeze(View)
