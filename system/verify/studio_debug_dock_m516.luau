-- Run from the CLIENT Command Bar in Studio Play, after entering the world.
local Players = game:GetService("Players")
local player = assert(Players.LocalPlayer, "Run in the client")
local playerGui = player:WaitForChild("PlayerGui")
local dock = require(player.PlayerScripts.Game1Client.dev.StudioDebugDock)
local screen = Instance.new("ScreenGui")
screen.Name = "M516Smoke"
screen.Parent = playerGui
local launcher = Instance.new("TextButton")
launcher.Parent = screen
local panel = Instance.new("Frame")
panel.Visible = false
panel.Parent = screen
dock.Bind("GP", launcher, panel, 440, true)
local neutral = launcher.BackgroundColor3
assert(not launcher.AutoButtonColor, "Hover should not highlight")
panel.Visible = true
task.wait()
assert(launcher.BackgroundColor3 ~= neutral, "Open panel not highlighted")
screen.Enabled = false
task.wait()
assert(launcher.BackgroundColor3 == neutral, "Hidden screen still highlighted")
screen.Enabled = true
panel.Visible = false
task.wait()
assert(launcher.BackgroundColor3 == neutral, "Closed panel still highlighted")
screen:Destroy()
local gp = assert(playerGui:FindFirstChild("Game1GameplayTestGui"), "Gameplay ScreenGui missing")
assert(gp.Enabled and gp:FindFirstChild("DebugLauncherGP"), "Gameplay launcher unavailable in world")
print("[M516] debug launcher visibility, highlight and GP presence OK")
