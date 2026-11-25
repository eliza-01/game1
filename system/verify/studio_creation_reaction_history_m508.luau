-- Studio Play CLIENT command bar. Exercises the actual weighted chooser.
local root = game:GetService("Players").LocalPlayer.PlayerScripts.Game1Client.character
local reactions = require(root.CharacterCreationReactions)
local rng = Random.new(508)
local function entry(group, weight, count)
    local rows = {}
    for i = 1, count do table.insert(rows, {animationId = group .. "_" .. i}) end
    return {group = group, weight = weight, rows = rows}
end
local a, b, c, d = entry("laugh", 100, 3), entry("hi", 50, 2), entry("sad", 1, 1), entry("bow", 100, 2)
local recent, seen = {}, {}
for i = 1, 1000 do
    local female = i % 2 == 0
    local pool = if female then {a,b,c,d} else {a,b,c}
    local clip, group = reactions.Choose(pool, if female then 251 else 151, rng, recent)
    assert(clip and group and not table.find(recent, group), "repeated emotion")
    assert(female or group ~= "bow", "male bow")
    reactions.Remember(recent, group)
    assert(#recent <= 2)
    seen[clip.animationId] = true
end
for _, item in ipairs({a,b,c,d}) do
    for _, clip in ipairs(item.rows) do assert(seen[clip.animationId], "missing variant " .. clip.animationId) end
end
local clip, group = reactions.Choose({a,b}, 150, rng, {"laugh", "hi"})
assert(clip == nil and group == nil, "exhausted pool must skip")
local history = {"laugh", "hi"}
local only = reactions.Choose({a,b,c}, 151, rng, history)
assert(only.animationId == "sad_1")
assert(#history == 2 and history[1] == "laugh" and history[2] == "hi", "chooser must not mutate history")
print("[game1][m508] emotion history smoke passed")
