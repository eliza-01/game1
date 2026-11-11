-- M280 Studio Play / Command Bar smoke: verify the 3D authored Bone axis,
-- ordinary Attachment direction and world-upright spawn behavior.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Orientation = require(Shared.world.SocketFacing)
local Spawn = require(Shared.world.HouseSpawnOrientation)
local sample = CFrame.new(2, 4, -8) * CFrame.Angles(math.rad(10), math.rad(35), math.rad(25))
local boneFrame = Orientation.FullFrame(sample, true)
assert((boneFrame.LookVector + sample.UpVector).Magnitude < 0.00001,
    "Bone front must point Tail -> Head")
assert((boneFrame.UpVector - sample.LookVector).Magnitude < 0.00001,
    "Bone roll must be preserved, not replaced with a world-up guess")
assert(Orientation.FullFrame(sample, false) == sample, "Attachments are already Roblox -Z forward")
local spawn = Spawn.Upright(sample, true, 3)
assert(spawn, "tilted test Bone should define a horizontal forward")
assert(math.abs(spawn.LookVector.Y) < 0.00001, "avatar must remain upright")
assert((spawn.Position - (sample.Position + Vector3.yAxis * 3)).Magnitude < 0.00001)
print("M280 directional Bone socket smoke passed")
