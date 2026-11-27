-- Engine-free tests of the actual helpers. Runs in Luau or stock Lua with adapters.
if not table.freeze then table.freeze = function(t) return t end end
if not table.clear then table.clear = function(t) for key in pairs(t) do t[key] = nil end end end
if not math.clamp then math.clamp = function(x, a, b) return math.max(a, math.min(b,x)) end end
local function module(path)
    if arg and arg[1] == "lua" then return assert(loadfile(path..".luau"))() end
    error("Run stock Lua using the Python harness, or use the literal Luau test entry")
end
local Repeat, Touches, Layout, Corners
if arg and arg[1] == "lua" then
    Repeat = module("src/client/combat/AttackRepeatInput")
    Touches = module("src/client/character/mobile/MobileActionTouches")
    Layout = module("src/client/character/mobile/MobileLayout")
    Corners = module("src/client/HudCornerLayout")
else
    Repeat = require("../../src/client/combat/AttackRepeatInput")
    Touches = require("../../src/client/character/mobile/MobileActionTouches")
    Layout = require("../../src/client/character/mobile/MobileLayout")
    Corners = require("../../src/client/HudCornerLayout")
end
local r = Repeat.New()
assert(not r.IsActive() and not r.ShouldAttempt(0,false))
r.SetHeld("mouse",true)
assert(r.IsActive() and r.ShouldAttempt(0,false))
assert(not r.ShouldAttempt(.01,false))
assert(not r.ShouldAttempt(10,true)) -- existing timeline owns interval
assert(r.ShouldAttempt(10,false))
r.SetHeld("touch",true)
r.SetHeld("mouse",false)
assert(r.IsActive())
r.SetHeld("touch",false)
assert(not r.IsActive())
r.SetAutomatic(true)
assert(r.ShouldAttempt(11,false))
r.SetHeld("touch",true)
r.SetHeld("touch",false)
assert(r.IsActive()) -- green toggle independent of held attacks
r.SetAutomatic(false)
assert(not r.IsActive())
r.SetHeld("mouse",true); r.Clear()
assert(not r.IsActive())
local vector = {}
vector.__sub = function(a,b) return {Magnitude=math.abs(a.x-b.x)} end
local function point(x) return setmetatable({x=x},vector) end
local t=Touches.New()
assert(t.Begin("jump","Jump",point(0)))
assert(t.Begin("attack","Attack",point(0)))
assert(t.Held("Attack") and t.Held("Jump"))
assert(not t.Begin("attack","Attack",point(0)))
assert(t.Move("attack",point(12)).Magnitude==12) -- held jump does not steal camera
assert(t.Move("jump",point(2))==nil) -- one drag owner
local kind,tap=t.Finish("attack")
assert(kind=="Attack" and not tap and t.Held("Jump") and not t.Held("Attack"))
assert(t.Move("jump",point(4)).Magnitude==2)
local cb=function() end
assert(t.Begin("weapon","Weapon",point(0),cb))
local k,clicked,callback=t.Finish("weapon")
assert(k=="Weapon" and clicked and callback==cb)
t.Clear(); assert(not t.Held("Jump") and not t.Has("jump"))
local function rect(box,w,h)
    return {x=w-box.x-box.size,y=h-box.y-box.size,w=box.size,h=box.size}
end
local function overlaps(a,b)
    return a.x < b.x+b.w and a.x+a.w > b.x and a.y < b.y+b.h and a.y+a.h > b.y
end
local function inside(a,w,h)
    assert(a.x>=0 and a.y>=0 and a.x+a.w<=w and a.y+a.h<=h, ("outside %dx%d: %s,%s,%s,%s"):format(w,h,a.x,a.y,a.w,a.h))
end
for _,size in ipairs({{568,240},{640,180},{640,200},{640,250},{740,300},{844,340},{1024,700},{240,400},{300,560},{390,760},{768,950}}) do
    local w,h=size[1],size[2]
    local l=Layout.Resolve(w,h)
    -- Reference proportions, radius and order are checked on the actual geometry.
    local a=l.attack
    assert(math.abs(l.jump.size/a.size-.46)<=1/a.size)
    assert(l.aim.size==l.jump.size)
    assert(math.abs(l.stick/a.size-1.06)<=1/a.size)
    assert(math.abs(l.weapon.size/a.size-.37)<=1/a.size)
    assert(l.weapon.margin==2)
    assert(a.x==2 and a.y<=a.size*.07 and l.skills[4].x==a.x and l.jump.x==l.skills[1].x)
    local angle=-math.huge
    for _,skill in ipairs(l.skills) do
        assert(skill.size==l.jump.size)
        local dx=skill.x+skill.size/2-a.x-a.size/2
        local dy=skill.y+skill.size/2-a.y-a.size/2
        assert(math.abs(math.sqrt(dx*dx+dy*dy)-a.size*1.28)<=1)
        local nextAngle=math.acos(dx/math.sqrt(dx*dx+dy*dy))
        assert(nextAngle>angle and dy>0)
        angle=nextAngle
    end
    assert(Corners.DebugLeft==16+Corners.SettingsSize)
    assert(Corners.DebugLeft>=Corners.SettingsLeft+Corners.SettingsSize)
    local weaponRight=l.weapon.margin+2*l.weapon.size+l.weapon.gap+8
    local cols=Corners.DebugColumns(w,weaponRight,44,8,8)
    for i=0,7 do
        local x=Corners.DebugLeft+(i%cols)*52
        assert(x+44<=w-weaponRight)
    end
    local all={rect(l.attack,w,h),rect(l.jump,w,h),rect(l.aim,w,h),{x=l.margin,y=h-l.margin-l.stick,w=l.stick,h=l.stick}}
    for _,s in ipairs(l.skills) do table.insert(all,rect(s,w,h)) end
    local weapon=l.weapon
    for i=0,3 do
        table.insert(all,{x=w-weapon.margin-(i%2)*(weapon.size+weapon.gap)-weapon.size,
            y=weapon.margin+math.floor(i/2)*(weapon.size+weapon.gap),w=weapon.size,h=weapon.size})
    end
    for i,a in ipairs(all) do
        inside(a,w,h)
        for j=i+1,#all do assert(not overlaps(a,all[j]),("overlap %dx%d: %d / %d"):format(w,h,i,j)) end
    end
    for _,p in ipairs({{64,nil},{116,nil},{40,82}}) do
        local b=Layout.Context(w,h,p[1],p[2])
        local a={x=w-b.x-b.width,y=h-b.y-p[1],w=b.width,h=p[1]}
        inside(a,w,h)
        for j,other in ipairs(all) do assert(not overlaps(a,other),("dock overlap %dx%d: %d / height %d"):format(w,h,j,p[1])) end
    end
end
print("M597: held sources, repeat throttle, action drag/tap ownership, 11 viewports, arc proportions, debug clearance and 33 docks passed")
