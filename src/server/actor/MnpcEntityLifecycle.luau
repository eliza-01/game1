-- Shared MNPC construction boundary. Entity identity/physics exist before any
-- visual clone. Population, combat readiness and death remain domain-owned.
local CollectionService = game:GetService("CollectionService")
local Shell = require(script.Parent:WaitForChild("MnpcNavigationShell"))
local Geometry = require(script.Parent:WaitForChild("MnpcRigGeometry"))
local VisualRig = require(script.Parent:WaitForChild("MnpcVisualRig"))
local Lifecycle = {}

function Lifecycle.Create(name: string, surface: Vector3, yaw: number, kind: "Monster" | "NPC", authoring: boolean?): (Model, BasePart, Humanoid)
    local entity = Instance.new("Model")
    entity.Name = name
    entity:SetAttribute("Game1MnpcKind", kind)
    entity:SetAttribute("Game1MnpcRigReady", false)
    entity:SetAttribute("Damageable", false)
    local root, humanoid = Shell.Create(entity, surface, yaw, kind, authoring)
    return entity, root, humanoid
end

function Lifecycle.CopyTemplateMetadata(entity: Model, template: Model)
    -- Preserve published wrapper metadata without cloning any geometry.
    for key, value in pairs(template:GetAttributes()) do
        if key ~= "Game1MnpcKind" and key ~= "Game1MnpcRigReady" then
            entity:SetAttribute(key, value)
        end
    end
    for _, tag in ipairs(CollectionService:GetTags(template)) do
        CollectionService:AddTag(entity, tag)
    end
    entity.ModelStreamingMode = template.ModelStreamingMode
end

function Lifecycle.MarkRigReady(entity: Model)
    local collider = entity:FindFirstChild("RootCollider")
    local visual = entity:FindFirstChild("ImportedRig")
    assert(entity.Parent and collider and collider:IsA("BasePart") and visual and visual:IsA("Model"), "MNPC rig is incomplete")
    entity:SetAttribute("Game1MnpcRigReady", true)
end

-- The shell can be published/moved with no ImportedRig or Animator. The plan
-- is explicit and belongs to this root; no reference to a cloned visual.
function Lifecycle.PrepareShell(model: Model, navigationRoot: BasePart, template: Model, surface: Vector3, yaw: number, kind: "Monster" | "NPC")
    assert(navigationRoot.Parent == model and model.PrimaryPart == navigationRoot, "MNPC shell required")
    assert(model:GetAttribute("Game1MnpcKind") == kind, "MNPC rig kind mismatch")
    assert(model:FindFirstChild("RootCollider") == nil and model:FindFirstChild("ImportedRig") == nil, "MNPC shell already prepared")
    assert(model:GetAttribute("Damageable") ~= true, "MNPC shell cannot be damageable without pose")
    local plan = Geometry.Plan(template, navigationRoot.CFrame, surface, yaw, kind)
    if not plan then return nil end
    local collider = Shell.CreateQueryCollider(model, navigationRoot, navigationRoot.CFrame * plan.colliderOffset, plan.colliderSize)
    return table.freeze({geometry = plan, root = navigationRoot, collider = collider})
end
Lifecycle.AttachRig = VisualRig.Attach
Lifecycle.Publish = Shell.Publish
return table.freeze(Lifecycle)
