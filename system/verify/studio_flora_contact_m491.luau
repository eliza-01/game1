-- Studio Play / client Command Bar in the uncompiled authoring Place.
-- Simulate a Model arriving before its mesh, composite geometry and stream-out.
local player = game:GetService("Players").LocalPlayer
local Index = require(player.PlayerScripts.Game1Client.world.FloraContactIndex)
assert(Index.Start())
local position = Vector3.new(50000, 5000, 50000)
local model = Instance.new("Model")
model.Parent = workspace
local ok, err = pcall(function()
    model:SetAttribute("Game1DecoAssetSlug", "bush_02")
    task.wait()
    assert(not Index.Find(position, 0))
    local part = Instance.new("MeshPart")
    part.Size = Vector3.new(2, 2, 2)
    part.CFrame = CFrame.new(position)
    part.Anchored = true
    part.Parent = model
    task.wait()
    assert(Index.Find(position, 0), "late mesh missing from index")
    local second = part:Clone()
    second.CFrame = CFrame.new(position + Vector3.new(8, 0, 0))
    second.Parent = model
    task.wait()
    assert(Index.Find(second.Position, 0), "second component missing")
    part:Destroy()
    task.wait()
    assert(not Index.Find(position, 0), "removed mesh still indexed")
    model:SetAttribute("Game1DecoAssetSlug", "bush_01")
    task.wait()
    assert(not Index.Find(second.Position, 0), "retired identity still indexed")
    model:SetAttribute("Game1DecoAssetSlug", "christmas_tree")
    task.wait()
    assert(Index.Find(second.Position, 0), "published alias missing")
end)
model:Destroy()
assert(ok, err)
print("m491 flora contact smoke passed")
