-- Studio Play, SERVER Command Bar: actual assembly resolution and rigid mount.
-- No player/profile/place mutations; all synthetic instances are destroyed.
local Shared = game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
local Appearance = require(game:GetService("ServerScriptService").Game1Server.character.CharacterCreationAppearanceService)
local Align = require(Shared.rig.AuthoredPropSocketMount)
local Facing = require(Shared.world.SocketFacing)
for _, id in {"human_male", "human_female"} do
    local recipe, checked = Appearance.Resolve(id, {colors = {eyes = {l = "#123456", r = "#ABCDEF"}}})
    assert(recipe and checked, "independent eye colors rejected")
    assert(recipe.parts.eye_l.color == "#123456" and recipe.parts.eye_r.color == "#ABCDEF")
    assert(checked.colors.eyes.l == "#123456" and checked.colors.eyes.r == "#ABCDEF")
    local legacy, normalized = Appearance.Resolve(id, {colors = {eyes = "#abcd12"}})
    assert(legacy.parts.eye_l.color == "#ABCD12" and legacy.parts.eye_r.color == "#ABCD12")
    assert(normalized.colors.eyes.l == normalized.colors.eyes.r)
    local invalid, _, problem = Appearance.Resolve(id, {colors = {eyes = {l = "invalid"}}})
    assert(not invalid and problem == "invalid_eyes_color")
end
local model = Instance.new("Model")
local targetPart = Instance.new("Part")
local function part(name, position)
    local p = Instance.new("Part")
    p.Name = name; p.Anchored = true; p.CFrame = position; p.Parent = model
    return p
end
local ok, problem = pcall(function()
    local carrier = part("rig_carrier", CFrame.new(1, 2, 3))
    model.PrimaryPart = carrier
    local visual = part("padlock_02", CFrame.new(4, 5, 6) * CFrame.Angles(0, 0.4, 0))
    local hole = Instance.new("Bone")
    hole.Name = "padlock_01_hole_socket"; hole.CFrame = CFrame.new(0.2, 0.3, -0.1); hole.Parent = visual
    targetPart.Anchored = true
    targetPart.CFrame = CFrame.new(20, 7, -9) * CFrame.Angles(0.2, 0.5, 0.1)
    local target = Instance.new("Bone"); target.Parent = targetPart
    target.CFrame = CFrame.new(0, 0.5, 0)
    local success, reason = Align.Align(model, hole.Name, target)
    assert(success, tostring(reason))
    local a = Facing.FullFrame(hole.TransformedWorldCFrame, true)
    local b = Facing.FullFrame(target.TransformedWorldCFrame, true)
    assert((a.Position - b.Position).Magnitude < 0.001 and a.LookVector:Dot(b.LookVector) > 0.99999)
    local second = part("duplicate", CFrame.new(-10, 0, 0))
    local duplicate = hole:Clone(); duplicate.Parent = second
    local rejected, why = Align.Align(model, hole.Name, target)
    assert(not rejected and why == "conflicting_visual_grips")
    duplicate:Destroy(); hole:Destroy()
    local missing, missingWhy = Align.Align(model, "padlock_01_hole_socket", target)
    assert(not missing and missingWhy == "missing_authored_grip")
end)
model:Destroy(); targetPart:Destroy()
assert(ok, tostring(problem))
print("M487 Studio appearance / authored prop alignment: OK")
