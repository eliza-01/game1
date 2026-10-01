local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Config = require(Shared:WaitForChild("AttackConfig"))
local DamageService = require(script.Parent:WaitForChild("DamageService"))
local Service = {}
local cooldowns = {}
local function modelFromPart(part: Instance): Model?
    local current = part
    while current and current ~= Workspace do
        if current:IsA("Model") and current:GetAttribute("Damageable") == true then return current end
        current = current.Parent
    end
    return nil
end
local function attack(player: Player, aim: any)
    if typeof(aim) ~= "Vector3" then return end
    local c=player.Character; local root=c and c:FindFirstChild("RootCollider"); if not (c and root and root:IsA("BasePart")) or c:GetAttribute("LifeState")~="Alive" then return end
    local now=os.clock(); if now-(cooldowns[player] or 0)<Config.CooldownSeconds then return end; cooldowns[player]=now
    local flat=Vector3.new(aim.X-root.Position.X,0,aim.Z-root.Position.Z); if flat.Magnitude<0.001 then flat=root.CFrame.LookVector end; local dir=flat.Unit
    local center=root.Position + dir*(Config.Range*.5)
    local boxCf=CFrame.lookAt(center, center+dir)
    local params=OverlapParams.new(); params.FilterType=Enum.RaycastFilterType.Exclude; params.FilterDescendantsInstances={c}
    local parts=Workspace:GetPartBoundsInBox(boxCf,Vector3.new(Config.BoxWidth,Config.BoxHeight,Config.Range),params)
    local seen={}
    local best,bestDist=nil,math.huge
    for _,part in ipairs(parts) do local m=modelFromPart(part); if m and not seen[m] then seen[m]=true; local r=m:FindFirstChild("RootCollider") or m.PrimaryPart; if r and r:IsA("BasePart") then local d=(r.Position-root.Position).Magnitude; if d<=Config.Range+1 and d<bestDist then best=m; bestDist=d end end end end
    c:SetAttribute("AttackSerial",(c:GetAttribute("AttackSerial") or 0)+1)
    if best then DamageService.Apply(c,best,tonumber(c:GetAttribute("Damage")) or 0) end
end
function Service.Start()
    local remotes=ReplicatedStorage:FindFirstChild("Game1Remotes") or Instance.new("Folder"); remotes.Name="Game1Remotes"; remotes.Parent=ReplicatedStorage
    local event=remotes:FindFirstChild("AttackIntent") or Instance.new("RemoteEvent"); event.Name="AttackIntent"; event.Parent=remotes; event.OnServerEvent:Connect(attack)
    Players.PlayerRemoving:Connect(function(p) cooldowns[p]=nil end)
end
return Service
