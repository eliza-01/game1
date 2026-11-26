--!strict
-- Click/tap on the NPC opens one modal. Each icon is an immediate purchase.
local Players=game:GetService("Players")
local RS=game:GetService("ReplicatedStorage")
local RunService=game:GetService("RunService")
local Input=game:GetService("UserInputService")
local Shared=RS:WaitForChild("Game1Shared")
local Buffs=require(Shared:WaitForChild("combat"):WaitForChild("BuffDefinitions"))
local Config=require(Shared:WaitForChild("dev"):WaitForChild("GameplayBufferConfig"))
local Icons=require(script.Parent.Parent:WaitForChild("combat"):WaitForChild("BuffIconView"))
local Coins=require(script.Parent:WaitForChild("GameplayBufferCoins"))
local Controller={}
local player=Players.LocalPlayer
local function near(model: Model): boolean
    local character=player.Character
    local root=character and character:FindFirstChild("RootCollider")
    local npcRoot=model:FindFirstChild("RootCollider")
    return player:GetAttribute("Game1GameplayTestActive")==true and player:GetAttribute("GameplayGuideActive")~=true
        and character~=nil and character:GetAttribute("LifeState")=="Alive" and model.Parent~=nil
        and root~=nil and root:IsA("BasePart") and npcRoot~=nil and npcRoot:IsA("BasePart")
        and (root.Position-npcRoot.Position).Magnitude<=Config.InteractionDistance
end
local function rounded(parent: GuiObject, radius: number)
    local c=Instance.new("UICorner"); c.CornerRadius=UDim.new(0,radius); c.Parent=parent
end
local function label(parent: Instance, text: string, size: number, position: UDim2, dimensions: UDim2): TextLabel
    local l=Instance.new("TextLabel"); l.Text=text; l.Font=Enum.Font.GothamMedium; l.TextSize=size; l.TextColor3=Color3.fromRGB(235,238,244); l.BackgroundTransparency=1; l.Position=position; l.Size=dimensions; l.Parent=parent; return l
end
function Controller.Start()
    if not RunService:IsStudio() then return end
    local remotes=RS:WaitForChild("Game1Remotes")
    local open=remotes:WaitForChild("GameplayBufferOpen",20)
    local remote=remotes:WaitForChild("GameplayTest",20)
    if not open or not open:IsA("RemoteEvent") or not remote or not remote:IsA("RemoteFunction") then return end
    local gui=Instance.new("ScreenGui"); gui.Name="Game1BufferShop"; gui.ResetOnSpawn=false; gui.DisplayOrder=60; gui.Enabled=false; gui.Parent=player:WaitForChild("PlayerGui")
    local backdrop=Instance.new("TextButton"); backdrop.Text=""; backdrop.AutoButtonColor=false; backdrop.BackgroundColor3=Color3.new(0,0,0); backdrop.BackgroundTransparency=.86; backdrop.Size=UDim2.fromScale(1,1); backdrop.Parent=gui
    local panel=Instance.new("Frame"); panel.AnchorPoint=Vector2.new(.5,.5); panel.Position=UDim2.fromScale(.5,.5); panel.Size=UDim2.new(.94,0,0,266); panel.BackgroundColor3=Color3.fromRGB(29,32,40); panel.BorderSizePixel=0; panel.Active=true; panel.Parent=gui; rounded(panel,12)
    local limit=Instance.new("UISizeConstraint"); limit.MaxSize=Vector2.new(410,266); limit.Parent=panel
    local scale=Instance.new("UIScale"); scale.Parent=panel
    local function resize()
        local width,height=gui.AbsoluteSize.X,gui.AbsoluteSize.Y
        scale.Scale=math.min(1,math.max(.5,(height-12)/266))
        if width>=680 then
            panel.AnchorPoint=Vector2.new(1,.5); panel.Position=UDim2.new(1,-18,.5,0)
        else
            panel.AnchorPoint=Vector2.new(.5,.5); panel.Position=UDim2.fromScale(.5,.5)
        end
    end
    gui:GetPropertyChangedSignal("AbsoluteSize"):Connect(resize); resize()
    label(panel,"Buffer · D",20,UDim2.fromOffset(12,8),UDim2.new(1,-54,0,28)).TextXAlignment=Enum.TextXAlignment.Left
    local closeButton=Instance.new("TextButton"); closeButton.Text="×"; closeButton.TextSize=26; closeButton.Font=Enum.Font.GothamBold; closeButton.TextColor3=Color3.fromRGB(235,238,244); closeButton.BackgroundTransparency=1; closeButton.Position=UDim2.new(1,-42,0,4); closeButton.Size=UDim2.fromOffset(38,38); closeButton.Parent=panel
    local balance=label(panel,"",14,UDim2.fromOffset(12,39),UDim2.new(1,-24,0,20)); balance.TextXAlignment=Enum.TextXAlignment.Left; balance.TextColor3=Color3.fromRGB(255,214,117)
    local status=label(panel,"",13,UDim2.new(0,12,1,-27),UDim2.new(1,-24,0,20)); status.TextColor3=Color3.fromRGB(235,197,122)
    local model: Model?=nil; local busy=false; local buttons: {[string]: any}={}
    local function close() model=nil; gui.Enabled=false end
    local function refresh()
        local character=player.Character
        local gold=tonumber(character and character:GetAttribute("Gold")) or 0
        balance.Text=string.format("Gold: %d  ·  %d / buff  ·  %d min",gold,Config.Price,math.floor(Buffs.Rows[1].duration/60))
        for effect,item in pairs(buttons) do
            local expires=tonumber(character and character:GetAttribute("BuffUntil_"..effect)) or 0
            local active=expires>workspace:GetServerTimeNow()
            item.button.Active=not busy and not active and gold>=Config.Price
            item.button.AutoButtonColor=item.button.Active
            item.state.Text=if active then "Active" elseif gold<Config.Price then "Not enough gold" else string.format("%d gold",Config.Price)
            item.button.BackgroundTransparency=if active then .55 else .05
        end
    end
    for i,row in ipairs(Buffs.Rows) do
        local button=Instance.new("TextButton"); button.Name=row.effect; button.Text=""; button.BorderSizePixel=0; button.BackgroundColor3=Color3.fromRGB(42,46,56)
        button.Position=UDim2.new((i-1)%2*.5,12+((i-1)%2)*(-6),0,68+math.floor((i-1)/2)*80); button.Size=UDim2.new(.5,-18,0,72); button.Parent=panel; rounded(button,8)
        local tile=Icons.Create(button,row,42); tile.Position=UDim2.fromOffset(9,15)
        local name=label(button,row.name,15,UDim2.fromOffset(59,10),UDim2.new(1,-64,0,24)); name.TextXAlignment=Enum.TextXAlignment.Left; name.TextColor3=row.color
        local state=label(button,"",12,UDim2.fromOffset(59,36),UDim2.new(1,-64,0,22)); state.TextXAlignment=Enum.TextXAlignment.Left; state.TextScaled=true; local size=Instance.new("UITextSizeConstraint"); size.MaxTextSize=12; size.Parent=state
        buttons[row.effect]={button=button,state=state}
        button.Activated:Connect(function()
            local npc=model; local character=player.Character
            if busy or not button.Active or not npc or not character or not near(npc) then return end
            busy=true; refresh(); status.Text=""
            local ok,response=pcall(function() return remote:InvokeServer("buyBuff",{effect=row.effect}) end)
            if ok and type(response)=="table" and response.ok then Coins.Play(character,npc,Config.Price) end
            busy=false
            if model==npc then status.Text=if ok and type(response)=="table" then tostring(response.message or "") else "Purchase failed"; refresh() end
        end)
    end
    backdrop.Activated:Connect(close); closeButton.Activated:Connect(close)
    Input.InputBegan:Connect(function(input) if gui.Enabled and input.KeyCode==Enum.KeyCode.Escape then close() end end)
    player.CharacterRemoving:Connect(close)
    open.OnClientEvent:Connect(function(npc)
        if typeof(npc)~="Instance" or not npc:IsA("Model") or npc:GetAttribute("GameplayBuffer")~=true or not near(npc) then return end
        model=npc; status.Text=""; gui.Enabled=true; refresh()
    end)
    local elapsed=0
    RunService.Heartbeat:Connect(function(dt)
        if not gui.Enabled then return end
        elapsed+=dt; if elapsed<.15 then return end; elapsed=0
        if not model or not near(model) then close() else refresh() end
    end)
end
return table.freeze(Controller)
