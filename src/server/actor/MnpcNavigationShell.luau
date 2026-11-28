-- Shared physical/navigation shell. No template, bones, Animator or combat geometry.
local ActorCollisionPolicy = require(script.Parent:WaitForChild("ActorCollisionPolicy"))
local Shell = {}
local ROOT_SIZE = Vector3.new(2, 2, 1)
local HIP_HEIGHT = 1.8

function Shell.Create(model: Model, surface: Vector3, yaw: number, kind: "Monster" | "NPC"): (BasePart, Humanoid)
    assert(model:FindFirstChild("HumanoidRootPart") == nil, "MNPC shell already exists")
    assert(kind == "Monster" or kind == "NPC", "Invalid MNPC kind")
    local root = Instance.new("Part")
    root.Name = "HumanoidRootPart"
    root.Size = ROOT_SIZE
    root.CFrame = CFrame.new(surface + Vector3.new(0, ROOT_SIZE.Y * 0.5 + HIP_HEIGHT, 0)) * CFrame.Angles(0, yaw, 0)
    root.Transparency = 1
    root.CastShadow = false
    root.Anchored = false
    ActorCollisionPolicy.Assign(root, kind)
    root.CanTouch = false
    root.CanQuery = false
    root.Massless = false
    root.Parent = model

    local humanoid = Instance.new("Humanoid")
    humanoid.Name = "Humanoid"
    humanoid.RequiresNeck = false
    humanoid.BreakJointsOnDeath = false
    humanoid.AutoRotate = true
    humanoid.HipHeight = HIP_HEIGHT
    humanoid.UseJumpPower = false
    humanoid.JumpHeight = 0
    humanoid.MaxSlopeAngle = 89
    humanoid:SetStateEnabled(Enum.HumanoidStateType.Jumping, false)
    if kind == "NPC" then
        -- Preserve M422: stationary NPCs must not sink into FallingDown on unpin.
        humanoid:SetStateEnabled(Enum.HumanoidStateType.FallingDown, false)
        humanoid:SetStateEnabled(Enum.HumanoidStateType.Ragdoll, false)
    end
    humanoid.WalkSpeed = 0
    humanoid.MaxHealth = 1
    humanoid.Health = 1
    humanoid.HealthDisplayType = Enum.HumanoidHealthDisplayType.AlwaysOff
    humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
    humanoid.NameDisplayDistance = 0
    humanoid.Parent = model
    model.PrimaryPart = root
    return root, humanoid
end

function Shell.Publish(model: Model, root: BasePart, destination: Folder)
    assert(model.PrimaryPart == root and root.Parent == model and model.Parent == nil, "Invalid MNPC shell publication")
    model.Parent = destination
    pcall(function() root:SetNetworkOwner(nil) end)
end

return table.freeze(Shell)
