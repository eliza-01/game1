-- Run from Studio client Command Bar. No world changes.
local player = assert(game:GetService("Players").LocalPlayer)
local Runner = require(player.PlayerScripts.Game1Client.character.CharacterLoadingRunner)
local gui = Instance.new("ScreenGui")
gui.Parent = player.PlayerGui
local glyph, pose = Runner.Build(gui, Color3.new(1, 1, 1), 103)
local ok, err = pcall(function()
    for _, sample in ipairs({{0, 0, true}, {0.5, 0.5, true}, {1, 1, false}, {1.5, 0.5, false}, {2, 0, true}}) do
        local x, right = Runner.Travel(sample[1])
        assert(x == sample[2] and right == sample[3], "Travel/direction")
    end
    -- Compare equal stride phases on opposite travel legs.
    pose(0)
    assert(glyph.Nose.Position.X.Offset > glyph.Head.Position.X.Offset, "Faces right")
    local positions = {}
    for _, part in ipairs(glyph:GetChildren()) do
        if part:IsA("Frame") then positions[part.Name] = {part.Position, part.Rotation} end
    end
    pose(2 / 1.65)
    assert(glyph.Nose.Position.X.Offset < glyph.Head.Position.X.Offset, "Faces left")
    for _, part in ipairs(glyph:GetChildren()) do
        if part:IsA("Frame") then
            local before = positions[part.Name]
            assert(math.abs(part.Position.X.Offset + before[1].X.Offset - Runner.Width) < 0.001, "Mirror X: " .. part.Name)
            assert(math.abs(part.Position.Y.Offset - before[1].Y.Offset) < 0.001, "Mirror Y: " .. part.Name)
            assert(math.abs(math.sin(math.rad(part.Rotation)) + math.sin(math.rad(before[2]))) < 0.001, "Mirror angle: " .. part.Name)
        end
    end
end)
gui:Destroy()
assert(ok, err)
print("[M509] loading runner travel and mirror OK")
