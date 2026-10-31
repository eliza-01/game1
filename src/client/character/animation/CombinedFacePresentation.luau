--!strict
-- Neutral idle for the existing two-eye MeshPart. One local display copy;
-- gaze still moves the existing two control bones. No mesh publication needed.
-- Retire this adapter when the combined component is replaced by independent parts.
local Idle=require(game:GetService("ReplicatedStorage").Game1Shared.character.FaceIdleDefaults)
local Presentation={}
Presentation.__index=Presentation

function Presentation.new(character: Model)
    local source=character:FindFirstChild("eyes_01",true)
    local carrier=character:FindFirstChild("rig_carrier",true)
    if not source or not source:IsA("BasePart") or not carrier then return nil end
    local head=carrier:FindFirstChild("face_head",true)
    local left=carrier:FindFirstChild("face_eye_ctrl_l",true) or carrier:FindFirstChild("face_eye_l",true)
    local right=carrier:FindFirstChild("face_eye_ctrl_r",true) or carrier:FindFirstChild("face_eye_r",true)
    if not head or not head:IsA("Bone") or not left or not left:IsA("Bone") or not right or not right:IsA("Bone") then return nil end
    local folder=Instance.new("Model");folder.Name="face_presentation"
    local mesh=source:Clone()
    for _,child in mesh:GetChildren() do if not child:IsA("SurfaceAppearance") then child:Destroy() end end
    mesh.Anchored=true;mesh.CanCollide=false;mesh.CanTouch=false;mesh.CanQuery=false;mesh.CastShadow=false
    mesh.LocalTransparencyModifier=0;mesh.Parent=folder
    local self=setmetatable({source=source,mesh=mesh,head=head,controls={left,right},base={},folder=folder,
        size=source.Size,visibility=source.LocalTransparencyModifier,offset=head.WorldCFrame:ToObjectSpace(source.CFrame),
        separation=(left.WorldPosition-right.WorldPosition).Magnitude,clock=0,state="idle",blink=nil,phase=nil,destroyed=false},Presentation)
    folder.Parent=workspace;source.LocalTransparencyModifier=1
    return self
end

function Presentation:BeforeAnimation()
    for bone,transform in self.base do if bone.Parent then bone.Transform=transform end end
    table.clear(self.base)
end

function Presentation:SetIdlePhase(phase: number?) self.phase=phase end

function Presentation:Reset()
    self:BeforeAnimation();self.clock=0;self.state="idle";self.blink=nil;self.phase=nil
end

function Presentation:Event(event: any,age: number?,upcoming: number?)
    local parameters=event.parameters or {}
    if event.name=="blink" then
        self.blink={start=self.clock+(upcoming or 0)-(age or 0),duration=parameters.duration or .16}
    elseif event.name=="face_state" then self.state=parameters.name
    elseif event.name=="face_reset" then self:Reset() end
end

function Presentation:Step(delta: number,_procedural: boolean?)
    if self.destroyed then return end
    self.clock+=math.max(0,delta)
    local gaze=if self.phase then Idle.Offset(self.phase)*self.separation else Vector3.zero
    local headWorld=self.head.TransformedWorldCFrame
    local worldOffset=headWorld:VectorToWorldSpace(gaze)
    local displacement=Vector3.zero
    for _,bone in self.controls do
        self.base[bone]=bone.Transform
        local before=bone.TransformedWorldCFrame
        bone.Transform=bone.Transform*CFrame.new(before:VectorToObjectSpace(worldOffset))
        displacement+=(bone.TransformedWorldCFrame.Position-before.Position)/2
    end
    local closure=if self.state=="closed" then 1 else 0
    if self.blink then
        local t=(self.clock-self.blink.start)/self.blink.duration
        if t>=1 then self.blink=nil else closure=math.sin(math.clamp(t,0,1)*math.pi)^2 end
    end
    self.mesh.Size=self.size*Vector3.new(1,1-.92*closure,1)
    self.mesh.CFrame=headWorld*self.offset+displacement
end

function Presentation:Destroy()
    if self.destroyed then return end
    self:Reset();self.destroyed=true
    if self.source.Parent then self.source.LocalTransparencyModifier=self.visibility end
    self.folder:Destroy()
end
return Presentation
