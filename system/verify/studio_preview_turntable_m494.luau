-- Execute in Studio Play, CLIENT command bar, after Rojo sync.
-- Synthetic geometry, no changes to the Place or actual character profile.
local player = game:GetService("Players").LocalPlayer
assert(player, "run in client context")
local module = require(player.PlayerScripts.Game1Client.character.CharacterPreviewTurntable)
local part = Instance.new("Part")
part.Size = Vector3.new(2, 4, 2)
part.CFrame = CFrame.new(12, 5, 7) * CFrame.Angles(0, math.rad(30), 0)
part.Anchored = true
part.CanCollide = false
part.CanQuery = false
local ray = Ray.new(part.CFrame:PointToWorldSpace(Vector3.new(0, 0, -5)), part.CFrame.ZVector)
assert(math.abs(assert(module.HitDistance(part, ray)) - 4) < 0.001, "oriented bounds hit")
assert(module.HitDistance(part, Ray.new(part.CFrame:PointToWorldSpace(Vector3.new(3, 0, -5)), part.CFrame.ZVector)) == nil, "miss")
local angle = 0
for _ = 1, 120 do
    local nextAngle = module.Advance(angle, math.rad(35), 1/60)
    assert(nextAngle >= angle and nextAngle - angle <= math.rad(150)/60 + 0.000001, "bounded smooth motion")
    angle = nextAngle
end
assert(math.abs(angle - math.rad(35)) < 0.001, "converges to target")
local model = Instance.new("Model")
part.Parent = model
model.PrimaryPart = part
local models = {test = model}
local turntable = module.new(models, function() return false end)
local base = CFrame.new(4, 5, 6) * CFrame.Angles(0, math.rad(20), 0)
turntable:Place("test", model, base)
turntable.rotations.test.angle = angle
turntable.rotations.test.target = angle
local replacement = model:Clone()
turntable:Place("test", replacement, base)
local pivot = replacement:GetPivot()
assert((pivot.Position - base.Position).Magnitude < 0.001, "fixed pivot position")
local expected = CFrame.new(base.Position) * CFrame.Angles(0, angle, 0) * base.Rotation
assert(pivot.LookVector:Dot(expected.LookVector) > 0.99999, "angle retained on replacement")
turntable:Destroy()
model:Destroy()
replacement:Destroy()
print("[game1][m494] synthetic turntable smoke passed")
