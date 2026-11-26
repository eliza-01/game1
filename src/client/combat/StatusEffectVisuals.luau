--!strict
-- Local presentation of server-owned effects. No damage, movement or collision authority.
local Players=game:GetService("Players")
local RunService=game:GetService("RunService")
local TweenService=game:GetService("TweenService")
local Debris=game:GetService("Debris")
local Visuals={}
local started=false
local random=Random.new()
local function part(parent: Instance,name: string,color: Color3): Part
    local p=Instance.new("Part"); p.Name=name; p.Color=color; p.Anchored=true; p.Massless=true
    p.CanCollide=false; p.CanQuery=false; p.CanTouch=false; p.CastShadow=false
    p.Material=Enum.Material.SmoothPlastic; p.Parent=parent; return p
end
local function glyph(parent: Instance,text: string,pos: UDim2,size: UDim2,color: Color3): TextLabel
    local label=Instance.new("TextLabel"); label.Text=text; label.Position=pos; label.Size=size
    label.BackgroundTransparency=1; label.TextColor3=color; label.TextScaled=true; label.Font=Enum.Font.GothamBlack
    label.TextStrokeTransparency=.2; label.TextStrokeColor3=Color3.new(0,0,0); label.Parent=parent; return label
end
local function bonePoint(model: Model,root: BasePart): Vector3
    local bone=model:FindFirstChild("spine_02",true) or model:FindFirstChild("spine_01",true)
    return if bone and bone:IsA("Bone") then bone.TransformedWorldCFrame.Position else root.Position
end
function Visuals.Start()
    if started then return end; started=true
    local player=Players.LocalPlayer
    local model: Model?=nil; local folder: Folder?=nil
    local cloud: Part?=nil; local smoke: ParticleEmitter?=nil; local block: Part?=nil
    local billboard: BillboardGui?=nil; local eyes: TextLabel?=nil; local mouth: TextLabel?=nil; local stun: TextLabel?=nil
    local boots: {[MeshPart]: Color3}={}
    local nextPoison,nextBleed,rootSince=0,0,0
    local function restoreBoots()
        for mesh,color in pairs(boots) do if mesh.Parent then mesh.Color=color end end
        table.clear(boots)
    end
    local function clear()
        restoreBoots()
        if folder then folder:Destroy() end
        if billboard then billboard:Destroy() end
        folder=nil; cloud=nil; smoke=nil; block=nil; billboard=nil; eyes=nil; mouth=nil; stun=nil
        model=nil; nextPoison=0; nextBleed=0; rootSince=0
    end
    player.CharacterRemoving:Connect(function(character) if model==character then clear() end end)
    local elapsed=0
    RunService.Heartbeat:Connect(function(dt)
        elapsed+=dt; if elapsed<.08 then return end; elapsed=0
        local character=player.Character
        if not character or character:GetAttribute("LifeState")~="Alive" then if model then clear() end; return end
        local raw=character:GetAttribute("ActiveSkillEffects")
        if type(raw)~="string" or raw=="" then if model then clear() end; return end
        local root=character:FindFirstChild("RootCollider")
        if not root or not root:IsA("BasePart") then return end
        if model~=character then clear(); model=character end
        if not folder then folder=Instance.new("Folder"); folder.Name="Game1LocalStatusVisuals"; folder.Parent=workspace end
        local targetFolder=assert(folder)
        local effects={}; for _,name in ipairs(string.split(raw," · ")) do effects[name]=true end
        local now=os.clock()
        if effects.Poison then
            if not cloud then
                cloud=part(targetFolder,"PoisonCloud",Color3.fromRGB(99,185,56)); cloud.Size=Vector3.new(.2,.2,.2); cloud.Transparency=1
                smoke=Instance.new("ParticleEmitter"); smoke.Texture="rbxasset://textures/particles/smoke_main.dds"
                smoke.Color=ColorSequence.new(Color3.fromRGB(117,211,61),Color3.fromRGB(45,112,40))
                smoke.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,.6),NumberSequenceKeypoint.new(1,3.2)})
                smoke.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.28),NumberSequenceKeypoint.new(1,1)})
                smoke.Lifetime=NumberRange.new(.9,1.6); smoke.Speed=NumberRange.new(.7,2); smoke.SpreadAngle=Vector2.new(180,180)
                smoke.Rate=0; smoke.RotSpeed=NumberRange.new(-65,65); smoke.Parent=cloud
            end
            cloud.Position=bonePoint(character,root)
            if now>=nextPoison then assert(smoke):Emit(18); nextPoison=now+3 end
        else
            if cloud then cloud:Destroy(); cloud=nil; smoke=nil end; nextPoison=0
        end
        if effects.Bleed and now>=nextBleed then
            nextBleed=now+.8
            local center=bonePoint(character,root)
            for i=1,5 do
                local drop=part(targetFolder,"BleedDrop",Color3.fromRGB(178,23,28)); drop.Shape=Enum.PartType.Ball
                drop.Size=Vector3.new(.12,.2,.12); drop.Position=center
                local angle=random:NextNumber(0,2*math.pi); local radius=random:NextNumber(.8,2.1)
                local destination=center+Vector3.new(math.cos(angle)*radius,-random:NextNumber(.7,1.7),math.sin(angle)*radius)
                TweenService:Create(drop,TweenInfo.new(.48,Enum.EasingStyle.Quad,Enum.EasingDirection.In),{Position=destination,Transparency=1}):Play()
                Debris:AddItem(drop,.6)
            end
        elseif not effects.Bleed then nextBleed=0 end
        if effects.Root then
            if not block then
                block=part(targetFolder,"RootMarker",Color3.fromRGB(105,67,40)); block.Material=Enum.Material.Ground; rootSince=now
                block.Size=Vector3.new(math.max(1.7,root.Size.X),1.15,math.max(1.7,root.Size.Z))
            end
            local params=RaycastParams.new(); params.FilterType=Enum.RaycastFilterType.Exclude; params.FilterDescendantsInstances={character,targetFolder}
            local ground=workspace:Raycast(root.Position,Vector3.new(0,-12,0),params)
            local floor=if ground then ground.Position.Y else root.Position.Y-root.Size.Y/2
            local lift=math.clamp((now-rootSince)/.35,0,1)
            block.Position=Vector3.new(root.Position.X,floor+block.Size.Y*(lift-.5),root.Position.Z)
        elseif block then block:Destroy(); block=nil end
        if effects.Slow then
            if next(boots)==nil then
                for _,mesh in ipairs(character:GetDescendants()) do
                    if mesh:IsA("MeshPart") and mesh:GetAttribute("CharacterPartSlot")=="boots" then boots[mesh]=mesh.Color end
                end
            end
            local tint=Color3.fromRGB(225,26,30):Lerp(Color3.fromRGB(141,17,19),(math.sin(now*5)+1)/2)
            for mesh in pairs(boots) do if mesh.Parent then mesh.Color=tint end end
        elseif next(boots) then restoreBoots() end
        if effects.Silence or effects.Stun then
            if not billboard then
                billboard=Instance.new("BillboardGui"); billboard.Name="Game1StatusGlyph"; billboard.Adornee=root
                billboard.Size=UDim2.fromOffset(64,54); billboard.StudsOffsetWorldSpace=Vector3.new(0,root.Size.Y/2+2.1,0)
                billboard.AlwaysOnTop=true; billboard.MaxDistance=80; billboard.Parent=root
                eyes=glyph(billboard,"● ●",UDim2.fromScale(0,0),UDim2.fromScale(1,.42),Color3.fromRGB(245,238,255))
                mouth=glyph(billboard,"×",UDim2.fromScale(.2,.32),UDim2.fromScale(.6,.48),Color3.fromRGB(245,238,255)); mouth.Rotation=90
                stun=glyph(billboard,"✦ ✦",UDim2.fromScale(0,.7),UDim2.fromScale(1,.3),Color3.fromRGB(255,210,73))
            end
            assert(eyes).Visible=effects.Silence==true; assert(mouth).Visible=effects.Silence==true; assert(stun).Visible=effects.Stun==true
        elseif billboard then billboard:Destroy(); billboard=nil; eyes=nil; mouth=nil; stun=nil end
    end)
end
return table.freeze(Visuals)
