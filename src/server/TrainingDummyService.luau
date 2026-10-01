local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local Service = {}
function Service.Start()
    if not RunService:IsStudio() or Workspace:FindFirstChild("game1TrainingDummy") then return end
    local spawn = Workspace:FindFirstChildWhichIsA("SpawnLocation", true)
    local m=Instance.new("Model"); m.Name="game1TrainingDummy"; m:SetAttribute("Damageable",true); m:SetAttribute("Level",1); m:SetAttribute("MaxHP",100); m:SetAttribute("HP",100); m:SetAttribute("Damage",0); m:SetAttribute("Defense",0); m:SetAttribute("LifeState","Alive")
    local p=Instance.new("Part"); p.Name="RootCollider"; p.Size=Vector3.new(3,5,3); p.Anchored=true; p.Position=(spawn and spawn.Position or Vector3.zero)+Vector3.new(0,2.5,-6); p.Parent=m; m.PrimaryPart=p; m.Parent=Workspace
    m:GetAttributeChangedSignal("HP"):Connect(function() if (m:GetAttribute("HP") or 0)<=0 then task.delay(2,function() if m.Parent then m:SetAttribute("HP",100);m:SetAttribute("LifeState","Alive") end end) end end)
end
return Service
