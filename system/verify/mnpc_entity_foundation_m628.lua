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
function F:Inverse() return frame(rotate(V.new(0,0,0)-self.Position,-self.yaw),-self.yaw) end
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
    return setmetatable({ClassName=kind,Name=kind,Archivable=true,children={},attrs={},tags={},states={},pivot=F.new()},I)
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
table.clear=function(t) for k in pairs(t) do t[k]=nil end end
local modules={ActorCollisionPolicy={Assign=function(root,kind) root.CanCollide=true; root.collisionKind=kind end}}
script={Parent={WaitForChild=function(_,name) return name end}}
require=function(name) return assert(modules[name],name) end
local collection={GetTags=function(_,model) return model.tags end,AddTag=function(_,model,tag) table.insert(model.tags,tag) end}
local running=false
local run={IsStudio=function() return true end,IsRunning=function() return running end}
game={GetService=function(_,name) if name=='RunService' then return run end; assert(name=='CollectionService'); return collection end}
modules.MnpcNavigationShell=assert(loadfile(arg[1]))()
modules.MnpcRigGeometry=assert(loadfile(arg[4]))()
modules.MnpcPresentationLifecycle=assert(loadfile(arg[5]))()
modules.MnpcVisualRig=assert(loadfile(arg[2]))()
local L=assert(loadfile(arg[3]))()
local authored, authoredRoot=L.Create('Authoring',V.new(0,0,0),0,'Monster',true)
assert(authored.Parent==nil and authoredRoot.CanCollide==false and authoredRoot.collisionKind==nil)
authored:Destroy()
running=true
assert(not pcall(L.Create,'Forbidden',V.new(0,0,0),0,'Monster',true))
running=false
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

-- M630: actual metadata + shell plan, no cloning before publish. Compare
-- against the old exact FULL calculation for each kind/rotation. Engine double
-- deliberately updates the welded collider manually when simulating movement.
local G=modules.MnpcRigGeometry
local function sameFrame(a,b)
    near(a.Position.X,b.Position.X); near(a.Position.Y,b.Position.Y); near(a.Position.Z,b.Position.Z)
    near(math.sin(a.yaw-b.yaw),0); near(math.cos(a.yaw-b.yaw),1)
end
local function sameSize(a,b) near(a.X,b.X);near(a.Y,b.Y);near(a.Z,b.Z) end
local function authored(wrapped)
    local f=fixture(wrapped,true)
    local function build()
        local obj=f.makeClone()
        obj:PivotTo(F.new(V.new(5,2,-9))*F.Angles(0,.37,0))
        if wrapped then
            local accessory=Instance.new('Part'); accessory.Name='wrapper_piece'; accessory.Size=V.new(1,3,2)
            accessory.CFrame=F.new(V.new(8,-3,-6))*F.Angles(0,.19,0); accessory.Parent=obj
        end
        return obj
    end
    local source=build(); source.makeClone=build
    return source
end
for _,kind in ipairs({'Monster','NPC'}) do
    for _,wrapped in ipairs({true,false}) do
        local source=authored(wrapped)
        for _,yaw in ipairs({0,.17,math.pi/2,2.9,-.6}) do
            local surface=V.new(13,-8,5)
            local old,oldRoot=L.Create('old',surface,yaw,kind)
            local oldVisual=L.AttachRig(old,oldRoot,source,surface,yaw,kind)
            local oldCollider=old:FindFirstChild('RootCollider')
            local e,r,h=L.Create('prepared',surface,yaw,kind)
            local beforeClones=source.cloneCount
            local prepared=assert(L.PrepareShell(e,r,source,surface,yaw,kind))
            assert(source.cloneCount==beforeClones and #e.children==3)
            assert(not prepared.collider.CanQuery and not prepared.collider.CanCollide and h.Parent==e)
            assert(e:GetAttribute('Damageable')==false and not e:GetAttribute('Game1MnpcRigReady'))
            assert(not e:FindFirstChild('ImportedRig') and not e:FindFirstChildWhichIsA('Bone',true))
            sameFrame(prepared.collider.CFrame,oldCollider.CFrame);sameSize(prepared.collider.Size,oldCollider.Size)
            L.Publish(e,r,destination)
            -- Movement/rotation of shell between spawn and attach.
            local initial=r.CFrame
            local moved=F.new(V.new(-30,7,21))*F.Angles(0,yaw+.8,0)
            r.CFrame=moved; prepared.collider.CFrame=moved*prepared.geometry.colliderOffset
            assert(not pcall(L.AttachRig,old,oldRoot,source,surface,yaw,kind,prepared))
            local v=assert(L.AttachRig(e,r,source,surface,yaw,kind,prepared))
            sameFrame(r.CFrame,moved)
            local oldBody=oldVisual:FindFirstChild('body',true)
            sameFrame(v:FindFirstChild('body',true).CFrame,moved*initial:ToObjectSpace(oldBody.CFrame))
            assert(e:FindFirstChild('RootCollider')==prepared.collider and prepared.collider.CanQuery)
            L.MarkRigReady(e); assert(e:GetAttribute('Game1MnpcRigReady'))
            old:Destroy(); e:Destroy()
        end
        -- The immutable template snapshot is reused until invalidated.
        local body=source:FindFirstChild('body',true)
        local origin=F.new(V.new(0,2.8,0)); local surface=V.new(0,0,0)
        local a=G.Plan(source,origin,surface,0,kind); body.Size=V.new(100,6,100)
        local b=G.Plan(source,origin,surface,0,kind); sameSize(a.colliderSize,b.colliderSize)
        G.Invalidate(source); local c=G.Plan(source,origin,surface,0,kind);assert(c.colliderSize.X>a.colliderSize.X)
    end
end
local unsupported=authored(true)
unsupported:FindFirstChild('body',true).Archivable=false
local e,r=L.Create('unsupported',V.new(0,0,0),0,'NPC')
assert(L.PrepareShell(e,r,unsupported,V.new(0,0,0),0,'NPC')==nil)
assert(not e:FindFirstChild('RootCollider') and unsupported.cloneCount==nil)
e:Destroy()
print('M630 metadata / moving shell oracle passed (20 scenarios)')

local staleSource=authored(false)
local staleEntity,staleRoot=L.Create('stale',V.new(0,0,0),0,'Monster')
local stalePlan=assert(L.PrepareShell(staleEntity,staleRoot,staleSource,V.new(0,0,0),0,'Monster'))
G.Invalidate(staleSource)
assert(L.AttachRig(staleEntity,staleRoot,staleSource,V.new(0,0,0),0,'Monster',stalePlan)==nil)
assert(staleSource.cloneCount==nil and not stalePlan.collider.CanQuery and #staleEntity.children==3)
staleEntity:Destroy()
local missing=authored(false)
local missingEntity,missingRoot=L.Create('missing',V.new(0,0,0),0,'NPC')
local missingPlan=assert(L.PrepareShell(missingEntity,missingRoot,missing,V.new(0,0,0),0,'NPC'))
missing.makeClone=function() return nil end
assert(L.AttachRig(missingEntity,missingRoot,missing,V.new(0,0,0),0,'NPC',missingPlan)==nil)
assert(not missingPlan.collider.CanQuery and #missingEntity.children==3)
missingEntity:Destroy()
print('M630 stale plan / unavailable clone rejection passed')

-- M631: a presentation lease owns exactly one rig generation. Releasing
-- it must preserve the live entity, gameplay attributes and prepared shell.
for _,kind in ipairs({'Monster','NPC'}) do
    for _,wrapped in ipairs({true,false}) do
        local source=authored(wrapped)
        local surface=V.new(2,0,-3)
        local entity,root,humanoid=L.Create('lease',surface,.5,kind)
        local plan=assert(L.PrepareShell(entity,root,source,surface,.5,kind))
        local collider=plan.collider
        L.Publish(entity,root,destination)
        local independent=Instance.new('Folder'); independent.Name='IndependentState'; independent.Parent=entity
        entity:SetAttribute('HP',51)
        local visual,lease=L.AttachRig(entity,root,source,surface,.5,kind,plan)
        assert(visual and lease)
        local weapon=Instance.new('Model'); weapon.Name='EquippedWeaponRight'; weapon.Parent=entity
        lease:OwnEquipment(weapon)
        L.MarkRigReady(entity); entity:SetAttribute('Damageable',true)
        local weld=collider:FindFirstChild('VisualRootWeld')
        local wrapper=entity:FindFirstChild('wrapper_piece')
        assert(not pcall(function() lease:OwnEquipment(visual) end))
        assert(lease:Release())
        assert(visual.destroyed and weapon.destroyed and weld.destroyed)
        if wrapped then assert(wrapper.destroyed) end
        assert(root.Parent==entity and humanoid.Parent==entity and independent.Parent==entity)
        assert(entity.Parent==destination and entity.PrimaryPart==root and entity:GetAttribute('HP')==51)
        assert(collider.Parent==entity and not collider.CanQuery and not collider:FindFirstChild('VisualRootWeld'))
        assert(not entity:GetAttribute('Game1MnpcRigReady') and not entity:GetAttribute('Damageable'))
        local moved=F.new(V.new(7,12,24))*F.Angles(0,1.2,0)
        root.CFrame=moved; collider.CFrame=moved*plan.geometry.colliderOffset
        local nextVisual,nextLease=L.AttachRig(entity,root,source,surface,.5,kind,plan)
        assert(nextVisual and nextLease and nextVisual~=visual)
        L.MarkRigReady(entity); entity:SetAttribute('Damageable',true)
        assert(not lease:Release() and collider.CanQuery and entity:GetAttribute('Damageable'))
        assert(nextVisual.Parent==entity and root.CFrame==moved)
        assert(nextLease:Release() and nextVisual.destroyed)
        entity:Destroy()
    end
    -- Explicit compatibility FULL path owns its generated query collider.
    local source=authored(true)
    local e,r,h=L.Create('fallback',V.new(0,0,0),0,kind)
    local v,lease=L.AttachRig(e,r,source,V.new(0,0,0),0,kind)
    assert(v and lease and r:FindFirstChild('RootColliderWeld'))
    assert(lease:Release() and not e:FindFirstChild('RootCollider') and not r:FindFirstChild('RootColliderWeld'))
    assert(r.Parent==e and h.Parent==e)
    e:Destroy()
end
print('M631 rig ownership / release / reacquire oracle passed (6 cases)')
