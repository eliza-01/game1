--!strict
-- Sole owner of local eye sizing/visibility and four-bone procedural overlays.
-- Static display copies live outside the skinned Model to avoid double skinning.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Presenter = {}
Presenter.__index = Presenter
local names = {eye_l="eyes_01_l",eye_r="eyes_01_r",brow_l="eyebrows_01_l",brow_r="eyebrows_01_r"}
local variants = {happy="eyes_01_happy",happy_sharp_caret="eyes_01_happy_sharp_caret",
    happy_thick_caret="eyes_01_happy_thick_caret",nausea_wave="eyes_01_nausea_wave"}

local function displayCopy(source: BasePart, parent: Instance): BasePart
    local mesh = source:Clone()
    for _, child in mesh:GetChildren() do
        if not child:IsA("SurfaceAppearance") then child:Destroy() end
    end
    mesh.Anchored=true;mesh.CanCollide=false;mesh.CanTouch=false;mesh.CanQuery=false
    mesh.CastShadow=false;mesh.LocalTransparencyModifier=0;mesh.Parent=parent
    return mesh
end

function Presenter.new(character: Model, assets: Instance?)
    local carrier=character:FindFirstChild("rig_carrier",true)
    if not carrier then return nil end
    local entries={}
    for key,name in names do
        local original=character:FindFirstChild(name,true)
        local boneName=string.gsub(key,"eye_","face_eye_"):gsub("brow_","face_brow_")
        local bone=carrier:FindFirstChild(boneName,true)
        if not original or not original:IsA("BasePart") or not bone or not bone:IsA("Bone") then return nil end
        entries[key]={original=original,bone=bone,size=original.Size,
            offset=bone.WorldCFrame:ToObjectSpace(original.CFrame),transparency=original.LocalTransparencyModifier}
    end
    local folder=Instance.new("Model");folder.Name="face_presentation";folder.Parent=workspace
    for _,entry in entries do
        entry.mesh=displayCopy(entry.original,folder)
        entry.original.LocalTransparencyModifier=1
    end
    local self=setmetatable({character=character,entries=entries,folder=folder,temporary={},state="idle",
        spin=0,angle=0,clock=0,blink=nil,base={},destroyed=false,assets=assets},Presenter)
    return self
end

function Presenter:BeforeAnimation()
    for bone,transform in self.base do
        if bone.Parent then bone.Transform=transform end
    end
    table.clear(self.base)
end

function Presenter:ClearVariants()
    for _,part in self.temporary do part:Destroy() end
    table.clear(self.temporary)
end

function Presenter:SetEyes(name: string)
    self:ClearVariants()
    self.character:SetAttribute("FaceMissingMesh",nil)
    self.eyeSet=name
    local templateName=if name=="spiral" then "eyes_01_spiral" else variants[name]
    if not templateName then return end
    local assets=self.assets or ReplicatedStorage:FindFirstChild("Game1FaceAssets")
    local template=assets and assets:FindFirstChild(templateName)
    -- A template carries its authored bone-local offset. Never guess its axes.
    if not template or not template:IsA("BasePart") or typeof(template:GetAttribute("FaceLocalCFrame"))~="CFrame" then
        self.character:SetAttribute("FaceMissingMesh",templateName)
        return
    end
    self.character:SetAttribute("FaceMissingMesh",nil)
    for _,side in {"l","r"} do
        self.temporary[side]=displayCopy(template,self.folder)
    end
end

function Presenter:Reset()
    self:BeforeAnimation()
    self:ClearVariants()
    self.state="idle";self.eyeSet="normal";self.spin=0;self.angle=0;self.clock=0;self.blink=nil
end

function Presenter:Event(event: any, age: number?, upcomingDelta: number?)
    local p=event.parameters or {}
    local elapsed=age or 0
    local upcoming=upcomingDelta or 0
    if event.name=="blink" then self.blink={start=self.clock+upcoming-elapsed,duration=p.duration or .16,side=p.side or "both"}
    elseif event.name=="face_state" then
        self.state=p.name;self.clock=elapsed-upcoming
        self:SetEyes(if variants[p.name] then p.name else "normal")
    elseif event.name=="face_reset" then self:Reset()
    elseif event.name=="eyes_set" then self:SetEyes(p.name)
    elseif event.name=="eyes_spin_start" then
        self.spin=math.rad(p.degrees_per_second or 180);self.angle=self.spin*(elapsed-upcoming)
    elseif event.name=="eyes_spin_stop" then self.spin=0 end
end

function Presenter:Step(delta: number, procedural: boolean?)
    if self.destroyed then return end
    self.clock+=math.max(0,delta);self.angle+=self.spin*math.max(0,delta)
    local blink=self.blink
    local closure=0
    if blink then
        local t=(self.clock-blink.start)/blink.duration
        if t>=1 then self.blink=nil else closure=math.sin(math.clamp(t,0,1)*math.pi)^2 end
    end
    for key,entry in self.entries do
        local bone=entry.bone
        self.base[bone]=bone.Transform
        local overlay=CFrame.identity
        local eye=string.sub(key,1,3)=="eye"
        local side=string.sub(key,-1)
        local sign=if side=="l" then 1 else -1
        -- Bone motion in native emotions takes precedence over procedural presets.
        if procedural then
            if self.state=="indignant_surprise" and side=="l" then
                overlay=CFrame.new(0,entry.size.Y*.4,0)*CFrame.Angles(0,0,if eye then 0 else math.rad(12))
            elseif self.state=="combat_idle" and not eye then
                overlay=CFrame.Angles(0,0,math.rad(-sign*12))
            elseif self.state=="sad" and not eye then overlay=CFrame.Angles(0,0,math.rad(sign*12)) end
        end
        bone.Transform=bone.Transform*overlay
        local scale=Vector3.one
        if eye then
            local closed=if self.state=="closed" then 1 else (if blink and (blink.side=="both" or blink.side==side) then closure else 0)
            scale=Vector3.new(1+.35*closed,1-.92*closed,1)
            if self.state=="sad" then scale*=Vector3.new(1,.75,1) end
        end
        entry.mesh.Size=entry.size*scale
        entry.mesh.CFrame=bone.TransformedWorldCFrame*entry.offset
        local effect=eye and self.temporary[side]
        entry.mesh.LocalTransparencyModifier=if effect then 1 else 0
        if effect then
            local phase=if side=="r" and self.eyeSet=="spiral" then math.pi else 0
            effect.CFrame=bone.TransformedWorldCFrame*(effect:GetAttribute("FaceLocalCFrame") :: CFrame)*CFrame.Angles(0,0,self.angle+phase)
        end
    end
end

function Presenter:Destroy()
    if self.destroyed then return end
    self:Reset();self.destroyed=true
    for _,entry in self.entries do
        if entry.original.Parent then entry.original.LocalTransparencyModifier=entry.transparency end
    end
    self.folder:Destroy()
end
return Presenter
