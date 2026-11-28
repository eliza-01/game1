-- Shared MNPC construction boundary. Entity identity/physics exist before any
-- visual clone. Population, combat readiness and death remain domain-owned.
local CollectionService = game:GetService("CollectionService")
local Shell = require(script.Parent:WaitForChild("MnpcNavigationShell"))
local VisualRig = require(script.Parent:WaitForChild("MnpcVisualRig"))
local Lifecycle = {}

function Lifecycle.Create(name: string, surface: Vector3, yaw: number, kind: "Monster" | "NPC"): (Model, BasePart, Humanoid)
    local entity = Instance.new("Model")
    entity.Name = name
    entity:SetAttribute("Game1MnpcKind", kind)
    entity:SetAttribute("Game1MnpcRigReady", false)
    local root, humanoid = Shell.Create(entity, surface, yaw, kind)
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

Lifecycle.AttachRig = VisualRig.Attach
Lifecycle.Publish = Shell.Publish
return table.freeze(Lifecycle)
