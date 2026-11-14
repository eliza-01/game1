-- M350: reconstruct Collision Blueprint from the published visual MeshPart frame.
-- Model.WorldPivot / PrimaryPart / PivotOffset are authoring metadata, not the
-- coordinate system used for collision placement. Existing MeshParts may have
-- individually edited X/Y/Z Size (Model:GetScale() can still be 1).
-- Pure geometry + anchor resolution; this module never mutates an Instance.
local Transform = {}

local function scaleVector(vector: Vector3, ratios: Vector3): Vector3
    return Vector3.new(vector.X * ratios.X, vector.Y * ratios.Y, vector.Z * ratios.Z)
end

local function finiteRatio(value: number): boolean
    return value == value and value >= 0.001 and value <= 1000
end

function Transform.Resolve(root: Model, blueprint: any): any
    local anchor = if type(blueprint) == "table" then blueprint.anchor else nil
    if type(anchor) ~= "table" or type(anchor.meshId) ~= "string"
        or type(anchor.localCFrame) ~= "table" or #anchor.localCFrame ~= 12
        or type(anchor.size) ~= "table" or #anchor.size ~= 3 then
        error("Outdated Collision Blueprint (no visual anchor). Re-Capture collision before Sync/Place")
    end
    local matched: MeshPart? = nil
    for _, candidate in ipairs(root:GetDescendants()) do
        if candidate:IsA("MeshPart")
            and tostring(candidate.MeshId):match("(%d+)$") == anchor.meshId then
            if matched then error("Ambiguous collision visual Mesh anchor; re-Capture") end
            matched = candidate
        end
    end
    if not matched then
        error("Collision visual Mesh anchor missing from placed asset; re-Capture on current publication")
    end
    local original = Vector3.new(table.unpack(anchor.size))
    if original.X <= 0 or original.Y <= 0 or original.Z <= 0 then
        error("Invalid Collision Blueprint visual anchor Size")
    end
    local ratios = Vector3.new(matched.Size.X / original.X,
        matched.Size.Y / original.Y, matched.Size.Z / original.Z)
    if not finiteRatio(ratios.X) or not finiteRatio(ratios.Y) or not finiteRatio(ratios.Z) then
        error("Unsupported Collision visual MeshPart Size; Place unchanged")
    end
    local average = (ratios.X + ratios.Y + ratios.Z) / 3
    local uniform = (ratios - Vector3.new(average, average, average)).Magnitude
        <= math.max(0.002, average * 0.003)
    return {mesh = matched, anchorFrame = CFrame.new(table.unpack(anchor.localCFrame)),
        ratios = ratios, uniform = uniform, uniformScale = average}
end

-- The visual MeshPart is an affine X/Y/Z-scaled reference. A rigid Roblox Part
-- cannot express shear. For Blocks we use the exact transformed centre and a
-- tight enclosing oriented box (the captured local axes), measuring any added
-- thickness. Reject geometries that need an excessively inflated enclosure.
-- This prevents a plausible-looking but badly oversized collision on meshes
-- whose colliders were not authored approximately aligned to their Mesh axes.
function Transform.Part(anchor: any, recipe: any): (CFrame, Vector3)
    local source = CFrame.new(table.unpack(recipe.localCFrame))
    local relative = anchor.anchorFrame:ToObjectSpace(source)
    local baseSize = Vector3.new(table.unpack(recipe.size))
    if anchor.uniform then
        local scale = anchor.uniformScale
        return anchor.mesh.CFrame * CFrame.new(relative.Position * scale) * relative.Rotation,
            baseSize * scale
    end
    if recipe.shape ~= "Block" then
        error("Non-uniform visual MeshPart Size requires Block collision Parts; Place unchanged")
    end

    local ratios = anchor.ratios
    local offset = scaleVector(relative.Position, ratios)
    local right, up, back = relative.RightVector, relative.UpVector, -relative.LookVector
    local scaledRight = scaleVector(right, ratios)
    local scaledUp = scaleVector(up, ratios)
    local scaledBack = scaleVector(back, ratios)

    -- Project the affine-transformed box onto its ORIGINAL orthonormal axes.
    -- The resulting rigid Part completely contains the source volume.
    local size = Vector3.new(
        math.abs(right:Dot(scaledRight)) * baseSize.X
            + math.abs(right:Dot(scaledUp)) * baseSize.Y
            + math.abs(right:Dot(scaledBack)) * baseSize.Z,
        math.abs(up:Dot(scaledRight)) * baseSize.X
            + math.abs(up:Dot(scaledUp)) * baseSize.Y
            + math.abs(up:Dot(scaledBack)) * baseSize.Z,
        math.abs(back:Dot(scaledRight)) * baseSize.X
            + math.abs(back:Dot(scaledUp)) * baseSize.Y
            + math.abs(back:Dot(scaledBack)) * baseSize.Z
    )
    local axisLengths = Vector3.new(scaledRight.Magnitude * baseSize.X,
        scaledUp.Magnitude * baseSize.Y, scaledBack.Magnitude * baseSize.Z)
    local excess = size - axisLengths
    -- At most 0.20 studs added to any full dimension, or at most 10% of that
    -- dimension. Reject only when BOTH limits are exceeded. Any larger shear
    -- needs a more suitable authoring primitive, not an implicit approximation.
    if (excess.X > 0.20 and excess.X > axisLengths.X * 0.10)
        or (excess.Y > 0.20 and excess.Y > axisLengths.Y * 0.10)
        or (excess.Z > 0.20 and excess.Z > axisLengths.Z * 0.10) then
        error("Non-uniform collision shape needs excessive shear enclosure; author aligned Block Parts")
    end
    if size.X <= 0.001 or size.Y <= 0.001 or size.Z <= 0.001
        or size.X > 4096 or size.Y > 4096 or size.Z > 4096 then
        error("Non-uniform collision Part Size outside Roblox authoring bounds")
    end
    return anchor.mesh.CFrame * CFrame.new(offset) * relative.Rotation, size
end

return table.freeze(Transform)
