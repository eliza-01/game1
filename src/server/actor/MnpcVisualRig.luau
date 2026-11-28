-- Attach a published rig to an already existing navigation shell.
-- All geometry preparation is isolated in a staging clone; never PivotTo the entity.
-- Returns a presentation lease for exact geometry/equipment ownership.
-- Domain owners quiesce animation/AI/hitbox consumers before releasing it.
local Shell = require(script.Parent:WaitForChild("MnpcNavigationShell"))
local Geometry = require(script.Parent:WaitForChild("MnpcRigGeometry"))
local PresentationLifecycle = require(script.Parent:WaitForChild("MnpcPresentationLifecycle"))
local VisualRig = {}

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
    local boundsModel = staged
    if kind == "NPC" then boundsModel = visual end
    local boundsFrame, boundsSize = Geometry.VisibleBounds(boundsModel)
    staged:PivotTo(staged:GetPivot() + Vector3.new(0, surface.Y - (boundsFrame.Position.Y - boundsSize.Y * 0.5), 0))
end

local function bindVisual(navigationRoot: BasePart, collider: BasePart, visualRoot: BasePart, skillCaster: boolean)
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
    return visualWeld
end

function VisualRig.Attach(model: Model, navigationRoot: BasePart, template: Model, surface: Vector3, yaw: number, kind: "Monster" | "NPC", prepared: any?): (Model?, any?)
    assert(navigationRoot.Parent == model and model.PrimaryPart == navigationRoot, "MNPC shell required")
    assert(model:GetAttribute("Game1MnpcKind") == kind, "MNPC rig kind mismatch")
    assert(model:FindFirstChild("ImportedRig") == nil, "MNPC visual already attached")
    local collider = model:FindFirstChild("RootCollider")
    if prepared then
        assert(prepared.root == navigationRoot and prepared.collider == collider and collider ~= nil
            and prepared.geometry.template == template and prepared.geometry.kind == kind, "MNPC shell plan mismatch")
        assert(collider:FindFirstChild("VisualRootWeld") == nil, "MNPC visual already attached")
        if not Geometry.IsCurrent(prepared.geometry) then return nil end
    else
        assert(collider == nil, "MNPC prepared shell requires its plan")
    end
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
    local boxCFrame, boxSize
    if prepared then
        -- Rebase on the *current* root, not on the original spawn position.
        staged:PivotTo(navigationRoot.CFrame * prepared.geometry.pivotOffset)
    else
        -- Explicit compatibility path for unsupported template geometry.
        groundAlign(staged, visual, surface, yaw, kind)
        boxCFrame, boxSize = Geometry.VisibleBounds(visual)
    end
    local owned = {}
    if visual == staged then
        staged.Name = "ImportedRig"
        staged.Parent = model
        table.insert(owned, staged)
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
            table.insert(owned, child)
        end
        staged:Destroy()
    end
    local fallbackRootWeld = nil
    if not collider then
        collider, fallbackRootWeld = Shell.CreateQueryCollider(model, navigationRoot, boxCFrame, boxSize)
    end
    local weld = bindVisual(navigationRoot, collider, visualRoot, kind == "Monster" and model:GetAttribute("MonsterSkillCaster") == true)
    local lease = PresentationLifecycle.new(model, visual, collider, weld, owned, fallbackRootWeld)
    collider.CanQuery = true
    return visual, lease
end

return table.freeze(VisualRig)
