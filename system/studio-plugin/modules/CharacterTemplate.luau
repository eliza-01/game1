local CharacterTemplate = {}

local WORLD_UP = Vector3.yAxis
local ALIGN_EPSILON = 1e-4
local UPRIGHT_DOT = 0.999

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

local function normalizedBoneName(name: string): string
    local normalized = string.lower(name)
    normalized = normalized:gsub("[%s_%-]", ".")
    return normalized
end

local function spineRank(name: string): number?
    local normalized = normalizedBoneName(name)
    if normalized == "spine" then
        return 0
    end
    local suffix = normalized:match("^spine%.?(%d+)$")
    if suffix then
        return tonumber(suffix)
    end
    return nil
end

local function isFootBone(name: string): boolean
    local normalized = normalizedBoneName(name)
    return normalized == "foot.l"
        or normalized == "foot.r"
        or normalized == "leftfoot"
        or normalized == "rightfoot"
        or normalized == "l.foot"
        or normalized == "r.foot"
end

local function exactBone(bones: { Bone }, wanted: { string }): Bone?
    for _, target in wanted do
        local normalizedTarget = normalizedBoneName(target)
        for _, bone in bones do
            if normalizedBoneName(bone.Name) == normalizedTarget then
                return bone
            end
        end
    end
    return nil
end

local function skeletonBones(importedRig: Model): { Bone }
    local result = {}
    for _, descendant in importedRig:GetDescendants() do
        if descendant:IsA("Bone") then
            table.insert(result, descendant)
        end
    end
    return result
end

local function averagePosition(bones: { Bone }): Vector3?
    if #bones == 0 then
        return nil
    end
    local sum = Vector3.zero
    for _, bone in bones do
        sum += bone.WorldCFrame.Position
    end
    return sum / #bones
end

local function resolveSkeletonUp(importedRig: Model): (Vector3, string)
    local bones = skeletonBones(importedRig)
    if #bones == 0 then
        error("character rig has no Bone instances for canonical orientation")
    end

    local feet = {}
    for _, bone in bones do
        if isFootBone(bone.Name) then
            table.insert(feet, bone)
        end
    end
    local lower = averagePosition(feet)
    if not lower then
        error("character rig has no supported foot bones; expected foot.L/foot.R or left/right foot aliases")
    end

    local upper = exactBone(bones, { "head", "head.x", "neck", "neck.001" })
    local source = "head_to_feet"
    if not upper then
        local bestRank = -math.huge
        for _, bone in bones do
            local rank = spineRank(bone.Name)
            if rank ~= nil and rank > bestRank then
                bestRank = rank
                upper = bone
            end
        end
        source = "spine_to_feet"
    end
    if not upper then
        error("character rig has no supported head/neck/spine bone for canonical orientation")
    end

    local direction = upper.WorldCFrame.Position - lower
    if direction.Magnitude <= ALIGN_EPSILON then
        error("character skeleton up-axis is degenerate")
    end
    return direction.Unit, source
end

local function rotationBetween(from: Vector3, to: Vector3): CFrame
    local a = from.Unit
    local b = to.Unit
    local dot = math.clamp(a:Dot(b), -1, 1)
    if dot >= UPRIGHT_DOT then
        return CFrame.identity
    end

    if dot <= -UPRIGHT_DOT then
        local axis = a:Cross(Vector3.xAxis)
        if axis.Magnitude <= ALIGN_EPSILON then
            axis = a:Cross(Vector3.zAxis)
        end
        return CFrame.fromAxisAngle(axis.Unit, math.pi)
    end

    local axis = a:Cross(b)
    if axis.Magnitude <= ALIGN_EPSILON then
        return CFrame.identity
    end
    return CFrame.fromAxisAngle(axis.Unit, math.acos(dot))
end

local function normalizeSkeletonOrientation(importedRig: Model): any
    local upBefore, source = resolveSkeletonUp(importedRig)
    local dotBefore = math.clamp(upBefore:Dot(WORLD_UP), -1, 1)
    local correction = rotationBetween(upBefore, WORLD_UP)
    local angleDegrees = math.deg(math.acos(dotBefore))

    if dotBefore < UPRIGHT_DOT then
        local pivot = importedRig:GetPivot()
        importedRig:PivotTo(CFrame.new(pivot.Position) * correction * pivot.Rotation)
    end

    local upAfter = select(1, resolveSkeletonUp(importedRig))
    local dotAfter = math.clamp(upAfter:Dot(WORLD_UP), -1, 1)
    if dotAfter < 0.995 then
        error(("character skeleton orientation normalization failed (up dot %.5f)"):format(dotAfter))
    end

    importedRig:SetAttribute("Game1TemplateOrientationSource", source)
    importedRig:SetAttribute("Game1TemplateOrientationDegrees", angleDegrees)
    importedRig:SetAttribute("Game1TemplateOrientationNormalized", dotBefore < UPRIGHT_DOT)

    return {
        source = source,
        normalized = dotBefore < UPRIGHT_DOT,
        correctionDegrees = angleDegrees,
        upDotBefore = dotBefore,
        upDotAfter = dotAfter,
    }
end

function CharacterTemplate.EnsureCanonicalRoot(wrapper: Model, importedRig: Model): (BasePart, any)
    local existing = importedRig:FindFirstChild("RootPart", true)
    if existing and existing:IsA("BasePart") then
        wrapper.PrimaryPart = existing
        importedRig.PrimaryPart = existing
        wrapper:SetAttribute("Game1CharacterRootSource", "asset")
        wrapper:SetAttribute("Game1CharacterTemplateSchema", 1)
        return existing, {
            source = "authored_root",
            normalized = false,
            correctionDegrees = 0,
            upDotBefore = 1,
            upDotAfter = 1,
        }
    end

    -- Reference character runtime expects ImportedRig/RootPart to be authored before
    -- Play. game1 accepts generic armatures, so the Studio sync boundary converts the
    -- loaded skeleton into that contract exactly once. Runtime never guesses pitch/roll.
    local orientation = normalizeSkeletonOrientation(importedRig)
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
    wrapper:SetAttribute("Game1CharacterTemplateSchema", 1)
    wrapper:SetAttribute("Game1CharacterOrientationSource", orientation.source)
    wrapper:SetAttribute("Game1CharacterOrientationDegrees", orientation.correctionDegrees)
    return root, orientation
end

return CharacterTemplate
