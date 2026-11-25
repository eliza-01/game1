--!strict
-- Grade is independent of rarity and upgrade rank. A plus tier shares the base requirement.
local Grade = {}
local names = {"Newbie", "D", "C", "B", "A", "S", "SS", "SSS"}
local colors = {"#9B9B9B", "#A7B9A3", "#69B67B", "#54B6B1", "#6B9DDF", "#9880D9", "#C18ADB", "#E8BA4E"}
function Grade.ForLevel(level: number): (string, number)
    local band = math.clamp(math.floor(level / 10) + 1, 1, #names)
    local plus = level % 10 >= 5
    local name = names[band] .. (if plus then "+" else "")
    return name, math.max(1, (band - 1) * 10)
end
function Grade.Color(level: number): Color3
    -- Current 1–35 test scale; gold is the top currently implemented tier.
    local index = math.clamp(math.floor(level / 5) + 1, 1, #colors)
    return Color3.fromHex(colors[index])
end
return table.freeze(Grade)
