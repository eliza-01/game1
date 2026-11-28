-- Actual plan and service with minimal Roblox doubles. No engine fetch claims.
local root, adapted, planPath = arg[1], arg[2], arg[3]
table.freeze = function(t) return t end
table.find = function(t,v) for i,x in ipairs(t) do if x==v then return i end end end
table.clear = function(t) for k in pairs(t) do t[k]=nil end end
local plan = dofile(planPath)
local registry = dofile(root..'/src/shared/character/CharacterRegistry.luau')
local catalog = dofile(root..'/src/shared/character/CharacterCreationAppearanceRegistry.luau')
local live = plan.Build(registry,catalog)
local unique = {}; for _,r in ipairs(live) do assert(not unique[r.assetId]); unique[r.assetId]=true end
assert(#live > 0 and #live <= 24)
print('Actual registry optional components: '..#live)
local function part(id, asset, atlas) return {id=id,asset_id=tostring(asset),atlas_image_id=atlas or ''} end
local default = part('base',1,'10')
local function row(id) return {id=id,status='ASSEMBLY_READY',assembly={ready=true,parts={head=default,hair=part('hair',2)}}} end
local reg={archetypes={row('human_male'),row('human_female')}}
local many={}; for i=1,40 do many[i]={id='h'..i,part=part('h'..i,100+i)} end
local cat={archetypes={human_male={hair={{id='hair',part=part('hair',2)},{id='a',part=part('a',3,'12')},{id='b',part=part('b',3,'13')}},head={{id='base',part=part('base',1)}}},human_female={hair={{id='c',part=part('c',4)},{id='d',part=part('d',3,'12')}}}}}
local planned=plan.Build(reg,cat)
assert(#planned==2 and planned[1].assetId==4 and planned[2].assetId==3)
assert(planned[2].atlases['12'] and planned[2].atlases['13'])
assert(#plan.Build(reg,{archetypes={human_male={hair=many}}})==24)
local function obj(class,props)
  local t=props or {};t.class=class;t.children=t.children or {}
  function t:IsA(c) return self.class==c end
  function t:WaitForChild(n) return n end
  function t:GetDescendants() return self.children end
  function t:Clone() return obj(self.class,{MeshId=self.MeshId,TextureID=self.TextureID,children={1,2}}) end
  function t:ClearAllChildren() self.children={} end
  function t:Destroy() self.destroyed=true;self.Parent=nil end
  return t
end
local rep=obj('Folder'); function rep:WaitForChild(n) return self end
local created={}; Instance={new=function(c) local x=obj(c);created[#created+1]=x;return x end}
game={GetService=function(_,n) return rep end}; script={Parent=obj('Folder')}; warn=function()end
local oldRequire=require
-- Shared mock needs actual module tokens distinct from service folders.
local shared=obj('Folder');function shared:WaitForChild(n) return n end
function rep:WaitForChild(n) return shared end
function shared:WaitForChild(n) if n=='character' then return shared elseif n=='CharacterRegistry' then return reg elseif n=='CharacterCreationAppearanceRegistry' then return cat end end
require=function(n) if n=='CharacterCreationWarmPlan' then return plan else return n end end
local service=dofile(adapted)
local loadCount=0
local function mesh(id,texture) return obj('MeshPart',{MeshId=id,TextureID=texture}) end
service.Bind(obj('Folder'),function(id)
 loadCount=loadCount+1
 return obj('Model',{children={mesh('rbxassetid://90','rbxassetid://91'),mesh('rbxassetid://90','rbxassetid://92')}})
end)
local folder,remote=created[1],created[2]
local stage='creation'; local player={GetAttribute=function(_,k) if k=='CharacterCreationPending' then return true else return stage end end}
local invoke=remote.OnServerInvoke
assert(not invoke(player,'4').ok and not invoke(player,100).ok and loadCount==0)
local a=invoke(player,1);assert(a.ok and #a.meshes==1 and #a.images==2)
local b=invoke(player,2);assert(b.ok and a.meshes[1]==b.meshes[1] and #b.images==4)
assert(invoke(player,2)==b and loadCount==2)
assert(invoke(player,3).done)
stage='world';assert(not invoke(player,1).ok and loadCount==2)
require=oldRequire
print('M648 plan / warm service: PASS')
