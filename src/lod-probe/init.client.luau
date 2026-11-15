-- Standalone Studio-only probe. Runs independently of game1 client controllers.
local RunService = game:GetService("RunService")
if not RunService:IsStudio() then return end

local Players = game:GetService("Players")
local player = Players.LocalPlayer
if not player then
    warn("[game1][LOD probe] No LocalPlayer; use Test > Play, not Edit mode")
    return
end

print("[game1][LOD probe] Standalone client starting")
local scripts = player:WaitForChild("PlayerScripts", 10)
local client = scripts and scripts:WaitForChild("Game1Client", 10)
local world = client and client:WaitForChild("world", 10)
local module = world and world:WaitForChild("LocationLodStudioProbe", 10)
if not module then
    warn("[game1][LOD probe] Module missing in PlayerScripts.Game1Client.world; check Rojo sync")
    return
end

local ok, err = pcall(function()
    require(module).Start()
end)
if not ok then
    warn("[game1][LOD probe] Startup failed: " .. tostring(err))
end
