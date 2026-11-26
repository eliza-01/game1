--!strict
-- D-tier shop presentation. Gameplay parameters come only from Balance.
local Balance = require(script.Parent.Parent:WaitForChild("balance"):WaitForChild("Balance"))
local icons = {
    table.freeze({effect="might", name="Might", grade="D", color=Color3.fromRGB(174,102,245), unit="ATK", iconMask=table.freeze({"......##.",".....###.","....###..","...###...","#.###....",".###.....",".###.....","##..#....","#........"})}),
    table.freeze({effect="earth", name="Earth", grade="D", color=Color3.fromRGB(240,82,76), unit="HP", iconMask=table.freeze({".........",".###.###.","#########","#########",".#######.","..#####..","...###...","....#....","........."})}),
    table.freeze({effect="life", name="Life", grade="D", color=Color3.fromRGB(250,211,75), unit="HP/s", iconMask=table.freeze({".........","...###...","...###...",".#######.",".#######.",".#######.","...###...","...###...","........."})}),
    table.freeze({effect="wind", name="Wind", grade="D", color=Color3.fromRGB(95,202,245), unit="Speed", iconMask=table.freeze({".........","..####...","......#..","#######..",".........",".#######.",".......#.","..#####..","........."})}),
}
local rows = {}
local byEffect = {}
for _, icon in ipairs(icons) do
    local skill = assert(Balance.Skill("skill_"..icon.effect.."_d"), "Missing D buff")
    local row = table.clone(skill)
    row.grade=icon.grade; row.color=icon.color; row.unit=icon.unit; row.iconMask=icon.iconMask
    row=table.freeze(row)
    table.insert(rows,row); byEffect[row.effect]=row
end
return table.freeze({Rows=table.freeze(rows), ByEffect=table.freeze(byEffect)})
