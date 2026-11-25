-- Studio EDIT mode Command Bar, after stopping Play. Exact retired instances only.
assert(not game:GetService("RunService"):IsRunning(), "Stop Play before cleanup")
local history = game:GetService("ChangeHistoryService")
local scripts = game:GetService("StarterPlayer"):FindFirstChild("StarterPlayerScripts")
local removed = 0
history:SetWaypoint("Before M506 retired debug cleanup")
if scripts then
    for _, child in ipairs(scripts:GetChildren()) do
        if child.Name == "Game1LodProbeClient" and child:IsA("LuaSourceContainer") then
            child:Destroy()
            removed += 1
        end
    end
end
for _, child in ipairs(workspace:GetChildren()) do
    if child.Name == "game1TrainingDummy" and child:IsA("Model") then
        child:Destroy()
        removed += 1
    end
end
history:SetWaypoint("M506 retired debug cleanup")
print(("[game1][m506] removed %d retired instance(s); save Place"):format(removed))
