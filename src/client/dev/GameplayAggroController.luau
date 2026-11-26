-- Named-species editor, local non-colliding radius previews; explicit Sync only.
local Players=game:GetService("Players")
local RS=game:GetService("ReplicatedStorage")
local RunService=game:GetService("RunService")
local HttpService=game:GetService("HttpService")
local Shared=RS:WaitForChild("Game1Shared")
local Balance=require(Shared:WaitForChild("balance"):WaitForChild("Balance"))
local Access=require(Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local Dock=require(script.Parent:WaitForChild("StudioDebugDock"))
local Controller={}
local started=false
local player=Players.LocalPlayer
local function text(parent,kind,value,x,y,w,h)
    local item=Instance.new(kind)
    item.Text=value; item.Font=Enum.Font.Gotham; item.TextSize=13; item.TextColor3=Color3.fromRGB(235,240,245)
    item.BackgroundColor3=Color3.fromRGB(44,56,66); item.BorderSizePixel=0
    item.Position=UDim2.fromOffset(x,y); item.Size=UDim2.fromOffset(w,h); item.Parent=parent
    if kind=="TextLabel" then item.BackgroundTransparency=1; item.TextXAlignment=Enum.TextXAlignment.Left end
    return item
end
-- Closed, low perimeter only: no floor disc, cap, collision or replicated parts.
local RING_SEGMENTS=96
local RING_HEIGHT=.24
local RING_WIDTH=.12
local RING_ALPHA=.34
local ACTIVE_COLOR=Color3.fromRGB(239,70,70)
local PASSIVE_COLOR=Color3.fromRGB(145,155,165)

local function makeRing()
    local model=Instance.new("Model")
    model.Name="GameplayAggroPreview"
    model.WorldPivot=CFrame.identity
    local segments={}
    for index=1,RING_SEGMENTS do
        local part=Instance.new("Part")
        part.Name="Outline"; part.Anchored=true; part.CanCollide=false; part.CanTouch=false; part.CanQuery=false
        part.CastShadow=false; part.Material=Enum.Material.Neon; part.Transparency=RING_ALPHA
        part.Parent=model; segments[index]=part
    end
    return {model=model,segments=segments}
end

local function updateRing(ring,center,radius,aggressive)
    if ring.radius~=radius then
        local pivot=ring.model:GetPivot()
        local halfAngle=math.pi/RING_SEGMENTS
        local apothem=radius*math.cos(halfAngle)
        local chord=math.max(.05,2*radius*math.sin(halfAngle)+.015)
        for index,part in ipairs(ring.segments) do
            local angle=(index-.5)*2*halfAngle
            local radial=Vector3.new(math.cos(angle),0,math.sin(angle))
            local tangent=Vector3.new(-radial.Z,0,radial.X)
            part.Size=Vector3.new(chord,RING_HEIGHT,RING_WIDTH)
            part.CFrame=pivot*CFrame.fromMatrix(radial*apothem,tangent,Vector3.yAxis)
        end
        ring.radius=radius
    end
    if ring.aggressive~=aggressive then
        local color=if aggressive then ACTIVE_COLOR else PASSIVE_COLOR
        for _,part in ipairs(ring.segments) do part.Color=color end
        ring.aggressive=aggressive
    end
    if ring.center~=center then
        ring.model:PivotTo(CFrame.new(center)); ring.center=center
    end
    if not ring.model.Parent then ring.model.Parent=workspace end
end

function Controller.Start()
    if started or not RunService:IsStudio() or not Access.ClientAllowed() then return end
    started=true
    local gui=Instance.new("ScreenGui"); gui.Name="Game1GameplayAggroGui"; gui.ResetOnSpawn=false; gui.Parent=player:WaitForChild("PlayerGui")
    local launch=text(gui,"TextButton","AG",0,0,44,44)
    local panel=Instance.new("Frame"); panel.Name="Panel"; panel.BackgroundColor3=Color3.fromRGB(22,29,38); panel.BorderSizePixel=0
    panel.Size=UDim2.fromOffset(360,440); panel.Visible=false; panel.Active=true; panel.Parent=gui
    text(panel,"TextLabel","MONSTER AGGRO · studs",10,4,280,28)
    local close=text(panel,"TextButton","×",318,4,32,28)
    local preview=text(panel,"TextButton","✓ Show radii",10,36,132,28)
    local sync=text(panel,"TextButton","Sync",254,36,96,28)
    local status=text(panel,"TextLabel","GP · current zone · stays visible when closed",10,68,340,30); status.TextWrapped=true
    local body=Instance.new("ScrollingFrame"); body.BackgroundTransparency=1; body.BorderSizePixel=0; body.Position=UDim2.fromOffset(10,100)
    body.Size=UDim2.new(1,-20,1,-110); body.AutomaticCanvasSize=Enum.AutomaticSize.Y; body.CanvasSize=UDim2.new(); body.ScrollBarThickness=5; body.Parent=panel
    local layout=Instance.new("UIListLayout"); layout.Padding=UDim.new(0,3); layout.Parent=body
    local entries,names={},{}
    for _,row in ipairs(Balance.Monsters) do
        if row.nameEn~="" and not entries[row.nameEn] then
            entries[row.nameEn]={nameEn=row.nameEn,oldRadius=row.aggroRadiusStuds,oldAggressive=row.aggressive,radius=row.aggroRadiusStuds,aggressive=row.aggressive}
            table.insert(names,row.nameEn)
        end
    end
    table.sort(names)
    local pending=nil
    local inputs={}
    for _,name in ipairs(names) do
        local entry=entries[name]
        local row=Instance.new("Frame"); row.Name=name; row.BackgroundTransparency=1; row.Size=UDim2.new(1,-6,0,31); row.Parent=body
        local caption=text(row,"TextLabel",name,0,0,196,30); caption.TextTruncate=Enum.TextTruncate.AtEnd
        local input=text(row,"TextBox",tostring(entry.radius),196,0,64,30); input.ClearTextOnFocus=false
        local toggle=text(row,"TextButton",if entry.aggressive then "✓ Aggro" else "Passive",264,0,66,30); toggle.TextSize=11
        inputs[name]=input
        input.FocusLost:Connect(function()
            local n=tonumber((input.Text:gsub(",",".")))
            if not pending and n and n==n and n>=0 and n<=10000 then entry.radius=n end
            input.Text=tostring(entry.radius)
        end)
        toggle.Activated:Connect(function() if pending then return end; entry.aggressive=not entry.aggressive; toggle.Text=if entry.aggressive then "✓ Aggro" else "Passive" end)
    end
    local show=true
    preview.Activated:Connect(function() show=not show; preview.Text=if show then "✓ Show radii" else "Show radii" end)
    local playerGui=player:WaitForChild("PlayerGui")
    local openAttribute="Game1DebugPanelOpen"
    launch.Activated:Connect(function() playerGui:SetAttribute(openAttribute,if panel.Visible then "" else "AG") end)
    close.Activated:Connect(function() if playerGui:GetAttribute(openAttribute)=="AG" then playerGui:SetAttribute(openAttribute,"") end end)
    playerGui:GetAttributeChangedSignal(openAttribute):Connect(function() panel.Visible=playerGui:GetAttribute(openAttribute)=="AG" end)
    Dock.Bind("AG",launch,panel,360,true)
    local folder=RS:WaitForChild("Game1GameplayAggroSync",20)
    local remote=RS:WaitForChild("Game1Remotes"):WaitForChild("SyncGameplayAggro",20)
    if not folder or not remote then status.Text="Sync service unavailable"; return end
    local function receipt()
        if not pending then return end
        local raw=folder:GetAttribute("Result")
        if type(raw)~="string" then return end
        local ok,data=pcall(HttpService.JSONDecode,HttpService,raw)
        if not ok or type(data)~="table" or data.nonce~=pending.nonce then return end
        if data.ok then
            for _,row in ipairs(pending.changes) do local e=entries[row.nameEn]; e.oldRadius=row.radius; e.oldAggressive=row.aggressive end
            status.Text="Saved to Database · Rojo Sync for next Play"
        else status.Text="Not saved: "..tostring(data.error) end
        pending=nil; sync.Active=true
    end
    folder:GetAttributeChangedSignal("Result"):Connect(receipt)
    sync.Activated:Connect(function()
        if pending then return end
        if player:GetAttribute("Game1GameplayTestActive")~=true then status.Text="Enter GP first"; return end
        local changes={}
        for _,name in ipairs(names) do
            local e=entries[name]; local n=tonumber((inputs[name].Text:gsub(",",".")))
            if not n or n~=n or n<0 or n>10000 then status.Text="Invalid radius: "..name; return end
            e.radius=n
            if e.radius~=e.oldRadius or e.aggressive~=e.oldAggressive then table.insert(changes,table.clone(e)) end
        end
        if #changes==0 then status.Text="No changes"; return end
        pending={changes=changes}; status.Text="Syncing…"; sync.Active=false
        local ok,result=pcall(function() return remote:InvokeServer(changes) end)
        if not ok or not result or not result.ok then pending=nil; sync.Active=true; status.Text=if ok and result then tostring(result.error) else "Sync failed"; return end
        pending.nonce=result.nonce; receipt()
        local token=result.nonce
        task.delay(12,function() if pending and pending.nonce==token then pending=nil; sync.Active=true; status.Text="Live preview applied; no save receipt. Check Studio Bridge." end end)
    end)
    local rings={}
    local function clear()
        for model,ring in pairs(rings) do ring.model:Destroy(); rings[model]=nil end
    end
    local elapsed=0
    local connection=RunService.Heartbeat:Connect(function(dt)
        elapsed+=dt; if elapsed<.12 then return end; elapsed=0
        local character=player.Character; local zone=character and character:GetAttribute("GameplayTestZone")
        if not show or not zone or zone<1 or zone>6 or player:GetAttribute("Game1GameplayTestActive")~=true then clear(); return end
        local monsters=workspace:FindFirstChild("Monsters"); local seen={}
        if monsters then for _,model in ipairs(monsters:GetChildren()) do
            local e=entries[tostring(model:GetAttribute("MonsterNameEn") or "")]
            local root=model:FindFirstChild("RootCollider") or model:FindFirstChild("HumanoidRootPart") or (model:IsA("Model") and model.PrimaryPart)
            if e and root and root:IsA("BasePart") and model:GetAttribute("Game1GameplayTestOwner")==player.UserId and model:GetAttribute("GameplayTestZone")==zone and model:GetAttribute("LifeState")=="Alive" and e.radius>0 then
                seen[model]=true
                local ring=rings[model]
                if not ring then ring=makeRing(); rings[model]=ring end
                local center=root.Position-Vector3.new(0,root.Size.Y/2-RING_HEIGHT/2-.025,0)
                updateRing(ring,center,e.radius,e.aggressive)
            end
        end end
        for model,ring in pairs(rings) do if not seen[model] then ring.model:Destroy(); rings[model]=nil end end
    end)
    gui.Destroying:Connect(function() connection:Disconnect(); clear() end)
end
return table.freeze(Controller)
