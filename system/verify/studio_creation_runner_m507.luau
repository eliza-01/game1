-- Run in Studio client Command Bar during Play. No assets or world mutation.
local Players = game:GetService("Players")
local player = assert(Players.LocalPlayer, "Run on the client")
local scripts = player:WaitForChild("PlayerScripts"):WaitForChild("Game1Client")
local Runner = require(scripts:WaitForChild("character"):WaitForChild("CharacterLoadingRunner"))
local gui = Instance.new("ScreenGui")
gui.Name = "M507RunnerSmoke"
gui.Parent = player:WaitForChild("PlayerGui")
local glyph, pose = Runner.Build(gui, Color3.new(1, 1, 1), 103)
glyph.Position = UDim2.fromOffset(80, 80)
local function joints(name, length)
    local segment = glyph:FindFirstChild(name)
    assert(segment and segment:IsA("Frame"), name)
    local centre = Vector2.new(segment.Position.X.Offset, segment.Position.Y.Offset)
    local angle = math.rad(segment.Rotation)
    local half = Vector2.new(-math.sin(angle), math.cos(angle)) * length / 2
    return centre - half, centre + half
end
local ok, err = pcall(function()
    for frame = 0, 120 do
        pose(frame / 120 / 1.65)
        for _, side in ipairs({"Near", "Far"}) do
            for _, kind in ipairs({"Arm", "Leg"}) do
                local length = if kind == "Arm" then 7 else 9
                local origin = if kind == "Arm" then Vector2.new(23, 13) else Vector2.new(19, 24)
                local start, joint = joints(side .. kind .. "Upper", length)
                local joint2, tip = joints(side .. kind .. "Lower", length)
                assert((start - origin).Magnitude < 0.001, "Detached shoulder/hip")
                assert((joint - joint2).Magnitude < 0.001, "Detached elbow/knee")
                assert(tip.X >= 0 and tip.X <= Runner.Width and tip.Y >= 0 and tip.Y <= Runner.Height, "Outside runner")
            end
        end
    end
    pose(0)
    local initial = glyph.NearArmUpper.Position
    pose(1 / 1.65)
    assert(math.abs(glyph.NearArmUpper.Position.X.Offset - initial.X.Offset) < 0.001, "Cycle discontinuity")
end)
gui:Destroy()
assert(ok, err)
print("[M507] runner joints and cycle OK")
