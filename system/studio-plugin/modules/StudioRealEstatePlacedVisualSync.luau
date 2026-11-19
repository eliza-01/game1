-- Full Real Estate sync for a NEW publication of the same stable house type.
-- Old and new MeshPart names/counts can differ completely. The placed Model,
-- Plot identity, authored pivot, scale and unmanaged siblings are never replaced.
-- Shared StudioManagedRigSwap owns the managed-child transaction and rollback.
local Targets = require(script.Parent.StudioRealEstatePlacedTargets)
local RigSwap = require(script.Parent.StudioManagedRigSwap)
local VisualSync = {}

local MANAGED_RIG_ATTRIBUTE = "Game1RealEstateManagedRig"

local function isManagedVisual(child: Instance, allowPreviousNames: boolean): boolean
    if not child:IsA("Model") then return false end
    if child:GetAttribute(MANAGED_RIG_ATTRIBUTE) == true then return true end
    if not allowPreviousNames then return false end
    -- Previously published Estate templates used <part>Rig / DoorAssembly.
    -- Only accept an actual imported MeshPart rig, never an arbitrary Model
    -- which happens to contain the word 'Rig'. Root ownership is checked by
    -- the caller before using this compatibility classifier.
    local knownName = child.Name == "DoorAssembly"
        or child.Name:match("^[A-Z][%w_]*Rig$") ~= nil
    return knownName and child:FindFirstChildWhichIsA("MeshPart", true) ~= nil
end

local function managedChildren(root: Model, allowPreviousNames: boolean): {Model}
    local result = {}
    for _, child in root:GetChildren() do
        if isManagedVisual(child, allowPreviousNames) then
            table.insert(result, child :: Model)
        end
    end
    table.sort(result, function(a, b) return a.Name < b.Name end)
    return result
end

local function preferredPrimary(rigs: {Model}): BasePart?
    for _, rig in rigs do
        local carrier = rig:FindFirstChild("rig_carrier", true)
        if carrier and carrier:IsA("MeshPart") then return carrier end
    end
    local choices = {}
    for _, rig in rigs do
        for _, descendant in rig:GetDescendants() do
            if descendant:IsA("BasePart") then table.insert(choices, descendant) end
        end
    end
    table.sort(choices, function(a, b) return a:GetFullName() < b:GetFullName() end)
    return choices[1]
end

local function stageRig(source: Model, template: Model, placed: Model,
    previousDoor: Model?): Model
    local candidate = source:Clone()
    local templateScale = template:GetScale()
    local ratio = placed:GetScale() / templateScale
    if ratio <= 0 or ratio ~= ratio or ratio > 1000 then
        candidate:Destroy()
        error("invalid authored-to-placed house scale")
    end
    -- Model:ScaleTo does not inherit the parent Model's ScaleTo history.
    -- Match the current placed house scale before moving the cloned rig.
    if math.abs(ratio - 1) > 0.000001 then
        candidate:ScaleTo(source:GetScale() * ratio)
    end
    local localFrame = template:GetPivot():ToObjectSpace(source:GetPivot())
    local target = placed:GetPivot() * CFrame.new(localFrame.Position * ratio) * localFrame.Rotation
    if source.Name == "DoorAssembly" and previousDoor then
        -- Only preserve the open angle if the authored hinge is unchanged.
        -- An entirely different door should use the new authored closed pivot.
        local oldClosed = previousDoor:GetAttribute("Game1DoorClosedLocalPivot")
        local newClosed = source:GetAttribute("Game1DoorClosedLocalPivot")
        if typeof(oldClosed) == "string" and oldClosed == newClosed then
            target = previousDoor:GetPivot()
        end
    end
    candidate:PivotTo(target)
    candidate:SetAttribute(MANAGED_RIG_ATTRIBUTE, true)
    return candidate
end

function VisualSync.Update(template: Model, slug: string, placedTargets: {Model}?): (number, number, {string})
    local targets = placedTargets or Targets.List(slug)
    local sources = managedChildren(template, true)
    if #sources == 0 then
        return 0, #targets, {"Full visual sync skipped: template has no published visual rigs"}
    end
    local changed, found = 0, 0
    local warnings = {}
    for _, root in targets do
        found += 1
        if root.Name ~= slug or root:GetAttribute("Game1RealEstateSlug") ~= slug then
            table.insert(warnings, root:GetFullName() .. ": wrong managed house identity")
            continue
        end
        local oldRigs = managedChildren(root, true)
        if #oldRigs == 0 then
            -- Do not erase player-owned or unmarked geometry to make room.
            table.insert(warnings, root:GetFullName() .. ": no verified managed visual rigs; use Plot Place to rebuild an authored preview")
            continue
        end
        local oldDoor = root:FindFirstChild("DoorAssembly")
        if oldDoor and not oldDoor:IsA("Model") then oldDoor = nil end
        local newRigs = {}
        local prepared, planOrError = pcall(function()
            for _, source in sources do
                table.insert(newRigs, stageRig(source, template, root, oldDoor :: Model?))
            end
            -- The old primary MeshPart may not exist in a new publication.
            -- The shared swap can select a new published part while retaining
            -- the ORIGINAL placed root pivot through PivotOffset.
            return RigSwap.Prepare(root, oldRigs, newRigs,
                {preferredPrimary = preferredPrimary(newRigs)})
        end)
        if not prepared then
            for _, rig in newRigs do rig:Destroy() end
            table.insert(warnings, root:GetFullName() .. ": preflight rejected: " .. tostring(planOrError))
            continue
        end
        local plan = planOrError
        local committed, reason = pcall(function()
            RigSwap.Commit(plan)
        end)
        if not committed then
            -- RigSwap.Commit performs its own rollback on failure.
            table.insert(warnings, root:GetFullName() .. ": update rolled back: " .. tostring(reason))
            continue
        end
        RigSwap.Finalize(plan)
        Targets.MarkPlaced(root)
        -- Never mutate Plot coordinates, revision, anchor policy or the root.
        root:SetAttribute("Game1RigAssetIds", template:GetAttribute("Game1RigAssetIds"))
        root:SetAttribute("Game1HouseModelAssetId", template:GetAttribute("Game1HouseModelAssetId"))
        root:SetAttribute("Game1DoorModelAssetId", template:GetAttribute("Game1DoorModelAssetId"))
        root:SetAttribute("Game1ModelAssetId", template:GetAttribute("Game1ModelAssetId"))
        root:SetAttribute("Game1PrimaryRigPart", template:GetAttribute("Game1PrimaryRigPart"))
        changed += 1
    end
    return changed, found, warnings
end

return table.freeze(VisualSync)
