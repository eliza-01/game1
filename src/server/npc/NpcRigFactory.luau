-- Build a mobile world actor without changing any imported bone or skinning data.
-- Navigation uses the same elevated HumanoidRootPart principle as monsters;
-- RootCollider remains a separate, non-colliding combat query reference.
local ActorCollisionPolicy = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorCollisionPolicy"))
local NpcRigFactory = {}

local function visibleBounds(model: Model): (CFrame, Vector3)
    local low = Vector3.new(math.huge, math.huge, math.huge)
    local high = Vector3.new(-math.huge, -math.huge, -math.huge)
    local found = false
    for _, item in ipairs(model:GetDescendants()) do
        if item:IsA("BasePart") and item.Name ~= "RootPart" and item.Name ~= "RootCollider" then
            found = true
            local h = item.Size * 0.5
            for x = -1, 1, 2 do
                for y = -1, 1, 2 do
                    for z = -1, 1, 2 do
                        local v = item.CFrame:PointToWorldSpace(Vector3.new(h.X * x, h.Y * y, h.Z * z))
                        low = Vector3.new(math.min(low.X, v.X), math.min(low.Y, v.Y), math.min(low.Z, v.Z))
                        high = Vector3.new(math.max(high.X, v.X), math.max(high.Y, v.Y), math.max(high.Z, v.Z))
                    end
                end
            end
        end
    end
    if not found then
        return model:GetBoundingBox()
    end
    return CFrame.new((low + high) * 0.5), high - low
end

function NpcRigFactory.Create(model: Model, surface: Vector3, yawDegrees: number): (Model?, BasePart?)
    local visual = model:FindFirstChild("ImportedRig")
    if not visual or not visual:IsA("Model") then
        visual = model
    end
    for _, item in ipairs(model:GetDescendants()) do
        if item:IsA("BasePart") then
            item.Anchored = false
            item.CanCollide = false
            item.CanTouch = false
            item.CanQuery = false
            item.Massless = true
        elseif item:IsA("Humanoid") then
            item:Destroy()
        end
    end
    -- The published rig owns the bone hierarchy. Never insert a runtime RootBone or
    -- reparent authored bones: that changes how imported animation tracks bind.
    -- Keep the same invariant as CharacterRigService (root parts/welds are separate).
    local visualRoot = visual:FindFirstChild("RootPart", true)
        or visual.PrimaryPart
        or visual:FindFirstChildWhichIsA("MeshPart", true)
        or visual:FindFirstChildWhichIsA("BasePart", true)
    if not visualRoot or not visualRoot:IsA("BasePart") then
        return nil, nil
    end
    model:PivotTo(CFrame.new(surface) * CFrame.Angles(0, math.rad(yawDegrees), 0) * model:GetPivot().Rotation)
    local boundsFrame, boundsSize = visibleBounds(visual)
    model:PivotTo(model:GetPivot() + Vector3.new(0, surface.Y - (boundsFrame.Position.Y - boundsSize.Y * 0.5), 0))
    boundsFrame, boundsSize = visibleBounds(visual)

    local root = Instance.new("Part")
    root.Name = "HumanoidRootPart"
    root.Size = Vector3.new(2, 2, 1)
    root.CFrame = CFrame.new(surface + Vector3.new(0, 2.8, 0)) * CFrame.Angles(0, math.rad(yawDegrees), 0)
    root.Anchored = false
    root.Transparency = 1
    ActorCollisionPolicy.Assign(root)
    root.CanQuery = false
    root.CanTouch = false
    root.Massless = false
    root.CastShadow = false
    root.Parent = model

    local collider = Instance.new("Part")
    collider.Name = "RootCollider"
    collider.Size = Vector3.new(math.max(0.5, boundsSize.X), math.max(0.5, boundsSize.Y), math.max(0.5, boundsSize.Z))
    collider.CFrame = boundsFrame
    collider.Anchored = false
    collider.Transparency = 1
    collider.CanCollide = false
    collider.CanQuery = true -- bone-aligned hitbox cache uses this stable root space.
    collider.CanTouch = false
    collider.Massless = true
    collider.Parent = model

    local colliderWeld = Instance.new("WeldConstraint")
    colliderWeld.Part0 = root
    colliderWeld.Part1 = collider
    colliderWeld.Parent = root
    local visualWeld = Instance.new("WeldConstraint")
    visualWeld.Part0 = collider
    visualWeld.Part1 = visualRoot
    visualWeld.Parent = collider
    local humanoid = Instance.new("Humanoid")
    humanoid.Name = "Humanoid"
    humanoid.RequiresNeck = false
    humanoid.BreakJointsOnDeath = false
    humanoid.AutoRotate = true
    humanoid.HipHeight = 1.8
    humanoid.UseJumpPower = false
    humanoid.JumpHeight = 0
    humanoid.MaxSlopeAngle = 89
    humanoid:SetStateEnabled(Enum.HumanoidStateType.Jumping, false)
    humanoid.WalkSpeed = 0
    -- Gameplay health is owned exclusively by DamageService, not Humanoid.
    humanoid.MaxHealth = 1
    humanoid.Health = 1
    humanoid.HealthDisplayType = Enum.HumanoidHealthDisplayType.AlwaysOff
    humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
    humanoid.NameDisplayDistance = 0
    humanoid.Parent = model

    model.PrimaryPart = root
    pcall(function() root:SetNetworkOwner(nil) end)
    return visual, root
end

return table.freeze(NpcRigFactory)
