local WeaponAttackVolume = {}

local BOX_LOCAL_ATTRIBUTE = "WeaponAttackBoxLocalCFrame"
local BOX_SIZE_ATTRIBUTE = "WeaponAttackBoxSize"
local BONE_BOX_LOCAL_ATTRIBUTE = "WeaponAttackBoneBoxLocalPosition"

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

local function axisCoordinate(value: Vector3, axisName: string): number
    if axisName == "X" then
        return value.X
    elseif axisName == "Y" then
        return value.Y
    end
    return value.Z
end

local function setAxisLength(size: Vector3, axisName: string, length: number): Vector3
    if axisName == "X" then
        return Vector3.new(length, size.Y, size.Z)
    elseif axisName == "Y" then
        return Vector3.new(size.X, length, size.Z)
    end
    return Vector3.new(size.X, size.Y, length)
end

local function bladeGeometry(
    weaponBoxCFrame: CFrame,
    weaponBoxSize: Vector3,
    weaponBoneBoxLocalPosition: Vector3
)
    local axis, axisName, axisLength = axisForBox(weaponBoxCFrame, weaponBoxSize)
    local halfLength = axisLength * 0.5
    local boneAxis = math.clamp(axisCoordinate(weaponBoneBoxLocalPosition, axisName), -halfLength, halfLength)
    local positiveLength = halfLength - boneAxis
    local negativeLength = boneAxis + halfLength
    local directionSign = if positiveLength >= negativeLength then 1 else -1
    local bladeLength = if directionSign > 0 then positiveLength else negativeLength
    if bladeLength <= 1e-4 then
        return nil
    end

    local bladeCenterAxis = (boneAxis + directionSign * halfLength) * 0.5
    local direction = axis * directionSign
    local bladeCenter = weaponBoxCFrame.Position + axis * bladeCenterAxis
    local weaponTip = weaponBoxCFrame.Position + axis * (directionSign * halfLength)
    return direction, axisName, bladeLength, bladeCenter, weaponTip
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

    -- Game1WeaponGrip is aligned exactly to the character weapon socket bone when
    -- the weapon is equipped. Persist that point in attack-box space so every
    -- animated pose can reconstruct the weapon-bone plane without counting the
    -- handle behind it as an attacking surface.
    local grip = weapon:FindFirstChild("Game1WeaponGrip", true)
    if grip and grip:IsA("Attachment") then
        weapon:SetAttribute(BONE_BOX_LOCAL_ATTRIBUTE, boxCFrame:PointToObjectSpace(grip.WorldPosition))
    else
        weapon:SetAttribute(BONE_BOX_LOCAL_ATTRIBUTE, nil)
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

function WeaponAttackVolume.ReadWeaponBoneBoxLocalPosition(weapon: Model): Vector3?
    local value = weapon:GetAttribute(BONE_BOX_LOCAL_ATTRIBUTE)
    return if typeof(value) == "Vector3" and finiteVector(value) then value else nil
end

function WeaponAttackVolume.Build(
    rootPosition: Vector3,
    weaponBoxCFrame: CFrame,
    weaponBoxSize: Vector3,
    attackRadius: number,
    weaponBoneBoxLocalPosition: Vector3?
): any?
    if typeof(rootPosition) ~= "Vector3"
        or typeof(weaponBoxCFrame) ~= "CFrame"
        or typeof(weaponBoxSize) ~= "Vector3"
        or typeof(weaponBoneBoxLocalPosition) ~= "Vector3"
        or not finiteVector(rootPosition)
        or not finiteVector(weaponBoxCFrame.Position)
        or not finiteVector(weaponBoxSize)
        or not finiteVector(weaponBoneBoxLocalPosition)
    then
        return nil
    end

    local radius = math.max(0, tonumber(attackRadius) or 0)
    if radius <= 0 or weaponBoxSize.X <= 0 or weaponBoxSize.Y <= 0 or weaponBoxSize.Z <= 0 then
        return nil
    end

    local direction, axisName, bladeLength, bladeCenter, weaponTip = bladeGeometry(
        weaponBoxCFrame,
        weaponBoxSize,
        weaponBoneBoxLocalPosition
    )
    if not direction then
        return nil
    end

    local extension = distanceToSphereExit(rootPosition, weaponTip, direction, radius)

    -- The physical source segment begins at the character weapon bone and ends
    -- at the blade tip. The handle side of the imported weapon box is excluded.
    -- The existing attack-radius continuation still starts at that blade tip, so
    -- the complete attacking OBB can never extend backwards through the handle.
    local volumeCFrame = CFrame.fromMatrix(bladeCenter, weaponBoxCFrame.XVector, weaponBoxCFrame.YVector, weaponBoxCFrame.ZVector)
        + direction * (extension * 0.5)
    local volumeSize = setAxisLength(weaponBoxSize, axisName, bladeLength + extension)

    return {
        cframe = volumeCFrame,
        size = volumeSize,
        direction = direction,
        extension = extension,
        bladeLength = bladeLength,
        weaponBonePosition = bladeCenter - direction * (bladeLength * 0.5),
        weaponTip = weaponTip,
        radius = radius,
        axis = axisName,
    }
end

return table.freeze(WeaponAttackVolume)
