-- Attach a published rig to an already existing navigation shell.
-- All geometry preparation is isolated in a staging clone; never PivotTo the entity.
-- Caller owns animation/weapon/hitbox lifetimes; this module creates no tracks.
local VisualRig = {}

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

local function groundAlign(staged: Model, visual: Model, surface: Vector3, yaw: number, kind: string)
    staged:PivotTo(CFrame.new(surface) * CFrame.Angles(0, yaw, 0) * staged:GetPivot().Rotation)
    -- Preserve the two existing ground alignment policies; NPC uses ImportedRig
    -- bounds while Monster uses the published wrapper bounds.
    local boundsFrame, boundsSize = visibleBounds(if kind == "NPC" then visual else staged)
    staged:PivotTo(staged:GetPivot() + Vector3.new(0, surface.Y - (boundsFrame.Position.Y - boundsSize.Y * 0.5), 0))
end

local function bindCollider(model: Model, navigationRoot: BasePart, visualRoot: BasePart, boxCFrame: CFrame, boxSize: Vector3, skillCaster: boolean)
    local collider = Instance.new("Part")
    collider.Name = "RootCollider"
    -- Query reference for existing mathematical combat OBB; not a physical body.
    collider.Size = Vector3.new(math.max(0.5, boxSize.X), math.max(0.5, boxSize.Y), math.max(0.5, boxSize.Z))
    collider.CFrame = boxCFrame
    collider.Transparency = 1
    collider.CastShadow = false
    collider.Anchored = false
    collider.CanCollide = false
    collider.CanTouch = false
    collider.CanQuery = true
    collider.Massless = true
    collider.Parent = model
    local rootWeld = Instance.new("WeldConstraint")
    rootWeld.Name = "RootColliderWeld"
    rootWeld.Part0 = navigationRoot
    rootWeld.Part1 = collider
    rootWeld.Parent = navigationRoot
    local visualWeld
    if skillCaster then
        navigationRoot.RootPriority = 127
        local castWeld = Instance.new("Weld")
        castWeld.C0 = collider.CFrame:ToObjectSpace(visualRoot.CFrame)
        visualWeld = castWeld
    else
        visualWeld = Instance.new("WeldConstraint")
    end
    visualWeld.Name = "VisualRootWeld"
    visualWeld.Part0 = collider
    visualWeld.Part1 = visualRoot
    visualWeld.Parent = collider
end

function VisualRig.Attach(model: Model, navigationRoot: BasePart, template: Model, surface: Vector3, yaw: number, kind: "Monster" | "NPC"): Model?
    assert(navigationRoot.Parent == model and model.PrimaryPart == navigationRoot, "MNPC shell required")
    assert(model:GetAttribute("Game1MnpcKind") == kind, "MNPC rig kind mismatch")
    assert(model:FindFirstChild("RootCollider") == nil and model:FindFirstChild("ImportedRig") == nil, "MNPC visual already attached")
    local staged = template:Clone()
    if not staged then return nil end
    local visual, visualRoot = prepareVisual(staged)
    if not visualRoot then
        staged:Destroy()
        return nil
    end
    -- A canonical wrapper contains ImportedRig; preserve its child hierarchy,
    -- including animation hosts and references within the clone. An unwrapped
    -- source is attached as a single ImportedRig rather than owning the entity.
    groundAlign(staged, visual, surface, yaw, kind)
    local boxCFrame, boxSize = visibleBounds(visual)
    if visual == staged then
        staged.Name = "ImportedRig"
        staged.Parent = model
    else
        -- Do not overwrite the navigation shell with a source runtime helper.
        for _, child in ipairs(staged:GetChildren()) do
            if child.Name == "HumanoidRootPart" or child.Name == "RootCollider" then
                staged:Destroy()
                return nil
            end
        end
        for _, child in ipairs(staged:GetChildren()) do
            child.Parent = model
        end
        staged:Destroy()
    end
    bindCollider(model, navigationRoot, visualRoot, boxCFrame, boxSize, kind == "Monster" and model:GetAttribute("MonsterSkillCaster") == true)
    return visual
end

return table.freeze(VisualRig)
