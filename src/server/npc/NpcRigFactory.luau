-- One responsibility: turn a published articulated FBX into a stationary, combat-queryable world actor.
-- The visual is never used as a physics collider. Later navigation may replace the anchored world root.
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

local function bridgeRootBones(visual: Model): number
    -- The Studio FBX animation export expects a synthetic RootBone above the authored roots.
    local count = 0
    for _, item in ipairs(visual:GetDescendants()) do
        if item:IsA("MeshPart") then
            local topBones = {}
            local rootBone: Bone? = nil
            for _, child in ipairs(item:GetChildren()) do
                if child:IsA("Bone") then
                    if child.Name == "RootBone" then
                        rootBone = child
                    else
                        table.insert(topBones, child)
                    end
                end
            end
            if #topBones > 0 then
                if not rootBone then
                    rootBone = Instance.new("Bone")
                    rootBone.Name = "RootBone"
                    rootBone.CFrame = CFrame.identity
                    rootBone.Parent = item
                    count += 1
                end
                for _, bone in ipairs(topBones) do
                    local relative = bone.CFrame
                    bone.Parent = rootBone
                    bone.CFrame = rootBone.CFrame:Inverse() * relative
                end
            end
        end
    end
    return count
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
    root.Name = "NavigationRoot"
    root.Size = Vector3.new(2, 2, 1)
    root.CFrame = CFrame.new(surface + Vector3.new(0, 2.8, 0)) * CFrame.Angles(0, math.rad(yawDegrees), 0)
    root.Anchored = true -- NPCs do not move autonomously in the initial 1hs phase.
    root.Transparency = 1
    root.CanCollide = false
    root.CanQuery = false
    root.CanTouch = false
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
    model.PrimaryPart = root
    model:SetAttribute("RuntimeAnimationRootBridgeCount", bridgeRootBones(visual))
    return visual, root
end

return table.freeze(NpcRigFactory)
