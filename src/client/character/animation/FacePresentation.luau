--!strict
-- Sole owner of local eye sizing/visibility and four-bone procedural overlays.
-- Static display copies live outside the skinned Model to avoid double skinning.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Idle = require(ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("character"):WaitForChild("FaceIdleDefaults"))
local Presenter = {}
Presenter.__index = Presenter
-- These are the deform Bones on the published rig and in the exported
-- emotion KeyframeSequences, not optional *_ctrl_* authoring helpers.
local faceBones = {eye_l="face_eye_l",eye_r="face_eye_r",
    brow_l="face_brow_l",brow_r="face_brow_r"}
local variants = {happy=true,happy_sharp_caret=true,happy_thick_caret=true,nausea_wave=true}

local function facePartsBySlot(character: Model): { [string]: MeshPart }
    local found: { [string]: MeshPart } = {}
    for _, object in character:GetDescendants() do
        if object:IsA("MeshPart") then
            local slot = object:GetAttribute("CharacterPartSlot")
            if typeof(slot) == "string" and faceBones[slot] then
                -- A slot can only have one geometry identity in a resolved recipe.
                if found[slot] then return {} end
                found[slot] = object
            end
        end
    end
    return found
end

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
    local parts=facePartsBySlot(character)
    for slot,boneName in faceBones do
        local original=parts[slot]
        if original then
            local bone=carrier:FindFirstChild(boneName,true)
            if not bone or not bone:IsA("Bone") then return nil end
            entries[slot]={original=original,bone=bone,size=original.Size,
                offset=bone.WorldCFrame:ToObjectSpace(original.CFrame),transparency=original.LocalTransparencyModifier}
        end
    end
    if not next(entries) then return nil end
    local head=carrier:FindFirstChild("face_head",true)
    local left,right=entries.eye_l,entries.eye_r
    local separation=if left and right then (left.bone.WorldPosition-right.bone.WorldPosition).Magnitude else 0
    local folder=Instance.new("Model");folder.Name="face_presentation";folder.Parent=workspace
    for _,entry in entries do
        entry.mesh=displayCopy(entry.original,folder)
        entry.original.LocalTransparencyModifier=1
    end
    local self=setmetatable({character=character,entries=entries,folder=folder,temporary={},state="idle",
        spin=0,angle=0,clock=0,blink=nil,base={},destroyed=false,assets=assets,
        head=if head and head:IsA("Bone") then head else nil,separation=separation,phase=nil},Presenter)
    return self
end

function Presenter:SetIdlePhase(phase: number?)
    self.phase=phase
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
    if name~="spiral" and not variants[name] then return end
    local assets=self.assets or ReplicatedStorage:FindFirstChild("Game1FaceAssets")
    for _,side in {"l","r"} do
        local entry=self.entries["eye_"..side]
        if entry then
            -- Derive optional effect geometry from the actual equipped eye identity.
            -- Example: human_female_m001_eye_l_spiral (not a hard-coded eyes_01).
            local templateName=entry.original.Name.."_"..name
            local template=assets and assets:FindFirstChild(templateName)
            if not template or not template:IsA("BasePart") or typeof(template:GetAttribute("FaceLocalCFrame"))~="CFrame" then
                self.character:SetAttribute("FaceMissingMesh",templateName)
            else
                self.temporary[side]=displayCopy(template,self.folder)
            end
        end
    end
end

function Presenter:Reset()
    self:BeforeAnimation()
    self:ClearVariants()
    self.state="idle";self.eyeSet="normal";self.spin=0;self.angle=0;self.clock=0;self.blink=nil;self.phase=nil
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
    local gaze=if self.phase and self.head and self.separation>0
        then self.head.TransformedWorldCFrame:VectorToWorldSpace(Idle.Offset(self.phase)*self.separation)
        else Vector3.zero
    for key,entry in self.entries do
        local bone=entry.bone
        self.base[bone]=bone.Transform
        local eye=string.sub(key,1,3)=="eye"
        -- Preserve the former combined-face idle motion with independent eyes.
        if eye and self.phase then
            local before=bone.TransformedWorldCFrame
            bone.Transform=bone.Transform*CFrame.new(before:VectorToObjectSpace(gaze))
        end
        local overlay=CFrame.identity
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
