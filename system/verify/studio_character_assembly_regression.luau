-- Run in Studio Play / Server after publishing the recipe dependencies.
-- Uses the active server tree; old folders may share its name in saved places.
local server
for _, candidate in game.ServerScriptService:GetChildren() do
    if candidate.Name == "Game1Server" and candidate:IsA("Script") then server = candidate end
end
assert(server, "active Game1Server Script missing")
local builder = require(server.character.CharacterAssemblyBuilder)
local registry = require(game.ReplicatedStorage.Game1Shared.character.CharacterRegistry)
local recipe
for _, row in registry.archetypes do
    if row.id == "human_male" then recipe = row.assembly end
end
assert(recipe and recipe.ready, "published human_male recipe required")
local cache = game.ServerStorage.game1CharacterCache
local function load(id)
    return assert(cache:FindFirstChild("component-" .. id), "component not loaded: " .. id)
end
local assembled = builder.Build(recipe, load)
local count = 0
for _, object in assembled:GetDescendants() do
    if object:IsA("MeshPart") and object:GetAttribute("CharacterPartSlot") then count += 1 end
end
assert(count == 8, "eight visible parts required")
assembled:Destroy()

-- A missing source influence pruned by import is accepted; an actual imported
-- bind mismatch must still fail, including bones other than the alignment bone.
local eyesId = tonumber(recipe.parts.eyes.asset_id)
local damaged = load(eyesId):Clone()
local eye = damaged:FindFirstChild("eyes_01", true)
local changed = eye:FindFirstChild("face_eye_seg08_l", true)
assert(changed, "fixture bone missing")
changed.CFrame *= CFrame.new(0.1, 0, 0)
local ok, reason = pcall(builder.Build, recipe, function(id)
    if id == eyesId then return damaged end
    return load(id)
end)
damaged:Destroy()
assert(not ok and string.find(tostring(reason), "incompatible bind", 1, true), "bad bind accepted")

-- Force a loader failure through the real CharacterService orchestration.
-- Preserve the current player and restore cache names even on failed assertions.
local player = assert(game.Players:GetPlayers()[1], "player required")
local previous = assert(player.Character, "spawned character required")
local cached = assert(cache:FindFirstChild("assembly-" .. recipe.fingerprint))
local savedName = cached.Name
local probe = Instance.new("ModuleScript")
probe.Name = "character_failure_probe"
local source = server.character.CharacterService.Source
local line = 'local CharacterAssemblyBuilder = require(script.Parent:WaitForChild("CharacterAssemblyBuilder"))'
local first, last = string.find(source, line, 1, true)
assert(first and last, "builder injection point missing")
probe.Source = string.sub(source, 1, first - 1)
    .. 'local CharacterAssemblyBuilder = { Build = function() error("injected assembly failure") end }'
    .. string.sub(source, last + 1)
probe.Parent = server.character
cached.Name = "probe_saved_assembly"
local oldError = player:GetAttribute("CharacterLoadError")
local spawnOk, result = pcall(function() return require(probe).Respawn(player, "human_male") end)
cached.Name = savedName
probe:Destroy()
local reported = player:GetAttribute("CharacterLoadError")
player:SetAttribute("CharacterLoadError", oldError)
assert(spawnOk and result == nil and player.Character == previous, "failure replaced current character")
assert(string.find(tostring(reported), "injected assembly failure", 1, true), "load error was hidden")
assert(previous:GetAttribute("CharacterArchetype") == "human_male", "wrong live character")
assert(previous:GetAttribute("UsingBootstrapVisual") == false, "bootstrap substitution")
return { pass = true, realPublishedParts = count, corruptBindRejected = true, failurePreservesPlayer = true }
