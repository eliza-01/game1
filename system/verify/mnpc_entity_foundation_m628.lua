-- Minimal deterministic engine double for the actual three MNPC modules.
-- Translation and yaw only; native welding and Humanoid motion are not emulated.
local V = {}; V.__index = V
function V.new(x,y,z) return setmetatable({X=x,Y=y,Z=z},V) end
function V.__add(a,b) return V.new(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
function V.__sub(a,b) return V.new(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
function V.__mul(a,b) return V.new(a.X*b,a.Y*b,a.Z*b) end
Vector3=V
local F={}
local function frame(p,yaw) return setmetatable({Position=p,yaw=yaw},F) end
F.__index=function(self,key)
    if key=='Rotation' then return frame(V.new(0,0,0),self.yaw) end
    return F[key]
end
function F.new(p) return frame(p or V.new(0,0,0),0) end
function F.Angles(_,y,__) return frame(V.new(0,0,0),y) end
local function rotate(v,a)
    return V.new(v.X*math.cos(a)+v.Z*math.sin(a),v.Y,-v.X*math.sin(a)+v.Z*math.cos(a))
end
function F:PointToWorldSpace(p) return self.Position+rotate(p,self.yaw) end
function F:ToObjectSpace(other) return frame(rotate(other.Position-self.Position,-self.yaw),other.yaw-self.yaw) end
function F.__mul(a,b) return frame(a:PointToWorldSpace(b.Position),a.yaw+b.yaw) end
function F.__add(a,b) return frame(a.Position+b,a.yaw) end
CFrame=F
local I={}; local methods={}
I.__index=function(self,key)
    if key=='Parent' then return rawget(self,'_parent') end
    return methods[key] or rawget(self,key)
end
I.__newindex=function(self,key,value)
    if key~='Parent' then rawset(self,key,value); return end
    local old=rawget(self,'_parent')
    if old then for i,c in ipairs(old.children) do if c==self then table.remove(old.children,i); break end end end
    rawset(self,'_parent',value)
    if value then table.insert(value.children,self) end
end
Instance={new=function(kind)
    return setmetatable({ClassName=kind,Name=kind,children={},attrs={},tags={},states={},pivot=F.new()},I)
end}
function methods:IsA(kind) return self.ClassName==kind or (kind=='BasePart' and (self.ClassName=='Part' or self.ClassName=='MeshPart')) end
function methods:GetChildren() local out={}; for i,c in ipairs(self.children) do out[i]=c end; return out end
function methods:GetDescendants()
    local out={}; local function visit(p) for _,c in ipairs(p.children) do table.insert(out,c); visit(c) end end
    visit(self); return out
end
function methods:FindFirstChild(name,deep)
    for _,c in ipairs(deep and self:GetDescendants() or self.children) do if c.Name==name then return c end end
end
function methods:FindFirstChildWhichIsA(kind,deep)
    for _,c in ipairs(deep and self:GetDescendants() or self.children) do if c:IsA(kind) then return c end end
end
function methods:Destroy()
    for _,c in ipairs(self:GetChildren()) do c:Destroy() end
    self.Parent=nil; self.destroyed=true
end
function methods:GetPivot() return self.pivot end
function methods:PivotTo(next)
    local prev=self.pivot
    for _,c in ipairs(self:GetDescendants()) do if c:IsA('BasePart') then c.CFrame=next*prev:ToObjectSpace(c.CFrame) end end
    self.pivot=next
end
function methods:GetBoundingBox() return self.pivot,V.new(1,1,1) end
function methods:SetStateEnabled(state,value) self.states[state]=value end
function methods:SetNetworkOwner(owner) self.networkOwnerSet=true; self.networkOwner=owner end
function methods:SetAttribute(key,value) self.attrs[key]=value end
function methods:GetAttribute(key) return self.attrs[key] end
function methods:GetAttributes() return self.attrs end
function methods:Clone() self.cloneCount=(self.cloneCount or 0)+1; return self.makeClone() end
Enum={HumanoidStateType={Jumping='Jumping',FallingDown='FallingDown',Ragdoll='Ragdoll'},HumanoidHealthDisplayType={AlwaysOff=1},HumanoidDisplayDistanceType={None=1}}
table.freeze=function(t) return t end
local modules={ActorCollisionPolicy={Assign=function(root,kind) root.CanCollide=true; root.collisionKind=kind end}}
script={Parent={WaitForChild=function(_,name) return name end}}
require=function(name) return assert(modules[name],name) end
local collection={GetTags=function(_,model) return model.tags end,AddTag=function(_,model,tag) table.insert(model.tags,tag) end}
game={GetService=function(_,name) assert(name=='CollectionService'); return collection end}
modules.MnpcNavigationShell=assert(loadfile(arg[1]))()
modules.MnpcVisualRig=assert(loadfile(arg[2]))()
local L=assert(loadfile(arg[3]))()
local function near(a,b) assert(math.abs(a-b)<1e-8, tostring(a)..' != '..tostring(b)) end
local function fixture(wrapped,valid)
    local wrapper=Instance.new('Model'); wrapper.Name='source'; wrapper:SetAttribute('Game1ModelAssetId','42'); wrapper.tags={'source-tag'}
    wrapper.ModelStreamingMode='Atomic'
    wrapper.makeClone=function()
        local clone=Instance.new('Model'); clone.Name='source'
        local visual=clone
        if wrapped then visual=Instance.new('Model'); visual.Name='ImportedRig'; visual.Parent=clone end
        if valid then
            local mesh=Instance.new('MeshPart'); mesh.Name='body'; mesh.Size=V.new(2,6,4); mesh.CFrame=F.new(V.new(0,5,0)); mesh.Parent=visual
            local root=Instance.new('Part'); root.Name='RootPart'; root.Size=V.new(.2,.02,.2); root.CFrame=F.new(V.new(0,2,0)); root.Parent=visual
            visual.PrimaryPart=root
            local bone=Instance.new('Bone'); bone.Name='spine'; bone.Parent=mesh
        end
        local oldHumanoid=Instance.new('Humanoid'); oldHumanoid.Parent=clone
        wrapper.lastClone=clone
        return clone
    end
    return wrapper
end
local destination=Instance.new('Folder')
for _,kind in ipairs({'Monster','NPC'}) do
    local surface=V.new(10,-12,20)
    local entity,root,humanoid=L.Create('actor',surface,math.pi/2,kind)
    assert(entity.Parent==nil and entity.PrimaryPart==root and root.Parent==entity)
    assert(#entity:GetChildren()==2 and humanoid.Parent==entity)
    assert(entity:GetAttribute('Game1MnpcKind')==kind and entity:GetAttribute('Game1MnpcRigReady')==false)
    assert(root.CanCollide and not root.CanQuery and not root.CanTouch and root.collisionKind==kind)
    near(root.CFrame.Position.Y,-9.2); near(root.CFrame.yaw,math.pi/2)
    assert(humanoid.HipHeight==1.8 and humanoid.states.Jumping==false and humanoid.Health==1)
    if kind=='NPC' then assert(humanoid.states.FallingDown==false and humanoid.states.Ragdoll==false) else assert(humanoid.states.FallingDown==nil) end
    assert(not pcall(L.MarkRigReady,entity))
    local source=fixture(kind=='NPC',true)
    L.CopyTemplateMetadata(entity,source)
    assert(source.cloneCount==nil and entity:GetAttribute('Game1ModelAssetId')=='42' and entity.tags[1]=='source-tag')
    assert(entity.ModelStreamingMode=='Atomic')
    if kind=='Monster' then entity:SetAttribute('MonsterSkillCaster',true) end
    local before=root.CFrame
    assert(not pcall(L.AttachRig,entity,root,source,surface,0,kind=="NPC" and "Monster" or "NPC"))
    assert(source.cloneCount==nil)
    local visual=L.AttachRig(entity,root,source,surface,math.pi/2,kind)
    assert(visual==entity:FindFirstChild('ImportedRig') and root.CFrame==before and entity.PrimaryPart==root)
    assert(source.cloneCount==1 and #source:GetChildren()==0)
    assert(visual:FindFirstChild('spine',true).Parent.Name=='body')
    assert(not visual:FindFirstChildWhichIsA('Humanoid',true))
    local body=visual:FindFirstChild('body',true)
    assert(not body.CanCollide and not body.CanTouch and not body.CanQuery and body.Massless)
    local collider=entity:FindFirstChild('RootCollider')
    assert(collider.CanQuery and not collider.CanCollide and not collider.CanTouch and collider.Massless)
    near(collider.CFrame.Position.Y,-9); near(collider.Size.X,4); near(collider.Size.Y,6); near(collider.Size.Z,2)
    local weld=root:FindFirstChild('RootColliderWeld'); assert(weld.Part0==root and weld.Part1==collider)
    local vw=collider:FindFirstChild('VisualRootWeld'); assert(vw.Part0==collider and vw.Part1==visual:FindFirstChild('RootPart',true))
    assert(vw.ClassName==(kind=='Monster' and 'Weld' or 'WeldConstraint'))
    assert(not pcall(L.AttachRig,entity,root,source,surface,0,kind))
    L.Publish(entity,root,destination); assert(root.networkOwnerSet and entity.Parent==destination)
    L.MarkRigReady(entity); assert(entity:GetAttribute('Game1MnpcRigReady')==true)
    entity:Destroy(); assert(#destination.children==0)
end
local entity,root=L.Create('bad',V.new(0,0,0),0,'Monster')
local bad=fixture(true,false)
assert(L.AttachRig(entity,root,bad,V.new(0,0,0),0,'Monster')==nil)
assert(bad.lastClone.destroyed and #entity.children==2 and not entity:GetAttribute('Game1MnpcRigReady'))
entity:Destroy()
print('M628 shell/rig oracle passed')
