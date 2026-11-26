--!strict
-- Player D-tier prototypes. Values are stat units, not Roblox world velocities.
-- Monster skills retain their own canonical skill catalogue and cooldowns.
local rows = {
    table.freeze({effect="might", name="Might", grade="D", power=20, duration=600, tick=0, color=Color3.fromRGB(174,102,245), unit="ATK", iconMask=table.freeze({"......##.",".....###.","....###..","...###...","#.###....",".###.....",".###.....","##..#....","#........"})}),
    table.freeze({effect="earth", name="Earth", grade="D", power=30, duration=600, tick=0, color=Color3.fromRGB(240,82,76), unit="HP", iconMask=table.freeze({".........",".###.###.","#########","#########",".#######.","..#####..","...###...","....#....","........."})}),
    table.freeze({effect="life", name="Life", grade="D", power=2, duration=600, tick=0, color=Color3.fromRGB(250,211,75), unit="HP/s", iconMask=table.freeze({".........","...###...","...###...",".#######.",".#######.",".#######.","...###...","...###...","........."})}),
    table.freeze({effect="wind", name="Wind", grade="D", power=20, duration=600, tick=0, color=Color3.fromRGB(95,202,245), unit="Speed", iconMask=table.freeze({".........","..####...","......#..","#######..",".........",".#######.",".......#.","..#####..","........."})}),
}
local byEffect = {}
for _, row in ipairs(rows) do byEffect[row.effect]=row end
return table.freeze({Rows=table.freeze(rows), ByEffect=table.freeze(byEffect)})
