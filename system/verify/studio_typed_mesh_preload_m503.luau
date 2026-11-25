-- Studio Play CLIENT command bar, after Character Creation templates arrive.
-- Uses actual published mesh instances, without changing a player or template.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
assert(RunService:IsClient(), "Run in the CLIENT command bar during Play")
local preloader = require(Players.LocalPlayer.PlayerScripts.Game1Client.character.CharacterCreationMeshPreloader)
local folder = ReplicatedStorage:WaitForChild("Game1CharacterCreationTemplates", 15)
assert(folder, "preview templates missing")
local count, parts = 0, 0
for _, template in ipairs(folder:GetChildren()) do
    if not template:IsA("Model") then continue end
    local meshes = {}
    for _, object in ipairs(template:GetDescendants()) do
        if object:IsA("MeshPart") then
            meshes[object] = {id = object.MeshId, texture = object.TextureID, parent = object.Parent}
            parts += 1
        end
    end
    local complete, geometryReady = preloader.PreloadModel(template, function() return template.Parent == folder end)
    assert(geometryReady, "typed geometry preload failed: " .. template.Name)
    for object, before in pairs(meshes) do
        assert(object.MeshId == before.id and object.TextureID == before.texture and object.Parent == before.parent,
            "preload mutated source mesh")
    end
    print("[m503] " .. template.Name .. " geometry ready; ordinary textures complete=" .. tostring(complete))
    count += 1
end
assert(count > 0 and parts > 0, "no actual mesh templates tested")
print(string.format("[m503] %d templates, %d mesh instances verified", count, parts))
