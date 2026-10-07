local WeaponAttackVolume = {}

local BOX_LOCAL_ATTRIBUTE = "WeaponAttackBoxLocalCFrame"
local BOX_SIZE_ATTRIBUTE = "WeaponAttackBoxSize"
local GRIP_BOX_LOCAL_ATTRIBUTE = "WeaponAttackGripBoxLocalPosition"

local function finiteNumber(value: number): boolean
    return value == value and value > -math.huge and value < math.huge
end

local function finiteVector(value: Vector3): boolean
    return finiteNumber(value.X) and finiteNumber(value.Y) and finiteNumber(value.Z)
end

local function axisForBox(boxCFrame: CFrame, boxSize: Vector3): (Vector3, string, number)
    if boxSize.X >= boxSize.Y and boxSize.X >= boxSize.Z then
        return boxCFrame.RightVector, "X", boxSize.X
    elseif boxSize.Y >= boxSize.X and boxSize.Y >= boxSize.Z then
        return boxCFrame.UpVector, "Y", boxSize.Y
    end
    return boxCFrame.LookVector, "Z", boxSize.Z
end

local function setAxisLength(size: Vector3, axisName: string, length: number): Vector3
    if axisName == "X" then
        return Vector3.new(length, size.Y, size.Z)
    elseif axisName == "Y" then
        return Vector3.new(size.X, length, size.Z)
    end
    return Vector3.new(size.X, size.Y, length)
end

local function outwardDirection(
    rootPosition: Vector3,
    boxCFrame: CFrame,
    axis: Vector3,
    axisLength: number,
    gripBoxLocalPosition: Vector3?
): Vector3
    local half = math.max(0, axisLength) * 0.5
    local positive = boxCFrame.Position + axis * half
    local negative = boxCFrame.Position - axis * half

    -- The runtime grip is normally authored on the handle. Prefer the opposite
    -- end of the longest weapon axis, so the continuation always leaves from
    -- the blade/head side and cannot flip just because an animation crosses the
    -- character root. Root distance is only a compatibility fallback.
    if typeof(gripBoxLocalPosition) == "Vector3" then
        local gripWorld = boxCFrame:PointToWorldSpace(gripBoxLocalPosition)
        local positiveDistance = (positive - gripWorld).Magnitude
        local negativeDistance = (negative - gripWorld).Magnitude
        if math.abs(positiveDistance - negativeDistance) > 1e-4 then
            return if negativeDistance > positiveDistance then -axis else axis
        end
    end

    if (negative - rootPosition).Magnitude > (positive - rootPosition).Magnitude then
        return -axis
    end
    return axis
end

local function distanceToSphereExit(rootPosition: Vector3, startPosition: Vector3, direction: Vector3, radius: number): number
    local offset = startPosition - rootPosition
    local c = offset:Dot(offset) - radius * radius
    if c >= 0 then
        return 0
    end
    local b = offset:Dot(direction)
    local discriminant = b * b - c
    if discriminant <= 0 then
        return 0
    end
    return math.max(0, -b + math.sqrt(discriminant))
end

function WeaponAttackVolume.StampWeaponBox(weapon: Model): (CFrame, Vector3)
    local boxCFrame, boxSize = weapon:GetBoundingBox()
    local localCFrame = weapon:GetPivot():ToObjectSpace(boxCFrame)
    weapon:SetAttribute(BOX_LOCAL_ATTRIBUTE, localCFrame)
    weapon:SetAttribute(BOX_SIZE_ATTRIBUTE, boxSize)

    local grip = weapon:FindFirstChild("Game1WeaponGrip", true)
    if grip and grip:IsA("Attachment") then
        weapon:SetAttribute(GRIP_BOX_LOCAL_ATTRIBUTE, boxCFrame:PointToObjectSpace(grip.WorldPosition))
    else
        weapon:SetAttribute(GRIP_BOX_LOCAL_ATTRIBUTE, nil)
    end
    return localCFrame, boxSize
end

function WeaponAttackVolume.ReadWeaponBox(weapon: Model): (CFrame?, Vector3?)
    local localCFrame = weapon:GetAttribute(BOX_LOCAL_ATTRIBUTE)
    local boxSize = weapon:GetAttribute(BOX_SIZE_ATTRIBUTE)
    if typeof(localCFrame) ~= "CFrame" or typeof(boxSize) ~= "Vector3" or not finiteVector(boxSize) then
        return nil, nil
    end
    if boxSize.X <= 0 or boxSize.Y <= 0 or boxSize.Z <= 0 then
        return nil, nil
    end
    return weapon:GetPivot() * localCFrame, boxSize
end

function WeaponAttackVolume.ReadEquippedWeaponBox(character: Model): (CFrame?, Vector3?, Model?)
    local weapon = character:FindFirstChild("EquippedWeapon")
    if not weapon or not weapon:IsA("Model") then
        return nil, nil, nil
    end
    local boxCFrame, boxSize = WeaponAttackVolume.ReadWeaponBox(weapon)
    return boxCFrame, boxSize, weapon
end

function WeaponAttackVolume.ReadGripBoxLocalPosition(weapon: Model): Vector3?
    local value = weapon:GetAttribute(GRIP_BOX_LOCAL_ATTRIBUTE)
    return if typeof(value) == "Vector3" then value else nil
end

function WeaponAttackVolume.Build(
    rootPosition: Vector3,
    weaponBoxCFrame: CFrame,
    weaponBoxSize: Vector3,
    attackRadius: number,
    gripBoxLocalPosition: Vector3?
): any?
    if typeof(rootPosition) ~= "Vector3"
        or typeof(weaponBoxCFrame) ~= "CFrame"
        or typeof(weaponBoxSize) ~= "Vector3"
        or not finiteVector(rootPosition)
        or not finiteVector(weaponBoxCFrame.Position)
        or not finiteVector(weaponBoxSize)
    then
        return nil
    end

    local radius = math.max(0, tonumber(attackRadius) or 0)
    if radius <= 0 or weaponBoxSize.X <= 0 or weaponBoxSize.Y <= 0 or weaponBoxSize.Z <= 0 then
        return nil
    end

    local axis, axisName, axisLength = axisForBox(weaponBoxCFrame, weaponBoxSize)
    local direction = outwardDirection(rootPosition, weaponBoxCFrame, axis, axisLength, gripBoxLocalPosition)
    local weaponTip = weaponBoxCFrame.Position + direction * (axisLength * 0.5)
    local extension = distanceToSphereExit(rootPosition, weaponTip, direction, radius)

    -- The gameplay volume is one OBB: the physical EquippedWeapon box plus a
    -- continuation along its longest axis. Because the box orientation comes
    -- from the animated weapon itself, a different attack pose creates a
    -- different hit volume without any aim-sector approximation.
    local volumeCFrame = weaponBoxCFrame + direction * (extension * 0.5)
    local volumeSize = setAxisLength(weaponBoxSize, axisName, axisLength + extension)

    return {
        cframe = volumeCFrame,
        size = volumeSize,
        direction = direction,
        extension = extension,
        weaponTip = weaponTip,
        radius = radius,
        axis = axisName,
    }
end

return table.freeze(WeaponAttackVolume)
