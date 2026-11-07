-- Location-only geometry placement policy, shared by row Sync and Place Registry.
-- The transaction itself belongs to StudioManagedRigSwap (also used by Estate).
-- Preserve manual per-part Size/CFrame on simple, unrigged published revisions;
-- fail closed for changed multipart/skinned geometry instead of losing edits.
local History = require(script.Parent.StudioPublishedMeshHistory)
local Physics = require(script.Parent.StudioMeshPhysicsCore)
local Geometry = {}

local function visuals(model: Model): {MeshPart}
    local result = {}
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("MeshPart") and not Physics.IsCollider(descendant.Name)
            and descendant:GetAttribute("Game1DecoPhysicsOnly") ~= true then
            table.insert(result, descendant)
        end
    end
    return result
end

local function simple(model: Model): boolean
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("Bone") or descendant:IsA("JointInstance")
            or descendant:IsA("Constraint") or descendant:IsA("WrapLayer")
            or descendant:IsA("WrapTarget") or descendant:IsA("Attachment") then
            return false
        end
    end
    return true
end

local function validRatio(value: number): boolean
    return value == value and value >= 0.001 and value <= 1000
end

local function sameSize(a: Vector3, b: Vector3): boolean
    return (a - b).Magnitude < 0.025
end

local function uniformRatio(target: Vector3, source: Vector3): number?
    local ratio = Vector3.new(target.X / source.X, target.Y / source.Y, target.Z / source.Z)
    if not validRatio(ratio.X) or not validRatio(ratio.Y) or not validRatio(ratio.Z) then
        return nil
    end
    local average = (ratio.X + ratio.Y + ratio.Z) / 3
    local tolerance = math.max(0.001, average * 0.002)
    if math.abs(ratio.X - average) > tolerance
        or math.abs(ratio.Y - average) > tolerance
        or math.abs(ratio.Z - average) > tolerance then
        return nil
    end
    return average
end

local function alignSingleVisualRig(stage: Model, placed: Model,
    oldVisual: MeshPart, source: MeshPart, target: MeshPart): BasePart?
    -- A legacy one-visual publication can gain Bones/sockets and a COL in its
    -- next immutable publication. Model:GetScale() remains 1 when the old
    -- MeshPart was uniformly resized by hand. Transfer only a proven uniform
    -- scale through ScaleTo so Bones, Attachments and the new COL stay aligned.
    local oldScale = uniformRatio(target.Size, oldVisual.Size)
    local newScale = uniformRatio(target.Size, source.Size)
    if oldScale == nil or newScale == nil then return nil end
    local scaleAgreement = math.max(0.001, oldScale * 0.002)
    if math.abs(oldScale - newScale) > scaleAgreement then return nil end
    stage:ScaleTo(stage:GetScale() * newScale)
    local transform = target.CFrame * source.CFrame:Inverse()
    stage:PivotTo(transform * stage:GetPivot())
    source.PivotOffset = target.PivotOffset
    for _, part in ipairs(stage:GetDescendants()) do
        if part:IsA("BasePart") then part.Anchored = target.Anchored end
    end
    if not sameSize(source.Size, target.Size) or source.CFrame ~= target.CFrame
        or source:GetPivot() ~= target:GetPivot() then
        error("не удалось сохранить uniform Scale/CFrame/PivotOffset rig; Place не изменён")
    end
    if placed.PrimaryPart == target then stage.PrimaryPart = source end
    return source
end

local function verifyMultipart(previous: Model, placed: Model)
    -- In a nontrivial rig, ScaleTo only tracks Model scale, not manual Size
    -- modifications. Refuse the update if any part's real size differs.
    local expected, actual = {}, {}
    for _, group in ipairs({{previous, expected}, {placed, actual}}) do
        for _, part in ipairs(group[1]:GetDescendants()) do
            if part:IsA("MeshPart") then
                local mid = History.Id(part.MeshId)
                group[2][mid] = group[2][mid] or {}
                table.insert(group[2][mid], part.Size)
            end
        end
    end
    local function sortSizes(list: {Vector3})
        table.sort(list, function(a, b)
            if a.X ~= b.X then return a.X < b.X end
            if a.Y ~= b.Y then return a.Y < b.Y end
            return a.Z < b.Z
        end)
    end
    for meshId, sizes in pairs(expected) do
        local placedSizes = actual[meshId]
        if not placedSizes or #placedSizes ~= #sizes then
            error("разный состав исторического rig; Place не изменён")
        end
        sortSizes(sizes)
        sortSizes(placedSizes)
        for index, size in ipairs(sizes) do
            if not sameSize(size, placedSizes[index]) then
                error("ручной Size в многомешевом/скелетном rig: требуется отдельная миграция; Place не изменён")
            end
        end
    end
end

-- Called only after published Mesh IDs and the whole outgoing child hierarchy
-- have been verified against the immutable prior publication.
-- Returns the validated primary anchor of the incoming stage.
function Geometry.Align(stage: Model, previous: Model, placed: Model): BasePart?
    local oldVisuals, newVisuals, placedVisuals = visuals(previous), visuals(stage), visuals(placed)
    if #oldVisuals == 1 and #newVisuals == 1 and #placedVisuals == 1 then
        local aligned = alignSingleVisualRig(stage, placed,
            oldVisuals[1], newVisuals[1], placedVisuals[1])
        if aligned then return aligned end
    end
    if #oldVisuals == 1 and #newVisuals == 1 and #placedVisuals == 1
        and simple(previous) and simple(stage) and simple(placed) then
        local source = newVisuals[1]
        local target = placedVisuals[1]
        local ratio = Vector3.new(target.Size.X / source.Size.X,
            target.Size.Y / source.Size.Y, target.Size.Z / source.Size.Z)
        if not validRatio(ratio.X) or not validRatio(ratio.Y) or not validRatio(ratio.Z) then
            error("неподдерживаемый Size размещённого MeshPart; Place не изменён")
        end
        local sourceFrame = source.CFrame
        local proposed = {}
        for _, part in ipairs(stage:GetDescendants()) do
            if part:IsA("BasePart") then
                local relative = sourceFrame:ToObjectSpace(part.CFrame)
                local offset = relative.Position
                proposed[part] = {
                    size = Vector3.new(part.Size.X * ratio.X, part.Size.Y * ratio.Y, part.Size.Z * ratio.Z),
                    frame = target.CFrame * CFrame.new(offset.X * ratio.X,
                        offset.Y * ratio.Y, offset.Z * ratio.Z) * relative.Rotation,
                }
            end
        end
        for part, value in pairs(proposed) do
            part.Size = value.size
            part.CFrame = value.frame
            part.Anchored = target.Anchored
        end
        -- Keep the precise authored mesh pivot as well as its visible CFrame:
        -- a published FBX may have a different PivotOffset than the old version.
        source.PivotOffset = target.PivotOffset
        if not sameSize(source.Size, target.Size) or source.CFrame ~= target.CFrame
            or source:GetPivot() ~= target:GetPivot() then
            error("не удалось сохранить CFrame/Size/PivotOffset; Place не изменён")
        end
        if placed.PrimaryPart == target then stage.PrimaryPart = source end
        return source
    end

    -- Historical complete rigs may have Bones, joints or multiple parts.
    -- Only Model scale and immutable authored geometry are transferable.
    previous:ScaleTo(placed:GetScale())
    verifyMultipart(previous, placed)
    stage:ScaleTo(placed:GetScale())
    local transform = History.Provenance(placed, previous)
    stage:PivotTo(transform * stage:GetPivot())
    return stage.PrimaryPart
end

return table.freeze(Geometry)
