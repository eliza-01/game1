table.freeze=function(t) return t end
local loadouts={loadouts={guard={right='sword',left='bow'}, invalid={right='missing',left='bow'}, empty={}}}
local rows={sword={weaponType='sword'},bow={weaponType='bow'}}
local resolved,mounted,owned,warnings=0,0,0,0
local failRight=false
local equip={
    ResolveVisual=function(slug)
        resolved=resolved+1
        if rows[slug] then return rows[slug],{} end
        return nil,nil,'not published'
    end,
    EquipVisual=function(entity,slug,hand,name)
        mounted=mounted+1
        if not rows[slug] or (failRight and hand=='right') then return nil,rows[slug],'missing socket' end
        return {name=name},rows[slug]
    end,
}
-- WaitForChild is recursive; mock each path without constructing any Instances.
local function path(name)
    return {name=name,WaitForChild=function(_,n) return path(n) end}
end
local modules={NpcEquipmentRegistry=loadouts, WeaponAttackMovement={AnimationSetForType=function(kind) return kind=='hands' and 'unarmed' or kind end},WeaponEquipService=equip}
require=function(node) return assert(modules[node.name],node.name) end
game={GetService=function(_,name) return path(name) end}
script={Parent={Parent=path('server')}}
warn=function() warnings=warnings+1 end
local S=assert(loadfile(arg[1]))()
local guard=S.Resolve('guard')
assert(guard.weaponType=='sword' and guard.weaponSet=='sword' and guard.items[1].hand=='right' and guard.items[2].hand=='left')
local invalid=S.Resolve('invalid'); assert(invalid.weaponType=='bow')
assert(S.Resolve('empty').weaponSet=='unarmed')
assert(resolved==4 and mounted==0 and owned==0)
local entity={attrs={},SetAttribute=function(self,k,v) self.attrs[k]=v end}
local lease={OwnEquipment=function(_,item) assert(item.name); owned=owned+1 end}
assert(S.Equip(entity,'guard',guard,lease)=='sword' and mounted==2 and owned==2)
failRight=true
assert(S.Equip(entity,'guard',guard,lease)=='bow' and entity.attrs.NpcWeaponType=='bow')
assert(mounted==4 and owned==3 and warnings==1)
assert(S.Equip(entity,'empty',S.Resolve('empty'),lease)=='unarmed' and mounted==4)
print('M631 equipment metadata / mount fallback oracle passed')
