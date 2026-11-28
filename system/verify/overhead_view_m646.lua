-- HealthBarView source is syntax-adapted by the Python harness, not reimplemented.
local function signal()
 local s={listeners={}}
 function s:Connect(fn) self.listeners[fn]=true;return {Disconnect=function() self.listeners[fn]=nil end} end
 function s:Fire() local a={};for fn in pairs(self.listeners) do a[#a+1]=fn end;for _,fn in ipairs(a) do fn() end end
 return s
end
local all={}
Instance={new=function(class)
 local i={ClassName=class,attrs={}}
 function i:SetAttribute(k,v) self.attrs[k]=v end
 function i:Destroy() self.Parent=nil;self.destroyed=true end
 all[#all+1]=i;return i
end}
local function v3(x,y,z) return {X=x,Y=y,Z=z} end
Vector3={new=v3,zero=v3(0,0,0)};Vector2={new=function(x,y) return {X=x,Y=y} end}
local function tuple(...) return table.concat({...},',') end
UDim={new=tuple};UDim2={new=tuple,fromOffset=tuple,fromScale=tuple};Color3={new=tuple,fromRGB=tuple};ColorSequence={new=tuple};TweenInfo={new=tuple}
Enum=setmetatable({}, {__index=function() return setmetatable({}, {__index=function(_,k) return k end}) end})
math.clamp=function(x,l,h) return math.max(l,math.min(x,h)) end;typeof=type;table.freeze=function(t)return t end;table.clear=function(t)for k in pairs(t) do t[k]=nil end end
local tweenCount,cancelCount=0,0
local tween={Create=function(_,fill,_,goal) tweenCount=tweenCount+1;return {Play=function() for k,v in pairs(goal) do fill[k]=v end end,Cancel=function() cancelCount=cancelCount+1 end,Destroy=function() end} end}
local text={GetTextSize=function(_,s,size) return {X=#s*size} end}
local lang={locale='en-us',Changed=signal(),FromSource=function(s)return s end,Current=function()return lang.locale end,Has=function()return false end};lang.Current=function()return lang.locale end
local iconCount=0
local icons={Create=function(parent) iconCount=iconCount+1;local p=Instance.new('Frame');p.Parent=parent;return p,{} end,DangerColor=function()return 'danger' end}
local node={};node.Parent=node;function node:WaitForChild(k) if k=='localization' then return self end;return k end
script={Parent=node};game={GetService=function(_,k)return ({TweenService=tween,TextService=text})[k]end};require=function(k)return ({LanguageState=lang,MonsterIconView=icons,NpcDisplayNameFormatter={Format=function(s)return s end}})[k]end
local View=assert(loadfile(arg[1]))()
local function model(attrs)
 local m={Name='actor',attrs=attrs,signals={}}
 function m:GetAttribute(k)return self.attrs[k]end
 function m:GetAttributeChangedSignal(k) self.signals[k]=self.signals[k] or signal();return self.signals[k]end
 function m:GetDescendants()return {}end
 function m:Set(k,v)self.attrs[k]=v;self:GetAttributeChangedSignal(k):Fire()end
 return m,{Parent=m,Position=v3(0,0,0),Size=v3(2,4,2)}
end
local spec={enabled=true,width=80,height=12,nameSize=14,levelSize=12,border=1,offsetStuds=1,maxDistanceStuds=100}
local style={monster=spec,self=spec,colors={red='#ff0000',yellow='#ffff00',green='#00ff00'}}
local a,ar=model({Game1MonsterRuntime=true,MonsterNameEn='Gremlin',MonsterNameRu='Гремлин',Level=4,HP=80,MaxHP=100,GameplayTestZone=1,Game1GameplayTestOwner=42})
local b,br=model({Game1NpcRuntime=true,NpcSlug='guard',NpcDisplayName='Guard',HP=20,MaxHP=100})
local v=View.Create();local gui,fill,title
for _,i in ipairs(all) do if i.ClassName=='BillboardGui' then gui=i elseif i.Name=='Fill' then fill=i elseif i.Name=='Caption' then title=i end end
assert(gui and fill and title and not gui.Parent)
local parent={};v.Bind(parent,a,ar,style);v.SetIcon(true,1);v.SetSegments(true,true)
assert(gui.Adornee==ar and gui.Parent==parent and gui.Enabled and fill.Size=='0.8,1' and iconCount==1 and title.Text=='Gremlin')
local stale=next(a.signals.HP.listeners)
a:Set('HP',50);assert(tweenCount==1 and fill.Size=='0.5,1');a:Set('HP',50);assert(tweenCount==1)
v.Unbind();assert(not gui.Parent and not gui.Adornee and not gui.Enabled and cancelCount==1 and title.Text=='')
for _,s in pairs(a.signals) do assert(next(s.listeners)==nil) end;assert(next(lang.Changed.listeners)==nil)
v.Bind(parent,b,br,style);v.SetMaxDistance(500);v.SetSegments(true,true)
assert(gui.Adornee==br and gui.Enabled and fill.Size=='0.2,1' and title.Text=='Guard' and gui.attrs.WorldInputPassthrough==nil and tweenCount==1)
a:Set('HP',90);stale();assert(fill.Size=='0.2,1' and tweenCount==1)
lang.locale='ru-ru';lang.Changed:Fire();assert(gui.MaxDistance==500 and tweenCount==1)
v.Unbind();v.Bind(parent,a,ar,style);assert(title.Text=='Гремлин' and fill.Size=='0.9,1');v.Destroy()
for _,s in pairs(a.signals) do assert(next(s.listeners)==nil) end;assert(next(lang.Changed.listeners)==nil and gui.destroyed)
print('M646 actual HealthBarView bind/unbind, stale HP, tween, locale, GP portrait, NPC distance OK')
