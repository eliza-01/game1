-- Run on Studio client command bar; pure palette rules, no DataStore mutation.
local colors = require(game:GetService("ReplicatedStorage").Game1Shared.character.CharacterCreationSavedColors)
assert(colors.Hex("#aabbcc") == "#AABBCC")
assert(colors.Hex("#xyzabc") == nil)
assert(colors.Hex("#11223344") == nil)
local list = colors.Normalize({"#aabbcc", "#AABBCC", "invalid", "#102030"})
assert(#list == 2 and list[1] == "#AABBCC")
assert(#colors.Add(list, "#aabbcc") == 2)
for i = 1, 30 do list = colors.Add(list, string.format("#%06X", i)) end
assert(#list == 24 and list[1] == "#00001E" and list[24] == "#000007")
print("[M510] account palette rules passed")
