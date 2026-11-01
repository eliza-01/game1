-- Command Bar: Run in Studio Play, with server context selected.
-- Tests the real runtime MeshPart binding without publishing any assets.
local server = assert(game.ServerScriptService:FindFirstChild("Game1Server"), "Game1Server not found")
local character = assert(server:FindFirstChild("character"), "character modules not found")
local binder = require(character:WaitForChild("CharacterAtlasBinder"))
local imageId = "130840873415092" -- published upper atlas in diagnostic 2026-10-31

local mesh = Instance.new("MeshPart")
mesh.Name = "AtlasBindingProbe"
local original = Instance.new("SurfaceAppearance")
original.Parent = mesh

local ok, report = pcall(function()
    assert(binder.Apply(mesh, "") == false, "empty ID must keep authored appearance")
    assert(original.Parent == mesh, "untouched material was removed")
    local badOk = pcall(binder.Apply, mesh, "bad-id")
    assert(not badOk and original.Parent == mesh, "invalid ID was accepted or mutated the mesh")

    assert(binder.Apply(mesh, imageId), "published image ID was not applied")
    assert(mesh.TextureID == "rbxassetid://" .. imageId, "wrong Image Asset URI")
    assert(not mesh:FindFirstChildOfClass("SurfaceAppearance"), "old material masks new atlas")
    return "Atlas binding OK: " .. mesh.TextureID
end)
mesh:Destroy()
assert(ok, tostring(report))
print("[game1][M179] " .. report)
return { pass = true, publishedImageId = imageId }
