--!strict
-- Local, open-top aura: no hitbox, physics or opaque cap. All pieces are
-- short-lived and follow the current character throughout the cast.
local RunService=game:GetService("RunService")
local Debris=game:GetService("Debris")
local Shared=game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local CharacterConfig=require(Shared:WaitForChild("character"):WaitForChild("CharacterConfig"))
local Visuals={}
local SEGMENTS=24
local function playAura(root: BasePart, character: Model?, color: Color3, offset: number, maxHeight: number, baseRadius: number, fixed: boolean)
    local folder=Instance.new("Folder"); folder.Name="LocalBuffAura"; folder.Parent=workspace
    if fixed then root.Parent=folder end
    Debris:AddItem(folder,1.5)
    local segments={}
    for i=1,SEGMENTS do
        local p=Instance.new("Part"); p.Name="AuraWall"; p.Anchored=true; p.CanCollide=false; p.CanTouch=false; p.CanQuery=false; p.CastShadow=false
        p.Material=Enum.Material.Neon; p.Color=color; p.Transparency=1; p.Size=Vector3.new(.2,.1,.05); p.Parent=folder
        segments[i]=p
    end
    local attachment=Instance.new("Attachment"); attachment.Name="BuffSparks"; attachment.Position=Vector3.new(0,-offset+.15,0); attachment.Parent=root
    local sparks=Instance.new("ParticleEmitter"); sparks.Texture="rbxasset://textures/particles/sparkles_main.dds"; sparks.Color=ColorSequence.new(color)
    sparks.Rate=0; sparks.Lifetime=NumberRange.new(.55,1); sparks.Speed=NumberRange.new(4,8); sparks.Acceleration=Vector3.new(0,2,0)
    sparks.EmissionDirection=Enum.NormalId.Top; sparks.SpreadAngle=Vector2.new(30,30); sparks.LightEmission=.8
    sparks.Size=NumberSequence.new({NumberSequenceKeypoint.new(0,.18),NumberSequenceKeypoint.new(.3,.3),NumberSequenceKeypoint.new(1,0)})
    sparks.Transparency=NumberSequence.new({NumberSequenceKeypoint.new(0,.1),NumberSequenceKeypoint.new(.5,.25),NumberSequenceKeypoint.new(1,1)})
    sparks.LockedToPart=true; sparks.Parent=attachment; sparks:Emit(32); Debris:AddItem(attachment,1.2)
    local start=os.clock(); local connection: RBXScriptConnection
    connection=RunService.RenderStepped:Connect(function()
        local t=(os.clock()-start)/1.05
        if t>=1 or not root.Parent or not folder.Parent or (character and character:GetAttribute("LifeState")~="Alive") then
            connection:Disconnect(); folder:Destroy(); attachment:Destroy(); return
        end
        local rise=math.clamp(t/.45,0,1)
        local radius=baseRadius+1.1*rise; local height=math.max(.1,maxHeight*rise)
        local center=root.Position-Vector3.yAxis*offset+Vector3.yAxis*(height/2)
        local fade=math.clamp((t-.35)/.65,0,1)
        for i,p in ipairs(segments) do
            local angle=(i-1)*2*math.pi/SEGMENTS; local dir=Vector3.new(math.cos(angle),0,math.sin(angle))
            p.Size=Vector3.new(2*radius*math.tan(math.pi/SEGMENTS)*.96,height,.06)
            p.CFrame=CFrame.lookAt(center+dir*radius,center); p.Transparency=.63+.37*fade
        end
    end)
end
function Visuals.Play(character: Model, color: Color3)
    local root=character:FindFirstChild("RootCollider")
    if not root or not root:IsA("BasePart") then return end
    playAura(root,character,color,CharacterConfig.RootAnchorOffset,5.2,1.7,false)
end
-- Fixed world-space aura: departure never follows the recalled monster.
function Visuals.PlayAt(foot: Vector3, color: Color3, height: number, radius: number)
    local root=Instance.new("Part"); root.Name="AuraOrigin"; root.Anchored=true
    root.Transparency=1; root.CanCollide=false; root.CanTouch=false; root.CanQuery=false; root.CastShadow=false
    root.Position=foot
    playAura(root,nil,color,0,height,radius,true)
end
return table.freeze(Visuals)
