--!strict
-- Studio fixture only. Prompts submit fixed definitions to the existing owner-
-- and distance-validated GP panel dispatcher; the dummy is not a combat actor.
local Shared=game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Buffs=require(Shared:WaitForChild("combat"):WaitForChild("BuffDefinitions"))
local CharacterConfig=require(Shared:WaitForChild("character"):WaitForChild("CharacterConfig"))
local Presentation=require(script.Parent.Parent:WaitForChild("monster"):WaitForChild("MonsterCastPresentation"))
local Buffer={}
local GOLD=Color3.fromRGB(224,174,55)
local function part(parent: Instance,name: string,frame: CFrame,size: Vector3,color: Color3): Part
    local p=Instance.new("Part"); p.Name=name; p.Size=size; p.CFrame=frame; p.Anchored=true
    p.CanCollide=false; p.CanTouch=false; p.CanQuery=false; p.Material=Enum.Material.SmoothPlastic
    p.Color=color; p.Parent=parent; return p
end
local function weld(parent: BasePart, child: BasePart, name: string)
    local w=Instance.new("Weld"); w.Name=name; w.Part0=parent; w.Part1=child
    w.C0=parent.CFrame:ToObjectSpace(child.CFrame); w.Parent=parent
    child.Anchored=false; child.Massless=true
end
function Buffer.Build(parent: Instance,layout: any,onBuff: (Player,BasePart,any,()->())->())
    local model=Instance.new("Model"); model.Name="BufferDummy"; model.Parent=parent
    local base=layout.hub*CFrame.new(54,-CharacterConfig.RootAnchorOffset,-50)
    local root=part(model,"RootCollider",base*CFrame.new(0,2.5,0),Vector3.one,GOLD); root.Transparency=1
    model.PrimaryPart=root
    local torso=part(model,"Torso",base*CFrame.new(0,3.1,0),Vector3.new(1.65,2,0.85),GOLD)
    torso.Material=Enum.Material.Metal; weld(root,torso,"VisualRootWeld")
    local function body(name: string,x: number,y: number,size: Vector3)
        local p=part(model,name,base*CFrame.new(x,y,0),size,GOLD); p.Material=Enum.Material.Metal; weld(torso,p,name.."Weld")
    end
    body("Head",0,4.65,Vector3.new(1.1,1.1,1.1))
    body("LeftArm",-1.2,3.05,Vector3.new(.65,1.9,.7)); body("RightArm",1.2,3.05,Vector3.new(.65,1.9,.7))
    body("LeftLeg",-.43,1.15,Vector3.new(.72,1.8,.8)); body("RightLeg",.43,1.15,Vector3.new(.72,1.8,.8))
    local name=Instance.new("BillboardGui"); name.Name="BufferLabel"; name.Adornee=torso; name.StudsOffsetWorldSpace=Vector3.new(0,3,0); name.Size=UDim2.fromOffset(180,32); name.AlwaysOnTop=true; name.MaxDistance=70; name.Parent=model
    local label=Instance.new("TextLabel"); label.Size=UDim2.fromScale(1,1); label.BackgroundTransparency=1; label.Text="BUFFER · D"; label.Font=Enum.Font.GothamBold; label.TextScaled=true; label.TextColor3=GOLD; label.TextStrokeTransparency=.25; label.Parent=name
    local playing=false
    local function lift()
        if playing or not model.Parent then return end
        playing=true
        local pose=Presentation.Begin(model)
        task.spawn(function()
            local start=os.clock()
            while model.Parent do
                local t=math.clamp((os.clock()-start)/.9,0,1)
                Presentation.Step(pose,t,true)
                if t>=1 then break end
                task.wait(.03)
            end
            Presentation.Finish(pose); playing=false
        end)
    end
    for i,row in ipairs(Buffs.Rows) do
        local post=part(model,"Buff_"..row.effect,base*CFrame.new((i-2.5)*5.5,1.5,5),Vector3.new(4,3,.65),row.color)
        local surface=Instance.new("SurfaceGui"); surface.Face=Enum.NormalId.Back; surface.CanvasSize=Vector2.new(240,150); surface.Parent=post
        local text=Instance.new("TextLabel"); text.Size=UDim2.fromScale(1,1); text.BackgroundTransparency=1; text.Font=Enum.Font.GothamBold; text.TextScaled=true; text.TextColor3=Color3.new(1,1,1); text.Text=row.name; text.Parent=surface
        local prompt=Instance.new("ProximityPrompt"); prompt.ActionText="Receive"; prompt.ObjectText=row.name.." · D"; prompt.MaxActivationDistance=8; prompt.RequiresLineOfSight=false; prompt.Parent=post
        prompt.Triggered:Connect(function(player)
            if not playing then onBuff(player,post,row,lift) end
        end)
    end
end
return table.freeze(Buffer)
