-- Studio Play CLIENT command bar; no authoring Place mutation.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
assert(RunService:IsClient(), "run in client command bar")
local Assembly = require(Players.LocalPlayer.PlayerScripts.Game1Client.world.LocationLodAssembly)
local prototype = Instance.new("Model")
local frame = CFrame.new(15, 3, 9) * CFrame.Angles(0, 0.2, 0)
prototype:SetAttribute("Game1LodPublishedPivot", frame)
prototype:SetAttribute("Game1LodVisualCount", 2)
local function mesh(name, size, offset)
    local part = Instance.new("MeshPart")
    part.Name = name
    part.Size = size
    part.CFrame = frame * CFrame.new(offset)
    part.Parent = prototype
    return part
end
local trunk = mesh("trunk_lod1", Vector3.new(2,4,2), Vector3.new(0,2,0))
assert(Assembly.Count(prototype) == 0, "partial replica accepted")
local crown = mesh("crown", Vector3.new(4,4,4), Vector3.new(0,6,0))
assert(Assembly.Count(prototype) == 2)
local target = CFrame.new(-90, 12, 34) * CFrame.Angles(0, 1.2, 0)
local full = {{CFrame=target*CFrame.new(0,8,0), Size=Vector3.new(8,16,8)}}
local clone, reason = Assembly.Create(prototype, target, full, function(part)
    local name = Assembly.AppearanceName(part, {trunk=true,crown=true})
    assert(name, "appearance mapping failed")
    part.Color = if name == "trunk" then Color3.new(0.5,0.2,0.1) else Color3.new(0,1,0)
end)
assert(clone, tostring(reason))
local a = clone:FindFirstChild("trunk_lod1")
local b = clone:FindFirstChild("crown")
assert(a and b and a:IsA("MeshPart") and b:IsA("MeshPart"))
assert((a.Size-trunk.Size*2).Magnitude < 0.01 and (b.Size-crown.Size*2).Magnitude < 0.01)
assert((target:PointToObjectSpace(a.Position)-Vector3.new(0,4,0)).Magnitude < 0.01)
assert((target:PointToObjectSpace(b.Position)-Vector3.new(0,12,0)).Magnitude < 0.01)
assert(a.Color ~= b.Color and a.Anchored and not a.CanCollide and not a.CanTouch and not a.CanQuery)
assert(a.CFrame.RightVector:Dot(target.RightVector) > 0.999)
assert(trunk.Parent == prototype and crown.Parent == prototype)
clone:Destroy()
prototype:Destroy()
local cache = ReplicatedStorage:WaitForChild("Game1StudioLodTemplates", 30)
assert(cache, "Studio LOD preview cache missing")
for _, id in ipairs({"71005212477453", "93826309717536"}) do
    local published = cache:WaitForChild(id, 30)
    local deadline = os.clock()+10
    while published and Assembly.Count(published) == 0 and os.clock() < deadline do task.wait() end
    assert(published and Assembly.Count(published) == 2, "published multipart LOD not ready: " .. id)
    print("[m504] multipart template ready: " .. id)
end
print("[m504] synthetic geometry and both published prototypes passed")
