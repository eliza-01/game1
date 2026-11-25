-- Client Command Bar during Studio Play, after entering the world. Read-only layout smoke.
local player = assert(game:GetService("Players").LocalPlayer)
local gui = assert(player.PlayerGui:FindFirstChild("Game1GameplayTestGui"))
local panel = assert(gui:FindFirstChild("Panel"))
local body = assert(panel:FindFirstChild("Body"))
local old = player.PlayerGui:GetAttribute("Game1DebugPanelOpen")
player.PlayerGui:SetAttribute("Game1DebugPanelOpen", "GP")
task.wait()
assert(panel.Visible and panel.AnchorPoint == Vector2.new(0, 1))
assert(panel.Position == UDim2.new(0, 8, 1, -8))
for _, pair in ipairs({{"Level", "Weapon"}, {"Armor", "Upgrade"}, {"Monster", "Group"}, {"Regeneration", "Vampiric"}}) do
    local left = assert(body:FindFirstChild(pair[1], true))
    local right = assert(body:FindFirstChild(pair[2], true))
    assert(left.Parent == right.Parent, "Cells not paired")
    assert(left.AbsolutePosition.X < right.AbsolutePosition.X, "Cell order")
    assert(math.abs(left.AbsoluteSize.X - right.AbsoluteSize.X) <= 1, "Unequal columns")
end
player.PlayerGui:SetAttribute("Game1DebugPanelOpen", old)
print("[M522] Gameplay compact layout OK; manually test grade clamp, recovery and Apply/Go closing")
