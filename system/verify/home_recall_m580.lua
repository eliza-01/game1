-- Execute the authoritative phase machine with mocked Roblox services.
local now=0; os.clock=function() return now end
local mt={}
local function v(x,y,z) return setmetatable({X=x,Y=y,Z=z},mt) end
mt.__add=function(a,b) return v(a.X+b.X,a.Y+b.Y,a.Z+b.Z) end
mt.__sub=function(a,b) return v(a.X-b.X,a.Y-b.Y,a.Z-b.Z) end
mt.__mul=function(a,b) return v(a.X*b,a.Y*b,a.Z*b) end
mt.__index=function(a,k) if k=='Magnitude' then return math.sqrt(a.X^2+a.Y^2+a.Z^2) end end
Vector3={zero=v(0,0,0),yAxis=v(0,1,0)}
table.freeze=function(t) return t end
local events={}; local players={}
local remotes={}; local services={Players={GetPlayers=function() return players end},ReplicatedStorage={FindFirstChild=function() return remotes end},TweenService={}}
function services.TweenService:Create(item,info,goal)
    return {Play=function() end,Cancel=function() end,Destroy=function() end,goal=goal}
end
game={GetService=function(_,key) return assert(services[key]) end}
Instance={new=function(kind) assert(kind=='RemoteEvent');return {FireClient=function(_,player,foot,height,radius) table.insert(events,{foot=foot,height=height,radius=radius}) end} end}
TweenInfo={new=function() return {} end}; Enum={EasingStyle={Sine=1},EasingDirection={InOut=1}}
script={Parent={WaitForChild=function(_,n) return n end}}; require=function() return {Event=function() end} end
local Recall=assert(loadfile(arg[1]))(); Recall.Start()
local root={Parent=true,Position=v(12,3,0),Anchored=false,Transparency=1,SetNetworkOwner=function(self,owner) self.serverOwned=true end}
local function part(alpha)
    return {Parent=true,Transparency=alpha,IsA=function(_,kind) return kind=='BasePart' end}
end
local mesh=part(.2); local hidden=part(1); local collider=part(1); collider.Position=root.Position; collider.Size=v(3,4,2)
local attrs={LifeState='Alive',Damageable=true,HP=75,MonsterInstanceId='same'}
local model={Parent=true,GetAttribute=function(_,key) return attrs[key] end,SetAttribute=function(_,key,val) attrs[key]=val end,
    GetDescendants=function() return {mesh,hidden,collider} end,FindFirstChild=function(_,key) assert(key=='RootCollider');return collider end,
    GetPivot=function() return root.Position end,PivotTo=function(_,goal) root.Position=goal;collider.Position=goal end}
local playerRoot=part(1);playerRoot.Position=v(0,0,0);players[1]={Character={FindFirstChild=function() return playerRoot end}}
local agent={model=model,root=root,home=v(2,3,1),humanoid={Move=function() end,MoveTo=function() end}}
Recall.Begin(agent); assert(Recall.Active(agent) and root.Anchored and attrs.Damageable==false and attrs.MonsterHomeRecalling)
Recall.Begin(agent);assert(#events==1 and events[1].foot.X==12 and events[1].height==10.4)
now=1; assert(not Recall.Step(agent) and root.Position.X==12)
now=1.05; assert(not Recall.Step(agent) and root.Position.X==2 and root.Position.Z==1 and mesh.Transparency==1)
assert(#events==2 and events[2].foot.X==2 and root.Anchored and not attrs.Damageable)
now=2.11; assert(Recall.Step(agent) and not Recall.Active(agent) and not root.Anchored and root.serverOwned)
assert(mesh.Transparency==.2 and hidden.Transparency==1 and attrs.Damageable and attrs.HP==75 and attrs.MonsterInstanceId=='same' and not attrs.MonsterHomeRecalling)
Recall.Begin(agent); Recall.Cancel(agent); assert(not root.Anchored and mesh.Transparency==.2 and attrs.Damageable)
Recall.Begin(agent);attrs.LifeState='Dying';Recall.Cancel(agent);assert(root.Anchored and not attrs.Damageable and not attrs.MonsterHomeRecalling)
print('Home recall: bounded phases, fixed FX positions, same instance, cleanup and death passed')
