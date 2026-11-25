-- Studio Play CLIENT command bar: synthetic selection policy and real registry.
local player = game:GetService("Players").LocalPlayer
local root = player.PlayerScripts.Game1Client.character
local reactions = require(root.CharacterCreationReactions)
local turn = require(root.CharacterPreviewTurntable)
local weights = {bow = 100, unaware = 100}
local registry = {profiles = {human_female = {family = "human", social = {
    bow = {{variant = 1, animationId = "rbxassetid://1"}, {variant = 2, animationId = "rbxassetid://2"}},
    unaware = {{variant = 1, animationId = "rbxassetid://3"}}}}, human_male = {family = "human", social = {
    bow = {{variant = 1, animationId = "rbxassetid://4"}}}}}, shared = {human = {social = {
        unaware = {{variant = 2, animationId = "rbxassetid://5", authoritative = true}}}}}}
local female, total = reactions.Pool(registry, "human_female", weights)
assert(#female == 2 and total == 200 and #female[1].rows == 2 and #female[2].rows == 2)
local male, maleTotal = reactions.Pool(registry, "human_male", weights)
assert(#male == 1 and male[1].group == "unaware" and maleTotal == 100)
local seen = {}
local rng = Random.new(505)
for _ = 1, 200 do seen[reactions.Choose(female, total, rng).animationId] = true end
for _, id in ipairs({1,2,3,5}) do assert(seen["rbxassetid://"..id], "missing variant "..id) end
assert(reactions.Choose({}, 0, rng) == nil)
local model = Instance.new("Model")
model.Parent = workspace
assert(turn.Target({human_female = model}, Vector2.new(-1000, -1000), "human_female", true) == "human_female")
model:Destroy()
print("[game1][m505] policy smoke passed; manually test UI drag, animation playback and hair following")
