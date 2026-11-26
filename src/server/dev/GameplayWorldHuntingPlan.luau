--!strict
-- Graybox hunting pockets in entry-local studs. +Z is the entrance; -Z is deeper.
-- Each pair is melee/ranged for a level, never a shared aggro group.
-- Separate ecological pockets, safe approach, lateral optional elites, visible onward route.
local Plan = {}
local pockets = {
    -- Valley: safe central lane, first optional toad, flower beds off the road.
    {yaw=0, points={
        {-60,112}, {132,100}, {-130,48}, {65,48},
        {130,-48}, {-65,-48}, {-132,-60}, {65,-120},
    }},
    -- Forest: outskirts -> ruins -> chapel. Main exit on the right of entry frame.
    {yaw=90, points={
        {-68,118}, {125,122}, {-132,55}, {61,64},
        {-64,-20}, {128,-65}, {-132,-65}, {59,-120},
        {-64,-133}, {128,-132},
    }},
    -- Excavation: sand -> caves -> ruins; side pockets around the east exit.
    {yaw=0, points={
        {-72,118}, {124,115}, {-132,40}, {62,55},
        {-65,-38}, {132,-48}, {-132,-85}, {59,-118},
        {-63,-132}, {132,-123},
    }},
    -- Gardens: arrival from west; clear northern exit and southern shortcut.
    {yaw=-90, points={
        {-62,120}, {130,120}, {-130,60}, {62,60},
        {-62,-40}, {130,-60}, {-130,-70}, {62,-120},
        {-62,-132}, {130,-130},
    }},
    -- Bastion: outer guard, side posts, rear ritual ground.
    {yaw=0, points={
        {-64,126}, {132,126}, {-132,62}, {65,62},
        {-64,-14}, {132,-30}, {-132,-32}, {65,-67},
        {-64,-124}, {132,-124},
    }},
    -- Dragon heights: progressively deeper nests; summit on a side branch.
    {yaw=0, points={
        {-62,120}, {130,120}, {-130,120}, {62,60},
        {-62,40}, {130,40}, {-130,-40}, {62,-40},
        {-62,-120}, {130,-40}, {-130,-120}, {130,-120},
    }},
}
-- Starter ranged enemies are voluntary fights. No automatic two-shooter pull.
-- Remaining zones use distinct side pockets and smaller first-contact radius.
function Plan.Aggro(index: number, low: number, row: any): (boolean, number)
    if index == 1 and row.type == "ranged" then return false, 24 end
    if index == 1 then return true, 20 end
    if index <= 6 and row.level == low then return row.type == "melee", 24 end
    return true, 30
end
-- More than one level-one melee target lets a new player gain XP without
-- camping one respawn or pulling a level-two ranged monster.
function Plan.Extra(index: number, low: number, row: any): {Vector2}
    if index == 1 and row.level == low and row.type == "melee" then
        return {Vector2.new(-130,130), Vector2.new(62,145)}
    end
    return {}
end
function Plan.EntryFrame(index: number, top: CFrame): CFrame
    local pocket = pockets[index]
    return if pocket then top*CFrame.Angles(0,math.rad(pocket.yaw),0) else top
end
function Plan.Point(index: number, low: number, row: any): Vector2?
    local pocket = pockets[index]
    if not pocket then return nil end
    local offset = (row.level-low)*2 + (if row.type == "melee" then 1 else 2)
    local point = pocket.points[offset]
    return if point then Vector2.new(point[1],point[2]) else nil
end
return table.freeze(Plan)
