-- Standalone deterministic payload/upgrade regression (Luau CLI).
local Eyes = require("../../src/shared/character/CharacterCreationEyeColors")
local defaults = Eyes.Defaults({eye_l = {color = "#123abc"}, eye_r = {color = "#456def"}})
assert(defaults.l == "#123ABC" and defaults.r == "#456DEF")
local legacy = assert(Eyes.Normalize("#aabbcc", defaults))
assert(legacy.l == "#AABBCC" and legacy.r == "#AABBCC")
local independent = assert(Eyes.Normalize({l = "#00aa00", r = "#0000bb"}, defaults))
assert(independent.l == "#00AA00" and independent.r == "#0000BB")
local again = assert(Eyes.Normalize(independent, defaults))
assert(again.l == independent.l and again.r == independent.r and again ~= independent)
local partial = assert(Eyes.Normalize({r = "#112233"}, defaults))
assert(partial.l == defaults.l and partial.r == "#112233")
local inherited = assert(Eyes.Normalize(nil, defaults))
assert(inherited.l == defaults.l and inherited.r == defaults.r and inherited ~= defaults)
for _, bad in ipairs({false, 1, "#123", {l = false}, {r = "red"}, {left = "#123456"}, {[1] = "#123456"}}) do
    assert(Eyes.Normalize(bad, defaults) == nil, "invalid eye payload accepted")
end
assert(defaults.l == "#123ABC" and defaults.r == "#456DEF", "defaults mutated")
print("M487 eye color contract: OK")
