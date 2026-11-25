--!strict
-- Studio Play-only live layout control; the plugin relays drafts to Control
-- Center's UI Options. Nothing here writes to the saved configuration.
local Players = game:GetService("Players")
local TextService = game:GetService("TextService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Access = require(ReplicatedStorage:WaitForChild("Game1Shared")
    :WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
local Contract = require(ReplicatedStorage:WaitForChild("Game1Shared")
    :WaitForChild("world"):WaitForChild("UiPresentationContract"))
local Dock = require(script.Parent:WaitForChild("StudioDebugDock"))
local MobileLayout = require(script.Parent.Parent:WaitForChild("character"):WaitForChild("mobile"):WaitForChild("MobileLayout"))
local Settings = require(script.Parent.Parent:WaitForChild("world"):WaitForChild("UiPresentationSettings"))
local ResourceFeedback = require(script.Parent.Parent:WaitForChild("world"):WaitForChild("FloatingResourceFeedback"))

local Debug = {}
local started = false
local BG = Color3.fromRGB(17, 23, 31)
local RAISED = Color3.fromRGB(32, 44, 56)
local INK = Color3.fromRGB(240, 247, 250)
local MUTED = Color3.fromRGB(168, 186, 199)
local ACTIVE = Color3.fromRGB(81, 211, 171)
local GROUPS = {"interaction", "status", "notification", "resource"}
local TITLES = {interaction="INTERACTION", status="FIRE / FOOD", notification="NOTICES", resource="RESOURCES"}
local FIELDS = {
    interaction={"offsetXPx", "offsetYPx", "widthPx", "fontPx"},
    status={"offsetXPx", "offsetYPx", "titleFontPx", "labelFontPx", "timerFontPx"},
    notification={"offsetXPx", "offsetYPx", "fontPx", "paddingPx", "durationSeconds"},
    resource={"offsetXPx", "offsetYPx", "fontPx", "paddingPx", "risePx", "durationSeconds"},
}

local function make(parent: Instance, kind: string, fields: {[string]: any}): any
    local item = Instance.new(kind)
    for name, value in pairs(fields) do (item :: any)[name] = value end
    item.Parent = parent
    return item
end
local function corner(parent: Instance, px: number)
    make(parent, "UICorner", {CornerRadius=UDim.new(0, px)})
end
local function button(parent: Instance, text: string, w: number, h: number): TextButton
    local item = make(parent, "TextButton", {Text=text, Size=UDim2.fromOffset(w,h),
        Font=Enum.Font.GothamSemibold, TextSize=11, BackgroundColor3=RAISED,
        TextColor3=INK, BorderSizePixel=0, AutoButtonColor=true})
    corner(item, 6)
    return item
end
local function label(parent: Instance, text: string, x: number, y: number, w: number): TextLabel
    return make(parent, "TextLabel", {Text=text, BackgroundTransparency=1,
        Position=UDim2.fromOffset(x,y),Size=UDim2.fromOffset(w,29),
        TextColor3=INK,TextXAlignment=Enum.TextXAlignment.Left,
        Font=Enum.Font.Gotham,TextSize=12})
end
local function clone(source: any): any
    if type(source) ~= "table" then return source end
    local result = {}
    for key, value in pairs(source) do result[key]=clone(value) end
    return result
end
local function numeric(value: number): string
    return string.format("%.2f",value):gsub("0+$",""):gsub("%.$","")
end

local function previewSurface(playerGui: Instance): (ScreenGui, Frame, TextLabel)
    local screen = make(playerGui,"ScreenGui",{Name="Game1UiDebugPreview",
        ResetOnSpawn=false, DisplayOrder=34})
    -- Noninteractive sample is not a camera input blocker.
    screen:SetAttribute("WorldInputPassthrough",true)
    local card = make(screen,"Frame",{Name="Sample",Visible=false,
        Size=UDim2.fromOffset(272,78),BackgroundColor3=BG,BorderSizePixel=0,
        AnchorPoint=Vector2.new(0.5,0.5)})
    corner(card,10)
    make(card,"UIStroke",{Color=Color3.fromRGB(93,110,126),Transparency=0.3})
    local caption = make(card,"TextLabel",{BackgroundTransparency=1,
        Position=UDim2.fromOffset(10,7),Size=UDim2.new(1,-20,1,-14),
        TextColor3=INK,TextXAlignment=Enum.TextXAlignment.Center,
        TextWrapped=true,Font=Enum.Font.GothamSemibold,TextSize=14,
        Text="[E]  Разжечь огонь"})
    return screen,card,caption
end

function Debug.Start()
    if started or not Access.ClientAllowed() then return end
    started = true
    local player = Players.LocalPlayer
    local playerGui = player:WaitForChild("PlayerGui")
    local screen = make(playerGui,"ScreenGui",{Name="Game1UiPresentationDebug",
        ResetOnSpawn=false,DisplayOrder=42})
    local launcher = button(screen,"UI",44,44)
    launcher.Position = Dock.ButtonPosition("UI")
    local panel = make(screen,"Frame",{Name="UiPresentationDebugPanel",Visible=false,
        Position=Dock.WindowPosition("UI",356),Size=UDim2.fromOffset(356,452),
        BackgroundColor3=BG,BorderSizePixel=0})
    corner(panel,10)
    make(panel,"UIStroke",{Color=Color3.fromRGB(65,82,97),Transparency=0.15})
    label(panel,"UI PRESENTATION · LIVE PREVIEW",12,6,300)
    local close = button(panel,"×",26,26)
    close.Position=UDim2.fromOffset(318,9)
    local status = label(panel,"Not saved · Import in Control Center / Options",12,413,333)
    status.TextColor3 = MUTED
    status.TextSize = 10
    local previewScreen, sample, caption = previewSurface(playerGui)
    local activePreview = false
    local resourcePreview: BillboardGui? = nil
    local remote: RemoteEvent? = nil
    task.spawn(function()
        local remotes = ReplicatedStorage:WaitForChild("Game1Remotes",15)
        local found = remotes and remotes:WaitForChild("UiPresentationDebugChanged",10)
        if found and found:IsA("RemoteEvent") then remote=found end
    end)

    local device = Settings.RuntimeDevice()
    local group = "interaction"
    local drafts = {desktop=Settings.Saved("desktop"),mobile=Settings.Saved("mobile")}
    local deviceButtons: {[string]: TextButton} = {}
    local groupButtons: {[string]: TextButton} = {}
    local rows = make(panel,"Frame",{Name="Rows",BackgroundTransparency=1,
        Position=UDim2.fromOffset(12,123),Size=UDim2.fromOffset(332,245)})
    local restore = button(panel,"Stop preview",100,30)
    restore.Position=UDim2.fromOffset(12,376)
    local reset = button(panel,"Reset device",100,30)
    reset.Position=UDim2.fromOffset(120,376)
    local hint = label(panel,"The sample shows the selected window without gameplay.",12,349,335)
    hint.TextColor3 = MUTED
    hint.TextSize = 10
    local latest = 0

    local function showSample()
        if resourcePreview then resourcePreview:Destroy(); resourcePreview = nil end
        sample.Visible = activePreview and group ~= "resource"
        if not activePreview then return end
        local cfg = drafts[device][group]
        caption.Position=UDim2.fromOffset(10,7)
        caption.Size=UDim2.new(1,-20,1,-14)
        if group == "interaction" then
            if device == "mobile" then
                local bounds = MobileLayout.Context(previewScreen.AbsoluteSize.X, previewScreen.AbsoluteSize.Y, 70)
                sample.AnchorPoint=Vector2.new(1,1)
                sample.Position=UDim2.new(1,-bounds.x+cfg.offsetXPx,1,-bounds.y+cfg.offsetYPx)
                sample.Size=UDim2.fromOffset(math.min(cfg.widthPx,bounds.width),70)
                caption.Text="Разжечь огонь"
            else
                sample.AnchorPoint=Vector2.new(1,0.5)
                sample.Position=UDim2.new(1,-22+cfg.offsetXPx,0.5,cfg.offsetYPx)
                sample.Size=UDim2.fromOffset(cfg.widthPx,70)
                caption.Text="[E]  Разжечь огонь"
            end
            caption.TextSize=cfg.fontPx
        elseif group == "status" then
            sample.AnchorPoint=Vector2.new(0.5,1)
            sample.Position=UDim2.new(0.5,cfg.offsetXPx,1,-24+cfg.offsetYPx)
            sample.Size=UDim2.fromOffset(320,92)
            caption.TextSize=cfg.titleFontPx
            caption.Text="Огонь  ▰▰▰▰▱ 01:20\nБлюдо  ▰▰▱▱▱ 00:18"
        elseif group == "notification" then
            sample.AnchorPoint=Vector2.new(0.5,1)
            sample.Position=UDim2.new(0.5,cfg.offsetXPx,0.83,cfg.offsetYPx)
            caption.TextSize=cfg.fontPx
            caption.Text="Переход завершён"
            local measured = TextService:GetTextSize(caption.Text, cfg.fontPx, Enum.Font.GothamSemibold,
                Vector2.new(430 - cfg.paddingPx*2, 400))
            sample.Size=UDim2.fromOffset(measured.X+cfg.paddingPx*2, measured.Y+cfg.paddingPx*2)
            caption.Position=UDim2.fromOffset(cfg.paddingPx,cfg.paddingPx)
            caption.Size=UDim2.fromOffset(measured.X,measured.Y)
        else
            -- Live head-mounted sample; no resource event or server writes.
            resourcePreview = ResourceFeedback.Preview(cfg)
        end
    end
    local function preview()
        activePreview=true
        Settings.Preview(device,drafts[device])
        showSample()
        latest += 1
        local revision=latest
        local selectedDevice=device
        local snapshot=clone(drafts[device])
        status.Text="Live in Studio · sending draft"
        task.delay(0.22,function()
            if revision~=latest or not activePreview then return end
            if remote then
                remote:FireServer({device=selectedDevice,settings=snapshot})
                status.Text="Live preview · draft sent to Control Center"
            else
                status.Text="Live preview · bridge unavailable"
            end
        end)
    end
    local function stop()
        latest += 1
        activePreview=false
        sample.Visible=false
        if resourcePreview then resourcePreview:Destroy(); resourcePreview=nil end
        Settings.Preview(nil,nil)
        status.Text="Saved presentation restored; nothing persisted"
    end
    local render: () -> ()
    local function update(key: string, raw: any)
        local value=tonumber(raw)
        local range=Contract.Bounds[key]
        if not value or value~=value or value==math.huge or value==-math.huge then render(); return end
        value=math.clamp(value,range[1],range[2])
        if key ~= "durationSeconds" then value=math.floor(value+0.5) end
        drafts[device][group][key]=value
        render()
        preview()
    end
    render=function()
        for _, item in ipairs(rows:GetChildren()) do item:Destroy() end
        for key, item in pairs(deviceButtons) do
            item.BackgroundColor3=if key==device then ACTIVE else RAISED
            item.TextColor3=if key==device then BG else INK
        end
        for key, item in pairs(groupButtons) do
            item.BackgroundColor3=if key==group then ACTIVE else RAISED
            item.TextColor3=if key==group then BG else INK
        end
        for index,key in ipairs(FIELDS[group]) do
            local y=(index-1)*36
            local value=drafts[device][group][key]
            label(rows,key,0,y,126)
            local minus=button(rows,"−",29,30); minus.Position=UDim2.fromOffset(131,y)
            local edit=make(rows,"TextBox",{Position=UDim2.fromOffset(166,y),
                Size=UDim2.fromOffset(101,30),BackgroundColor3=RAISED,
                TextColor3=INK,Font=Enum.Font.Code,TextSize=12,
                ClearTextOnFocus=false,BorderSizePixel=0,Text=numeric(value)})
            corner(edit,6)
            local plus=button(rows,"+",29,30); plus.Position=UDim2.fromOffset(273,y)
            local step=if key=="durationSeconds" then 0.1 else 1
            minus.Activated:Connect(function() update(key,value-step) end)
            plus.Activated:Connect(function() update(key,value+step) end)
            edit.FocusLost:Connect(function() update(key,edit.Text) end)
        end
    end
    for index,key in ipairs({"desktop","mobile"}) do
        local item=button(panel,if key=="desktop" then "PC" else "MOBILE",152,30)
        item.Position=UDim2.fromOffset(12+(index-1)*166,44)
        deviceButtons[key]=item
        item.Activated:Connect(function() device=key;render();preview() end)
    end
    for index,key in ipairs(GROUPS) do
        local item=button(panel,TITLES[key],76,30)
        item.Position=UDim2.fromOffset(12+(index-1)*84,83)
        groupButtons[key]=item
        item.Activated:Connect(function() group=key;render();preview() end)
    end
    reset.Activated:Connect(function()
        drafts[device]=Settings.Saved(device)
        render();preview()
    end)
    restore.Activated:Connect(stop)
    local function syncPanel()
        local open = playerGui:GetAttribute("Game1DebugPanelOpen") == "UI"
        if panel.Visible == open then return end
        panel.Visible = open
        if open then render(); preview() else stop() end
    end
    launcher.Activated:Connect(function()
        playerGui:SetAttribute("Game1DebugPanelOpen", if panel.Visible then "" else "UI")
    end)
    close.Activated:Connect(function()
        if playerGui:GetAttribute("Game1DebugPanelOpen") == "UI" then playerGui:SetAttribute("Game1DebugPanelOpen", "") end
    end)
    playerGui:GetAttributeChangedSignal("Game1DebugPanelOpen"):Connect(syncPanel)
    Dock.Bind("UI", launcher, panel, 356)
    render(); syncPanel()
end
return table.freeze(Debug)
