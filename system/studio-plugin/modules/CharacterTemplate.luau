local CharacterTemplate = {}

local function chooseRigAnchor(importedRig: Model): BasePart?
    local fallback: BasePart? = nil
    for _, descendant in importedRig:GetDescendants() do
        if descendant:IsA("BasePart") then
            fallback = fallback or descendant
            if descendant:IsA("MeshPart") and descendant:FindFirstChildWhichIsA("Bone", true) then
                return descendant
            end
        end
    end
    return fallback
end

local function clearLegacyOrientationMetadata(wrapper: Model, importedRig: Model)
    -- game1 used to infer a body "up" vector from head/spine/feet bones and
    -- rotate the imported rig to world Y. That is deliberately forbidden now:
    -- authored FBX/model basis is the animation basis and must stay untouched.
    for _, attributeName in {
        "Game1TemplateOrientationSource",
        "Game1TemplateOrientationDegrees",
        "Game1TemplateOrientationNormalized",
    } do
        importedRig:SetAttribute(attributeName, nil)
    end
    for _, attributeName in {
        "Game1CharacterOrientationSource",
        "Game1CharacterOrientationDegrees",
    } do
        wrapper:SetAttribute(attributeName, nil)
    end

    importedRig:SetAttribute("Game1TemplateBasisMode", "authored")
    wrapper:SetAttribute("Game1RigBasisMode", "authored")
end

local function authoredBasisInfo(): any
    return {
        source = "authored_basis",
        basisMode = "authored",
        normalized = false,
        correctionDegrees = 0,
    }
end

function CharacterTemplate.EnsureCanonicalRoot(wrapper: Model, importedRig: Model): (BasePart, any)
    clearLegacyOrientationMetadata(wrapper, importedRig)

    local existing = importedRig:FindFirstChild("RootPart", true)
    if existing and existing:IsA("BasePart") then
        wrapper.PrimaryPart = existing
        importedRig.PrimaryPart = existing
        wrapper:SetAttribute("Game1CharacterRootSource", "asset")
        wrapper:SetAttribute("Game1CharacterTemplateSchema", 2)
        return existing, authoredBasisInfo()
    end

    -- Build only the gameplay/root helper. Never infer pitch/roll from anatomy and
    -- never PivotTo the imported visual rig here. The FBX authored basis is shared
    -- by the rest skeleton and every animation clip, so changing it at sync time
    -- makes otherwise-correct animation tracks lean or rotate as a whole.
    local anchor = chooseRigAnchor(importedRig)
    if not anchor then
        error("character rig has no BasePart anchor")
    end

    local boxCFrame, boxSize = importedRig:GetBoundingBox()
    local root = Instance.new("Part")
    root.Name = "RootPart"
    root.Size = Vector3.new(0.35, 0.03, 0.35)
    root.CFrame = CFrame.new(
        boxCFrame.Position.X,
        boxCFrame.Position.Y - boxSize.Y * 0.5,
        boxCFrame.Position.Z
    )
    root.Transparency = 1
    root.CastShadow = false
    root.Anchored = false
    root.CanCollide = false
    root.CanTouch = false
    root.CanQuery = false
    root.Massless = true
    root:SetAttribute("Game1GeneratedCharacterRoot", true)
    root.Parent = importedRig

    local weld = Instance.new("WeldConstraint")
    weld.Name = "ImportedRigRootWeld"
    weld.Part0 = root
    weld.Part1 = anchor
    weld.Parent = root

    importedRig.PrimaryPart = root
    wrapper.PrimaryPart = root
    wrapper:SetAttribute("Game1CharacterRootSource", "generated")
    wrapper:SetAttribute("Game1CharacterTemplateSchema", 2)
    return root, authoredBasisInfo()
end

return CharacterTemplate
