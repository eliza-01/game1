-- Studio server Command Bar in Play: actual policy and facing goal smoke.
local server = game:GetService("ServerScriptService").Game1Server
local Target = require(server.monster.MonsterTargetPolicy)
local Facing = require(server.actor.ActorFacingTracker)
local folder = Instance.new("Folder")
folder.Parent = workspace
local origin = Vector3.new(0, 10000, 0)
local function actor(name, position)
    local model = Instance.new("Model")
    model.Name = name
    local root = Instance.new("Part")
    root.Name = "HumanoidRootPart"
    root.Size = Vector3.one
    root.Anchored = true
    root.Position = position
    root.Parent = model
    model.PrimaryPart = root
    model:SetAttribute("Damageable", true)
    model:SetAttribute("LifeState", "Alive")
    model.Parent = folder
    return model, root
end
local monster, root = actor("Source", origin)
local victim, targetRoot = actor("Target", origin + Vector3.new(0, 0, -3))
local humanoid = Instance.new("Humanoid")
humanoid.RequiresNeck = false
humanoid.AutoRotate = true
humanoid.Parent = monster
monster:SetAttribute("MonsterAttackRadius", 5)
local agent = {model = monster, root = root}
local ok, err = pcall(function()
    for _, kind in ipairs({"melee", "ranged"}) do
        monster:SetAttribute("MonsterCombatType", kind)
        for _, direction in ipairs({Vector3.xAxis, -Vector3.xAxis, Vector3.zAxis, -Vector3.zAxis}) do
            targetRoot.Position = origin + direction * 3
            assert(Target.AttackStillConnects(agent, victim), kind .. " orbit must not evade")
            Facing.Track(monster, root, humanoid, victim, Target.RootOf, true)
            local align = root:FindFirstChild("Game1AttackFacing")
            assert(align and align.RigidityEnabled and not humanoid.AutoRotate)
            assert(align.CFrame.LookVector:Dot(direction) > 0.999)
        end
    end
    targetRoot.Position = origin + Vector3.xAxis * 3
    task.wait(0.1)
    assert(root.Game1AttackFacing.CFrame.LookVector:Dot(Vector3.xAxis) > 0.999)
    targetRoot.Position = origin + Vector3.xAxis * 6
    assert(not Target.AttackStillConnects(agent, victim), "out of range")
    targetRoot.Position = origin + Vector3.new(3, 6, 0)
    assert(not Target.AttackStillConnects(agent, victim), "vertical tolerance")
    targetRoot.Position = origin + Vector3.xAxis * 3
    local wall = Instance.new("Part")
    wall.Anchored = true
    wall.Size = Vector3.new(0.5, 4, 4)
    wall.Position = origin + Vector3.xAxis * 1.5
    wall.Parent = folder
    assert(not Target.AttackStillConnects(agent, victim), "blocked LOS")
    wall:Destroy()
    victim:SetAttribute("LifeState", "Dead")
    assert(not Target.AttackStillConnects(agent, victim), "dead target")
    victim:SetAttribute("LifeState", "Alive")
    victim:SetAttribute("Game1GameplayTestOwner", 123)
    assert(not Target.AttackStillConnects(agent, victim), "GP isolation")
    Facing.Stop(monster)
    assert(not root:FindFirstChild("Game1AttackFacing") and humanoid.AutoRotate)
    Facing.Track(monster, root, humanoid, victim, Target.RootOf)
    assert(not root.Game1AttackFacing.RigidityEnabled, "default NPC mode unchanged")
end)
Facing.Stop(monster)
folder:Destroy()
assert(ok, err)
print("[M536] target lock geometry, live facing goal, cleanup and default mode OK")
