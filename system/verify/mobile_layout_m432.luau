-- Optional executable geometry test: luau system/verify/mobile_layout_m432.luau
local Layout = require("../../src/client/character/mobile/MobileLayout")
local function rect(box, w, h, width, height)
    return {x=w-box.x-width, y=h-box.y-height, w=width, h=height}
end
local function overlaps(a,b)
    return a.x < b.x+b.w and a.x+a.w > b.x and a.y < b.y+b.h and a.y+a.h > b.y
end
local function inside(r,w,h)
    assert(r.x>=0 and r.y>=0 and r.x+r.w<=w and r.y+r.h<=h)
end
for _, size in ipairs({{568,240},{640,200},{640,250},{740,300},{844,340},{1024,700},{300,560},{390,760},{768,950}}) do
    local w,h = size[1],size[2]
    local l = Layout.Resolve(w,h)
    assert(l.attack.size > l.jump.size and l.jump.size >= 48 and l.aim.size >= 48)
    local a = rect(l.attack,w,h,l.attack.size,l.attack.size)
    local j = rect(l.jump,w,h,l.jump.size,l.jump.size)
    local t = rect(l.aim,w,h,l.aim.size,l.aim.size)
    local stick={x=l.margin,y=h-l.margin-l.stick,w=l.stick,h=l.stick}
    for _, r in ipairs({a,j,t,stick}) do inside(r,w,h) end
    assert(not overlaps(a,j) and not overlaps(a,t) and not overlaps(j,t))
    for _, n in ipairs({1,2}) do
        local ph=12+n*52
        local dock=Layout.Context(w,h,ph)
        local c=rect(dock,w,h,dock.width,ph)
        inside(c,w,h)
        assert(not overlaps(c,a) and not overlaps(c,j) and not overlaps(c,t) and not overlaps(c,stick))
    end
    assert(Layout.IsMoveZone(l.margin+l.stick/2,h-l.margin-l.stick/2,w,h))
    assert(not Layout.IsMoveZone(w*0.2,h*0.2,w,h))
    assert(not Layout.IsMoveZone(w*0.8,h*0.8,w,h))
end
print("OK: mobile safe layout, disjoint hit targets, 9 viewport sizes / 18 context layouts")
