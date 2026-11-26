-- M539 replacement for the retired lane test. Studio Server Command Bar, without entering GP.
local dev=game:GetService("ServerScriptService"):WaitForChild("Game1Server"):WaitForChild("dev")
local Shared=game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Balance=require(Shared.balance.Balance)
local Layout=require(dev.GameplayTestLayout)
local origin=CFrame.new(236.646,46.24,49.04)*CFrame.Angles(0,math.rad(137.647),0)
local layout=Layout.Build(origin,Balance.Monsters,Balance.MaxLevel,40,Vector3.new(3,5,3),12,Balance.SkilledMonsters)
assert(Balance.MaxLevel==35)
local count=0
for _,row in ipairs(Balance.Monsters) do
    local slot=assert(layout.slots[row.id]); count+=1
    local box=assert(layout.boxes[slot.zone]); assert(row.level>=box.low and row.level<=box.high)
    local p=box.top:PointToObjectSpace(slot.point)
    assert(math.abs(p.X)<box.size.X/2 and math.abs(p.Z)<box.size.Z/2 and math.abs(p.Y)<0.01)
    local v=box.top:PointToObjectSpace(slot.visit.Position)
    assert(math.abs(v.X)<box.size.X/2 and math.abs(v.Z)<box.size.Z/2)
    assert(box.size.X==384 and box.size.Z==384 and box.size.Y==16)
end
assert(count==70)
for _,row in ipairs(Balance.SkilledMonsters) do assert(layout.slots[row.id].zone==8) end
for _,slot in pairs(layout.slots) do
    local box=layout.boxes[slot.zone]
    local p=box.top:PointToObjectSpace(slot.point)
    local v=box.top:PointToObjectSpace(slot.visit.Position)
    assert(math.abs(p.X)+slot.homeRadius<=192 and math.abs(p.Z)+slot.homeRadius<=192)
    assert(math.abs(v.X)<192 and math.abs(v.Z)<192)
end
for _,box in pairs(layout.boxes) do
    local e=box.top:PointToObjectSpace(box.entry.Position)
    assert(math.abs(e.Z)<192 and math.abs(e.X)<192)
end
print("[M540] 70 slots, rotated frame, zone bounds, visits and skilled annex passed")
