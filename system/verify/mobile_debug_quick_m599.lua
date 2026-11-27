-- Engine-free behavior of the actual profile, catalog and mobile quick switch.
table.freeze = table.freeze or function(t) return t end
local function load(name) return assert(loadfile('src/client/'..name..'.luau'))() end
local profile = load('dev/DebugDockProfile')
local desktop=profile.Resolve(false,true)
assert(desktop.count==8 and desktop.slots.TL==0 and desktop.slots.AG==7)
local mobile=profile.Resolve(true,true)
assert(mobile.count==4 and mobile.slots.GP==0 and mobile.slots.UI==1 and mobile.slots.HP==2 and mobile.slots.CD==3)
assert(not mobile.slots.TL and not mobile.slots.CS and not mobile.slots.HS and not mobile.slots.AG)
local published=profile.Resolve(true,false)
assert(published.count==3 and not published.slots.GP and published.slots.UI==0 and published.slots.HP==1 and published.slots.CD==2)
local catalog=load('weapon/WeaponSlotCatalog')
local rows={{weaponType='sword',slug='z_sword'},{weaponType='bow',slug='b_bow'}, {weaponType='sword',slug='a_sword'}, {weaponType='dagger',slug='d_dagger'}, {weaponType='hands',slug=''}}
assert(catalog.Pick(rows,'sword')=='a_sword')
assert(catalog.Pick(rows,'sword','z_sword')=='z_sword')
assert(catalog.Pick(rows,'sword','b_bow')=='a_sword')
assert(catalog.Pick(rows,'bigsword')==nil)
local function signal()
 local fns={}
 return {Connect=function(self,fn) fns[fn]=true; return {Disconnect=function() fns[fn]=nil end} end,
 Fire=function(self,...) for fn in pairs(fns) do fn(...) end end}
end
local function object(attrs)
 local obj={attrs=attrs, AttributeChanged=signal(), signals={}}
 function obj:GetAttribute(k) return self.attrs[k] end
 function obj:GetAttributeChangedSignal(k) self.signals[k]=self.signals[k] or signal(); return self.signals[k] end
 function obj:Set(k,v) self.attrs[k]=v; self.AttributeChanged:Fire(k); if self.signals[k] then self.signals[k]:Fire() end end
 return obj
end
local player=object({}); player.CharacterAdded=signal(); player.CharacterRemoving=signal()
local char=object({LifeState='Alive',EquippedWeaponType='sword',EquippedWeaponSlug='z_sword'})
player.Character=char
local gui=object({}); gui.Parent=object({}); gui.GetPropertyChangedSignal=gui.GetAttributeChangedSignal
local tap, selected, visible
local suspended=false
local fakeSlots={Create=function(_, fn) tap=fn; return {SetSelected=function(k) selected=k end,SetVisible=function(v) visible=v end,Layout=function() end} end}
local guard={IsWorldSuspended=function() return suspended end}
local fakeParent={Parent={WaitForChild=function(_,name) return name end},WaitForChild=function(_,name) return name end}
script={Parent=fakeParent}
local originalRequire=require
require=function(name) return ({MobileWeaponSlots=fakeSlots,WeaponSlotCatalog=catalog,UiInputGuard=guard})[name] or error(name) end
local queue={}
task={spawn=function(fn) table.insert(queue,fn) end}
warn=function() end
local getCount=0; local equips={}
local quick=load('weapon/MobileWeaponQuickSelect')
local function equip(slug)
 table.insert(equips,slug)
 for _,r in ipairs(rows) do if r.slug==slug then char:Set('EquippedWeaponSlug',slug);char:Set('EquippedWeaponType',r.weaponType) end end
 return {ok=true}
end
quick.Mount(gui,player,function() getCount=getCount+1;return {enabled=true,weapons=rows} end,equip)
assert(visible and selected=='sword')
tap('sword'); assert(#queue==0)
tap('bow');tap('dagger');assert(#queue==1)
table.remove(queue,1)();assert(getCount==1 and #equips==1 and equips[1]=='b_bow' and selected=='bow')
tap('sword');table.remove(queue,1)();assert(equips[2]=='z_sword' and getCount==1)
tap('bigsword');table.remove(queue,1)();assert(#equips==2)
-- Missing binding is not cached indefinitely. A subsequent catalog can expose the weapon.
table.insert(rows,{weaponType='bigsword',slug='newbie_slayer_01'})
tap('bigsword');table.remove(queue,1)();assert(getCount==2 and #equips==3 and equips[3]=='newbie_slayer_01' and selected=='bigsword')
suspended=true;gui.Parent:Set('Game1SettingsInputBlocked',true);assert(not visible);tap('dagger');assert(#queue==0)
suspended=false;gui.Parent:Set('Game1SettingsInputBlocked',false);assert(visible)
tap('dagger');player.CharacterRemoving:Fire(char);player.Character=nil;table.remove(queue,1)();assert(#equips==3 and not visible)
player.Character=char;player.CharacterAdded:Fire(char);assert(visible)
player:Set('Game1GameplayTestActive',true);assert(not visible);tap('bow');assert(#queue==0)
require=originalRequire
print('M599 mobile debug profiles and direct switch passed')
