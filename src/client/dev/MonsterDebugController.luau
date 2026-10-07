local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local MonsterDebugController = {}
local started = false
local player = Players.LocalPlayer

local PANEL_WIDTH = 336
local PANEL_HEIGHT = 354
local COLLAPSED = 44
local PANEL_X = 16
local PANEL_Y = 254
local OPEN_ATTRIBUTE = "Game1DebugPanelOpen"
local PANEL_ID = "MO"
local POLL_SECONDS = 0.65
local STEP = 0.5

local COLORS = {
    panel = Color3.fromRGB(15,20,27), control = Color3.fromRGB(28,37,48), selected = Color3.fromRGB(31,76,70),
    accent = Color3.fromRGB(72,214,180), attack = Color3.fromRGB(239,116,116), text = Color3.fromRGB(239,244,248),
    muted = Color3.fromRGB(139,157,173), line = Color3.fromRGB(55,69,83),
}

local function corner(parent: Instance, radius: number)
    local value = Instance.new("UICorner"); value.CornerRadius = UDim.new(0,radius); value.Parent = parent
end
local function stroke(parent: Instance)
    local value = Instance.new("UIStroke"); value.Color = COLORS.line; value.Transparency = 0.25; value.Parent = parent
end
local function label(parent: Instance, text: string, size: number, bold: boolean?): TextLabel
    local value = Instance.new("TextLabel")
    value.BackgroundTransparency = 1; value.Text = text; value.TextColor3 = COLORS.text; value.TextSize = size
    value.Font = bold and Enum.Font.GothamSemibold or Enum.Font.Gotham; value.TextXAlignment = Enum.TextXAlignment.Left
    value.Parent = parent; return value
end
local function button(parent: Instance, text: string): TextButton
    local value = Instance.new("TextButton")
    value.AutoButtonColor = false; value.BackgroundColor3 = COLORS.control; value.BorderSizePixel = 0
    value.Text = text; value.TextColor3 = COLORS.text; value.TextSize = 11; value.Font = Enum.Font.GothamSemibold
    value.Parent = parent; corner(value,7); stroke(value); return value
end
local function numberBox(parent: Instance): TextBox
    local value = Instance.new("TextBox")
    value.BackgroundColor3 = COLORS.control; value.BorderSizePixel = 0; value.ClearTextOnFocus = false
    value.TextColor3 = COLORS.text; value.TextSize = 11; value.Font = Enum.Font.GothamSemibold; value.TextXAlignment = Enum.TextXAlignment.Center
    value.Parent = parent; corner(value,7); stroke(value); return value
end
local function formatNumber(value: any): string
    return string.format("%.2f", math.max(0, tonumber(value) or 0)):gsub("0+$",""):gsub("%.$","")
end

local function makeRing(name: string, color: Color3)
    local folder = Instance.new("Folder"); folder.Name = name
    local parts = {}
    for index=1,64 do
        local part = Instance.new("Part")
        part.Name=("Segment%02d"):format(index); part.Anchored=true; part.CanCollide=false; part.CanTouch=false; part.CanQuery=false
        part.CastShadow=false; part.Material=Enum.Material.Neon; part.Color=color; part.Transparency=0.18; part.Parent=folder
        parts[index]=part
    end
    return folder,parts
end

local function createGui()
    local playerGui = player:WaitForChild("PlayerGui")
    local old = playerGui:FindFirstChild("Game1MonsterDebugGui"); if old then old:Destroy() end
    local gui = Instance.new("ScreenGui"); gui.Name="Game1MonsterDebugGui"; gui.ResetOnSpawn=false; gui.DisplayOrder=22; gui.Parent=playerGui
    local panel = Instance.new("Frame"); panel.BackgroundColor3=COLORS.panel; panel.BorderSizePixel=0; panel.Position=UDim2.fromOffset(PANEL_X,PANEL_Y); panel.Size=UDim2.fromOffset(COLLAPSED,COLLAPSED); panel.Parent=gui; corner(panel,10); stroke(panel)
    local toggle=button(panel,"MO"); toggle.Position=UDim2.fromOffset(0,0); toggle.Size=UDim2.fromOffset(COLLAPSED,COLLAPSED)
    local title=label(panel,"MONSTER DEBUG",11,true); title.Position=UDim2.fromOffset(16,6); title.Size=UDim2.fromOffset(180,16)
    local subtitle=label(panel,"aggro + combat sandbox",9,false); subtitle.TextColor3=COLORS.muted; subtitle.Position=UDim2.fromOffset(16,22); subtitle.Size=UDim2.fromOffset(200,14)
    local body=Instance.new("Frame"); body.BackgroundTransparency=1; body.Position=UDim2.fromOffset(16,50); body.Size=UDim2.fromOffset(PANEL_WIDTH-32,PANEL_HEIGHT-60); body.Visible=false; body.Parent=panel

    local prev=button(body,"‹"); prev.Position=UDim2.fromOffset(0,0); prev.Size=UDim2.fromOffset(34,34)
    local nextButton=button(body,"›"); nextButton.Position=UDim2.fromOffset(270,0); nextButton.Size=UDim2.fromOffset(34,34)
    local selected=button(body,"NO MONSTERS"); selected.Position=UDim2.fromOffset(40,0); selected.Size=UDim2.fromOffset(224,34); selected.TextTruncate=Enum.TextTruncate.AtEnd
    local aggressive=button(body,"☐ PASSIVE"); aggressive.Position=UDim2.fromOffset(0,46); aggressive.Size=UDim2.fromOffset(304,34)

    local function radiusRow(y:number, caption:string)
        local cap=label(body,caption,9,true); cap.TextColor3=COLORS.muted; cap.Position=UDim2.fromOffset(0,y); cap.Size=UDim2.fromOffset(304,14)
        local minus=button(body,"−"); minus.Position=UDim2.fromOffset(0,y+18); minus.Size=UDim2.fromOffset(42,34)
        local box=numberBox(body); box.Position=UDim2.fromOffset(48,y+18); box.Size=UDim2.fromOffset(208,34)
        local plus=button(body,"+"); plus.Position=UDim2.fromOffset(262,y+18); plus.Size=UDim2.fromOffset(42,34)
        return minus,box,plus
    end
    local aggroMinus,aggroBox,aggroPlus=radiusRow(92,"AGGRO RADIUS · STUDS")
    local attackMinus,attackBox,attackPlus=radiusRow(158,"ATTACK RADIUS · STUDS")
    local reset=button(body,"RESET FROM ASSET MANAGER"); reset.Position=UDim2.fromOffset(0,226); reset.Size=UDim2.fromOffset(304,34)
    local stateText=label(body,"Studio-only runtime tuning",9,false); stateText.TextColor3=COLORS.muted; stateText.Position=UDim2.fromOffset(2,268); stateText.Size=UDim2.fromOffset(300,16)

    local aggroFolder,aggroParts=makeRing("Game1MonsterAggroRadiusPreview",COLORS.accent)
    local attackFolder,attackParts=makeRing("Game1MonsterAttackRadiusPreview",COLORS.attack)
    local collapsed=true
    local rows={}
    local selectedIndex=1
    local selectedRow=nil
    local busy=false

    local function setCollapsed(value:boolean)
        collapsed=value
        body.Visible=not value; title.Visible=not value; subtitle.Visible=not value
        toggle.Text=value and "MO" or "×"; toggle.Position=value and UDim2.fromOffset(0,0) or UDim2.fromOffset(PANEL_WIDTH-COLLAPSED,0)
        TweenService:Create(panel,TweenInfo.new(0.14,Enum.EasingStyle.Quad,Enum.EasingDirection.Out),{Size=value and UDim2.fromOffset(COLLAPSED,COLLAPSED) or UDim2.fromOffset(PANEL_WIDTH,PANEL_HEIGHT)}):Play()
        aggroFolder.Parent=if value then nil else Workspace; attackFolder.Parent=if value then nil else Workspace
    end
    toggle.Activated:Connect(function()
        if collapsed then playerGui:SetAttribute(OPEN_ATTRIBUTE,PANEL_ID) else playerGui:SetAttribute(OPEN_ATTRIBUTE,"") end
    end)
    playerGui:GetAttributeChangedSignal(OPEN_ATTRIBUTE):Connect(function() setCollapsed(playerGui:GetAttribute(OPEN_ATTRIBUTE)~=PANEL_ID) end)
    setCollapsed(playerGui:GetAttribute(OPEN_ATTRIBUTE)~=PANEL_ID)

    local remotes=ReplicatedStorage:WaitForChild("Game1Remotes")
    local catalogRemote=remotes:WaitForChild("GetMonsterDebugCatalog") :: RemoteFunction
    local applyRemote=remotes:WaitForChild("ApplyMonsterDebug") :: RemoteFunction

    local function renderSelected()
        selectedRow=rows[selectedIndex]
        if not selectedRow then
            selected.Text="NO MONSTERS"; aggressive.Text="☐ —"; aggroBox.Text=""; attackBox.Text=""; stateText.Text="no runtime monsters"
            return
        end
        selected.Text=tostring(selectedRow.label or selectedRow.id)
        aggressive.Text=selectedRow.aggressive and "☑ AGGRESSIVE" or "☐ PASSIVE"
        aggressive.BackgroundColor3=selectedRow.aggressive and COLORS.selected or COLORS.control
        aggressive.TextColor3=selectedRow.aggressive and COLORS.accent or COLORS.text
        if not aggroBox:IsFocused() then aggroBox.Text=formatNumber(selectedRow.aggroRadius) end
        if not attackBox:IsFocused() then attackBox.Text=formatNumber(selectedRow.attackRadius) end
        stateText.Text=string.format("%s%s",tostring(selectedRow.aiState or "Idle"),tostring(selectedRow.targetName or "")~="" and (" · target "..tostring(selectedRow.targetName)) or "")
    end

    local function refreshCatalog()
        local previousId=selectedRow and tostring(selectedRow.id) or ""
        local ok,result=pcall(function() return catalogRemote:InvokeServer() end)
        if not ok or type(result)~="table" then return end
        rows=result.monsters or {}
        selectedIndex=1
        for index,row in ipairs(rows) do if tostring(row.id)==previousId then selectedIndex=index; break end end
        renderSelected()
    end

    local function applyPatch(patch:any)
        if busy or not selectedRow then return end
        busy=true
        local ok,result=pcall(function() return applyRemote:InvokeServer(selectedRow.id,patch) end)
        busy=false
        if ok and type(result)=="table" and result.ok==true and result.monster then
            rows[selectedIndex]=result.monster; renderSelected()
        else
            stateText.Text="apply failed"; stateText.TextColor3=COLORS.attack
        end
    end

    prev.Activated:Connect(function() if #rows>0 then selectedIndex=((selectedIndex-2)%#rows)+1; renderSelected() end end)
    nextButton.Activated:Connect(function() if #rows>0 then selectedIndex=(selectedIndex%#rows)+1; renderSelected() end end)
    selected.Activated:Connect(function() if #rows>0 then selectedIndex=(selectedIndex%#rows)+1; renderSelected() end end)
    aggressive.Activated:Connect(function() if selectedRow then applyPatch({aggressive=not selectedRow.aggressive}) end end)
    local function wireRadius(minus:TextButton,box:TextBox,plus:TextButton,key:string)
        local function current() return math.max(0,tonumber(box.Text) or 0) end
        minus.Activated:Connect(function() applyPatch({[key]=math.max(0,current()-STEP)}) end)
        plus.Activated:Connect(function() applyPatch({[key]=current()+STEP}) end)
        box.FocusLost:Connect(function() local n=tonumber(box.Text); if n then applyPatch({[key]=math.max(0,n)}) else renderSelected() end end)
    end
    wireRadius(aggroMinus,aggroBox,aggroPlus,"aggroRadius")
    wireRadius(attackMinus,attackBox,attackPlus,"attackRadius")
    reset.Activated:Connect(function() applyPatch({reset=true}) end)

    local ray=RaycastParams.new(); ray.FilterType=Enum.RaycastFilterType.Exclude; ray.IgnoreWater=false; ray.RespectCanCollide=true
    local function renderRing(parts,model:Model?,radius:number,heightOffset:number)
        local root=model and (model:FindFirstChild("HumanoidRootPart") or model:FindFirstChild("RootCollider"))
        if not root or not root:IsA("BasePart") or radius<=0 then for _,part in ipairs(parts) do part.Transparency=1 end; return end
        ray.FilterDescendantsInstances={model}
        local hit=Workspace:Raycast(root.Position,Vector3.new(0,-64,0),ray)
        local center=Vector3.new(root.Position.X,(hit and hit.Position.Y or root.Position.Y-root.Size.Y*0.5)+heightOffset,root.Position.Z)
        local chord=2*radius*math.sin(math.pi/#parts)+0.04
        for index,part in ipairs(parts) do
            local angle=((index-0.5)/#parts)*math.pi*2
            local pos=center+Vector3.new(math.cos(angle)*radius,0,math.sin(angle)*radius)
            part.Size=Vector3.new(chord,0.055,0.10); part.CFrame=CFrame.new(pos)*CFrame.Angles(0,-angle-math.pi*0.5,0); part.Transparency=0.18
        end
    end
    RunService.RenderStepped:Connect(function()
        if collapsed or not selectedRow then return end
        renderRing(aggroParts,selectedRow.model,tonumber(selectedRow.aggroRadius) or 0,0.045)
        renderRing(attackParts,selectedRow.model,tonumber(selectedRow.attackRadius) or 0,0.085)
    end)

    task.spawn(function()
        while gui.Parent do refreshCatalog(); task.wait(POLL_SECONDS) end
    end)
    gui.Destroying:Connect(function() aggroFolder:Destroy(); attackFolder:Destroy() end)
end

function MonsterDebugController.Start()
    if started or not RunService:IsStudio() then return end
    started=true
    task.spawn(createGui)
end

return table.freeze(MonsterDebugController)
