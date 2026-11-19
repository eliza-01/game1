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
    -- House v3 has an authored rig_carrier pivot, not an unstable visual Mesh ID.
    -- The same Part reconstruction handles both schemas without a second system.
    if type(blueprint) == "table" and blueprint.schemaVersion == 3 then
        if blueprint.pivot ~= "Model:GetPivot()" then error("Invalid House collision pivot") end
        local scale = root:GetScale()
        if scale <= 0 or scale ~= scale or scale > 1000 then error("Invalid house scale") end
        return {mesh = {CFrame = root:GetPivot()}, anchorFrame = CFrame.new(),
            ratios = Vector3.new(scale, scale, scale), uniform = true, uniformScale = scale}
    end
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

-- A captured primitive is transformed by the visual MeshPart's *per-axis*
-- Size changes, independently of the Model's uniform ScaleTo. This affine
-- transform may shear a primitive whose local axes do not align with the mesh.
-- In Instance Manager, an explicit 3-D inspection may approve a visibly
-- approximate collision. Ordinary Place/Sync remain strict and never silently
-- replace wedges with Blocks or accept approximate primitive geometry.
local function inBounds(size: Vector3): boolean
    return size.X > 0.001 and size.Y > 0.001 and size.Z > 0.001
        and size.X <= 4096 and size.Y <= 4096 and size.Z <= 4096
end

local function perpendicular(a: Vector3, b: Vector3): boolean
    return math.abs(a:Dot(b)) <= a.Magnitude * b.Magnitude * 0.0001
end

function Transform.Part(anchor: any, recipe: any, allowExcessive: boolean?): (CFrame, Vector3, any?)
    local source = CFrame.new(table.unpack(recipe.localCFrame))
    local relative = anchor.anchorFrame:ToObjectSpace(source)
    local baseSize = Vector3.new(table.unpack(recipe.size))
    if anchor.uniform then
        local scale = anchor.uniformScale
        return anchor.mesh.CFrame * CFrame.new(relative.Position * scale) * relative.Rotation,
            baseSize * scale
    end

    local ratios = anchor.ratios
    local offset = scaleVector(relative.Position, ratios)
    local right, up, back = relative.RightVector, relative.UpVector, -relative.LookVector
    local scaledRight = scaleVector(right, ratios)
    local scaledUp = scaleVector(up, ratios)
    local scaledBack = scaleVector(back, ratios)
    local axisLengths = Vector3.new(scaledRight.Magnitude * baseSize.X,
        scaledUp.Magnitude * baseSize.Y, scaledBack.Magnitude * baseSize.Z)

    -- A non-uniform scale is EXACT for a Wedge/CornerWedge if its three
    -- transformed basis vectors remain orthogonal (including 90-degree
    -- rotations). A Cylinder is also exact if its Y/Z radial scales match.
    local orthogonal = perpendicular(scaledRight, scaledUp)
        and perpendicular(scaledRight, scaledBack)
        and perpendicular(scaledUp, scaledBack)
    local wedge = recipe.shape == "Wedge" or recipe.shape == "CornerWedge"
    local cylinder = recipe.shape == "Cylinder"
    local matchingRadii = math.abs(scaledUp.Magnitude - scaledBack.Magnitude)
        <= math.max(0.0001, scaledUp.Magnitude * 0.0001)
    if orthogonal and (wedge or (cylinder and matchingRadii)) then
        if not inBounds(axisLengths) then
            error("Non-uniform collision Part Size outside Roblox authoring bounds")
        end
        local centre = anchor.mesh.CFrame:PointToWorldSpace(offset)
        local frame = CFrame.fromMatrix(centre, scaledRight.Unit, scaledUp.Unit, scaledBack.Unit)
        return frame, axisLengths
    end

    -- The transformed primitive may be sheared. Project its full bounding
    -- box onto the original orthonormal axes to produce a deterministic
    -- candidate. For Blocks this is a conservative enclosing OBB. For Wedge,
    -- CornerWedge, Ball and Cylinder, keeping the SAME primitive type with
    -- these dimensions is an APPROXIMATION, not an assured enclosure: the
    -- sloped/curved surface can differ. Never allow it without an explicit
    -- Instance Manager visual inspection and approval.
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
    if not inBounds(size) then
        error("Non-uniform collision Part Size outside Roblox authoring bounds")
    end
    local excess = size - axisLengths
    -- A Block enclosure exceeding BOTH .20 studs AND 10% on an axis is
    -- not silently permitted. Other primitives always require approval if
    -- their affine transform cannot be represented exactly.
    local excessive = (excess.X > 0.20 and excess.X > axisLengths.X * 0.10)
        or (excess.Y > 0.20 and excess.Y > axisLengths.Y * 0.10)
        or (excess.Z > 0.20 and excess.Z > axisLengths.Z * 0.10)
    local approximate = recipe.shape ~= "Block"
    if approximate and allowExcessive ~= true then
        error("Non-uniform " .. tostring(recipe.shape)
            .. " collision requires visual approximation review in Instance Manager")
    end
    if excessive and allowExcessive ~= true then
        error("Non-uniform collision shape needs excessive shear enclosure; preview and approve in Instance Manager")
    end
    local warning = if excessive or approximate then {
        partId = recipe.id,
        shape = recipe.shape,
        approximate = approximate,
        reason = if approximate then "Approximate " .. tostring(recipe.shape)
            .. ": slope/curvature may differ from the affinely transformed original"
            else "Block enclosure enlarged by non-uniform shear",
        excessStuds = {math.max(0, excess.X), math.max(0, excess.Y), math.max(0, excess.Z)},
        addedPercent = {
            math.max(0, excess.X) / math.max(axisLengths.X, 0.001) * 100,
            math.max(0, excess.Y) / math.max(axisLengths.Y, 0.001) * 100,
            math.max(0, excess.Z) / math.max(axisLengths.Z, 0.001) * 100,
        },
    } else nil
    return anchor.mesh.CFrame * CFrame.new(offset) * relative.Rotation, size, warning
end

return table.freeze(Transform)
