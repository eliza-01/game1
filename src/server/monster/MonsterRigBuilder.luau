-- Visual rig preparation and physics navigation shell for a spawned monster.
-- This module does not own AI, animation playback, population or death.
local ActorCollisionPolicy = require(script.Parent.Parent:WaitForChild("actor"):WaitForChild("ActorCollisionPolicy"))
local MonsterRigBuilder = {}
local NAVIGATION_ROOT_SIZE = Vector3.new(2, 2, 1)
local NAVIGATION_HIP_HEIGHT = 1.8

local function visibleBounds(model: Model): (CFrame, Vector3)
    local minimum = Vector3.new(math.huge, math.huge, math.huge)
    local maximum = Vector3.new(-math.huge, -math.huge, -math.huge)
    local found = false
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("BasePart") and descendant.Name ~= "RootPart" and descendant.Name ~= "RootCollider" then
            found = true
            local half = descendant.Size * 0.5
            for x = -1, 1, 2 do
                for y = -1, 1, 2 do
                    for z = -1, 1, 2 do
                        local corner = descendant.CFrame:PointToWorldSpace(Vector3.new(half.X * x, half.Y * y, half.Z * z))
                        minimum = Vector3.new(math.min(minimum.X, corner.X), math.min(minimum.Y, corner.Y), math.min(minimum.Z, corner.Z))
                        maximum = Vector3.new(math.max(maximum.X, corner.X), math.max(maximum.Y, corner.Y), math.max(maximum.Z, corner.Z))
                    end
                end
            end
        end
    end
    if not found then
        return model:GetBoundingBox()
    end
    local size = maximum - minimum
    return CFrame.new((minimum + maximum) * 0.5), size
end

local function ensureRuntimeAnimationRoot(visual: Model): number
    -- Studio's Animation Editor exports skinned FBX clips with a synthetic
    -- RootBone pose above the authored skeleton root. Runtime Animator ignores
    -- animation on a Bone that is itself the root of a MeshPart hierarchy.
    -- Materialize that neutral RootBone in the runtime clone so the authored
    -- root bone (for example `spine`) becomes an ordinary animated child.
    --
    -- The helper is identity-only and is added before tracks are loaded. Existing
    -- authored Bone world/rest transforms are therefore unchanged. The navigation
    -- wrapper remains responsible only for world locomotion/yaw; animation owns
    -- the complete authored bone pose, including root-bone translation/rotation.
    local bridged = 0
    for _, descendant in ipairs(visual:GetDescendants()) do
        if descendant:IsA("MeshPart") then
            local directBones = {}
            local animationRoot: Bone? = nil
            for _, child in ipairs(descendant:GetChildren()) do
                if child:IsA("Bone") then
                    if child.Name == "RootBone" then
                        animationRoot = child
                    else
                        table.insert(directBones, child)
                    end
                end
            end

            if #directBones > 0 then
                if not animationRoot then
                    animationRoot = Instance.new("Bone")
                    animationRoot.Name = "RootBone"
                    animationRoot.CFrame = CFrame.identity
                    animationRoot.Parent = descendant
                    animationRoot:SetAttribute("Game1RuntimeAnimationRoot", true)
                    bridged += 1
                end

                for _, bone in ipairs(directBones) do
                    -- Preserve the authored rest/world transform even if a source
                    -- asset already supplied a non-identity RootBone.
                    local authoredMeshLocal = bone.CFrame
                    bone.Parent = animationRoot
                    bone.CFrame = animationRoot.CFrame:Inverse() * authoredMeshLocal
                end
            end
        end
    end

    visual:SetAttribute("Game1RuntimeAnimationRootBridgeCount", bridged)
    return bridged
end

local function prepareVisual(runtimeModel: Model): (Model, BasePart?)
    local visual = runtimeModel:FindFirstChild("ImportedRig")
    if not visual or not visual:IsA("Model") then
        visual = runtimeModel
    end
    for _, descendant in ipairs(runtimeModel:GetDescendants()) do
        if descendant:IsA("BasePart") then
            descendant.Anchored = false
            descendant.CanCollide = false
            descendant.CanTouch = false
            descendant.CanQuery = false
            descendant.Massless = true
        elseif descendant:IsA("Humanoid") then
            descendant:Destroy()
        end
    end
    local visualRoot = visual:FindFirstChild("RootPart", true)
        or visual.PrimaryPart
        or visual:FindFirstChildWhichIsA("MeshPart", true)
        or visual:FindFirstChildWhichIsA("BasePart", true)
    return visual :: Model, if visualRoot and visualRoot:IsA("BasePart") then visualRoot else nil
end

local function createNavigationRig(runtimeModel: Model, visual: Model, visualRoot: BasePart, surface: Vector3, yawRadians: number): (BasePart?, Humanoid?)
    -- Never weld every visual BasePart to the navigation root. Doing so turns an
    -- articulated Motor6D rig into one rigid physics assembly and can also fight
    -- imported rig constraints. Move the monster through one visual root only;
    -- all Bone/Motor6D articulation below that root remains animation-owned.
    local navigationRoot = Instance.new("Part")
    navigationRoot.Name = "HumanoidRootPart"
    navigationRoot.Size = NAVIGATION_ROOT_SIZE
    navigationRoot.CFrame = CFrame.new(
        surface + Vector3.new(0, NAVIGATION_ROOT_SIZE.Y * 0.5 + NAVIGATION_HIP_HEIGHT, 0)
    ) * CFrame.Angles(0, yawRadians, 0)
    navigationRoot.Transparency = 1
    navigationRoot.CastShadow = false
    navigationRoot.Anchored = false
    ActorCollisionPolicy.Assign(navigationRoot)
    navigationRoot.CanTouch = false
    navigationRoot.CanQuery = false
    navigationRoot.Massless = false
    navigationRoot.Parent = runtimeModel

    local boxCFrame, boxSize = visibleBounds(visual)
    local root = Instance.new("Part")
    root.Name = "RootCollider"
    -- Movement collider only. Combat uses precomputed bone-local mesh bounds.
    root.Size = Vector3.new(math.max(0.5, boxSize.X), math.max(0.5, boxSize.Y), math.max(0.5, boxSize.Z))
    root.CFrame = boxCFrame
    root.Transparency = 1
    root.CastShadow = false
    root.Anchored = false
    root.CanCollide = false
    root.CanTouch = false
    root.CanQuery = true
    root.Massless = true
    root.Parent = runtimeModel

    local rootWeld = Instance.new("WeldConstraint")
    rootWeld.Name = "RootColliderWeld"
    rootWeld.Part0 = navigationRoot
    rootWeld.Part1 = root
    rootWeld.Parent = navigationRoot

    local visualWeld = Instance.new("WeldConstraint")
    visualWeld.Name = "VisualRootWeld"
    visualWeld.Part0 = root
    visualWeld.Part1 = visualRoot
    visualWeld.Parent = root

    local humanoid = Instance.new("Humanoid")
    humanoid.Name = "Humanoid"
    humanoid.RequiresNeck = false
    humanoid.BreakJointsOnDeath = false
    humanoid.AutoRotate = true
    humanoid.HipHeight = NAVIGATION_HIP_HEIGHT
    humanoid.UseJumpPower = false
    humanoid.JumpHeight = 0
    humanoid.MaxSlopeAngle = 89
    humanoid:SetStateEnabled(Enum.HumanoidStateType.Jumping, false)
    humanoid.WalkSpeed = 0
    humanoid.MaxHealth = 1
    humanoid.Health = 1
    humanoid.HealthDisplayType = Enum.HumanoidHealthDisplayType.AlwaysOff
    humanoid.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
    humanoid.NameDisplayDistance = 0
    humanoid.Parent = runtimeModel

    runtimeModel.PrimaryPart = navigationRoot
    pcall(function() navigationRoot:SetNetworkOwner(nil) end)
    return navigationRoot, humanoid
end

local function groundAlign(model: Model, surface: Vector3, yawRadians: number)
    local sourcePivot = model:GetPivot()
    local sourceRotation = sourcePivot.Rotation
    model:PivotTo(CFrame.new(surface) * CFrame.Angles(0, yawRadians, 0) * sourceRotation)
    local boxCFrame, boxSize = visibleBounds(model)
    local bottomY = boxCFrame.Position.Y - boxSize.Y * 0.5
    model:PivotTo(model:GetPivot() + Vector3.new(0, surface.Y - bottomY, 0))
end

MonsterRigBuilder.PrepareVisual = prepareVisual
MonsterRigBuilder.EnsureRuntimeAnimationRoot = ensureRuntimeAnimationRoot
MonsterRigBuilder.CreateNavigationRig = createNavigationRig
MonsterRigBuilder.GroundAlign = groundAlign
return table.freeze(MonsterRigBuilder)
