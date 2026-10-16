-- Precomputed bone-local combat hitbox definitions. Attach-time only;
-- no workspace traversal, network events, or attack-time geometry reads.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local SkeletonHeadResolver = require(Shared:WaitForChild("combat"):WaitForChild("SkeletonHeadResolver"))

local HitboxDefinitionBuilder = {}
local definitionCache: { [string]: any } = {}
local MIN_BOX_AXIS = 0.05
local BODY_BOX_PADDING = 0.035
local HEAD_BOX_PADDING = 0.015
local BROAD_RADIUS_PADDING = 0.25

local function transformedBoneFrame(bone: Bone): CFrame
    return SkeletonHeadResolver.TransformedBoneFrame(bone)
end

local function scaleVector(value: Vector3, scale: Vector3): Vector3
    return Vector3.new(value.X * scale.X, value.Y * scale.Y, value.Z * scale.Z)
end

local function meshScale(meshPart: MeshPart): Vector3
    local ok, meshSize = pcall(function()
        return meshPart.MeshSize
    end)
    if not ok or typeof(meshSize) ~= "Vector3" then
        return Vector3.one
    end
    return Vector3.new(
        if math.abs(meshSize.X) > 1e-6 then meshPart.Size.X / meshSize.X else 1,
        if math.abs(meshSize.Y) > 1e-6 then meshPart.Size.Y / meshSize.Y else 1,
        if math.abs(meshSize.Z) > 1e-6 then meshPart.Size.Z / meshSize.Z else 1
    )
end

local function prepareRecord(record: any)
    local scale = record.scale
    local prepared = {}
    for _, source in pairs(record.geometry.vertices or {}) do
        local scaledPosition = scaleVector(source.position, scale)
        local influences = {}
        for _, influence in ipairs(source.influences or {}) do
            local bindCFrame = influence.bindCFrame
            local scaledBindFrame = CFrame.new(scaleVector(bindCFrame.Position, scale)) * bindCFrame.Rotation
            table.insert(influences, {
                boneName = influence.boneName,
                relative = scaledBindFrame:PointToObjectSpace(scaledPosition),
                weight = influence.weight,
            })
        end
        table.insert(prepared, {
            bindLocal = scaledPosition,
            influences = influences,
        })
    end
    record.preparedVertices = prepared
end

local function boneForInfluence(binding: any, record: any, boneName: string): Bone?
    return record.bonesByName[boneName] or binding.bonesByName[boneName]
end

local function vertexWorldPosition(binding: any, record: any, source: any): (Vector3?, string?)
    if #source.influences == 0 then
        return record.meshPart.CFrame:PointToWorldSpace(source.bindLocal), nil
    end

    local position = Vector3.zero
    for _, influence in ipairs(source.influences) do
        local bone = boneForInfluence(binding, record, influence.boneName)
        if not bone or not bone.Parent then
            return nil, ("mesh bone %s is missing from runtime rig"):format(tostring(influence.boneName))
        end
        position += transformedBoneFrame(bone):PointToWorldSpace(influence.relative) * influence.weight
    end
    return position, nil
end

local function newBounds(): any
    return {
        minimum = Vector3.new(math.huge, math.huge, math.huge),
        maximum = Vector3.new(-math.huge, -math.huge, -math.huge),
        count = 0,
    }
end

local function growBounds(bounds: any, point: Vector3)
    bounds.minimum = Vector3.new(
        math.min(bounds.minimum.X, point.X),
        math.min(bounds.minimum.Y, point.Y),
        math.min(bounds.minimum.Z, point.Z)
    )
    bounds.maximum = Vector3.new(
        math.max(bounds.maximum.X, point.X),
        math.max(bounds.maximum.Y, point.Y),
        math.max(bounds.maximum.Z, point.Z)
    )
    bounds.count += 1
end

local function boxFromBounds(bounds: any, padding: number): (CFrame?, Vector3?)
    if bounds.count <= 0 then
        return nil, nil
    end
    local center = (bounds.minimum + bounds.maximum) * 0.5
    local rawSize = bounds.maximum - bounds.minimum
    local size = Vector3.new(
        math.max(MIN_BOX_AXIS, rawSize.X + padding * 2),
        math.max(MIN_BOX_AXIS, rawSize.Y + padding * 2),
        math.max(MIN_BOX_AXIS, rawSize.Z + padding * 2)
    )
    return CFrame.new(center), size
end

local function strongestInfluence(source: any): any?
    local strongest = nil
    local strongestWeight = -1
    for _, influence in ipairs(source.influences or {}) do
        if influence.weight > strongestWeight then
            strongest = influence
            strongestWeight = influence.weight
        end
    end
    return strongest
end

local function definitionCacheKey(binding: any): string
    local chunks = {}
    for index, record in ipairs(binding.records) do
        local scale = record.scale
        table.insert(chunks, string.format(
            "%d:%s:%s:%.6f,%.6f,%.6f",
            index,
            record.path,
            record.geometry.key,
            scale.X,
            scale.Y,
            scale.Z
        ))
    end
    local root = binding.root
    local headName = binding.headBone and binding.headBone.Name or ""
    local parentName = binding.headParentBone and binding.headParentBone.Name or ""
    local identity = tostring(
        binding.entity:GetAttribute("MonsterSlug")
        or binding.entity:GetAttribute("NpcSlug")
        or binding.entity:GetAttribute("CharacterArchetype")
        or binding.visual.Name
    )
    table.insert(chunks, string.format(
        "identity:%s|root:%.6f,%.6f,%.6f|head:%s|parent:%s",
        identity,
        root.Size.X,
        root.Size.Y,
        root.Size.Z,
        headName,
        parentName
    ))
    return table.concat(chunks, "|")
end

local function buildDefinition(binding: any): (any?, string?)
    local basis = binding.root.CFrame
    local headBone = binding.headBone
    local headParentBone = binding.headParentBone
    local hasHead = headBone ~= nil and headParentBone ~= nil
    local headFrame = if headBone then transformedBoneFrame(headBone) else nil
    local headCutoffY = math.huge
    if hasHead then
        headCutoffY = basis:PointToObjectSpace(transformedBoneFrame(headParentBone :: Bone).Position).Y
    end

    local broadRadius = 0
    local headBounds = newBounds()
    local bodyGroups = {}
    local totalVertices = 0

    for recordIndex, record in ipairs(binding.records) do
        prepareRecord(record)
        for _, source in ipairs(record.preparedVertices) do
            local worldPosition, positionError = vertexWorldPosition(binding, record, source)
            if not worldPosition then
                return nil, positionError
            end
            totalVertices += 1
            local bodyLocal = basis:PointToObjectSpace(worldPosition)
            broadRadius = math.max(broadRadius, (worldPosition - binding.root.Position).Magnitude)

            if hasHead and bodyLocal.Y >= headCutoffY then
                growBounds(headBounds, (headFrame :: CFrame):PointToObjectSpace(worldPosition))
            else
                local strongest = strongestInfluence(source)
                local groupKey = nil
                local group = nil
                local anchorFrame = nil
                if strongest then
                    local bone = boneForInfluence(binding, record, strongest.boneName)
                    if not bone or not bone.Parent then
                        return nil, ("dominant mesh bone %s is missing from runtime rig"):format(tostring(strongest.boneName))
                    end
                    groupKey = ("bone:%d:%s"):format(recordIndex, strongest.boneName)
                    group = bodyGroups[groupKey]
                    if not group then
                        group = {
                            kind = "bone",
                            recordIndex = recordIndex,
                            boneName = strongest.boneName,
                            bounds = newBounds(),
                        }
                        bodyGroups[groupKey] = group
                    end
                    anchorFrame = transformedBoneFrame(bone)
                else
                    groupKey = ("mesh:%d"):format(recordIndex)
                    group = bodyGroups[groupKey]
                    if not group then
                        group = {
                            kind = "mesh",
                            recordIndex = recordIndex,
                            bounds = newBounds(),
                        }
                        bodyGroups[groupKey] = group
                    end
                    anchorFrame = record.meshPart.CFrame
                end
                growBounds(group.bounds, (anchorFrame :: CFrame):PointToObjectSpace(worldPosition))
            end
        end
    end

    if totalVertices <= 0 then
        return nil, "visual mesh contains no render vertices"
    end

    local bodyBoxes = {}
    local groupKeys = {}
    for key in pairs(bodyGroups) do
        table.insert(groupKeys, key)
    end
    table.sort(groupKeys)
    for _, key in ipairs(groupKeys) do
        local group = bodyGroups[key]
        local localCFrame, size = boxFromBounds(group.bounds, BODY_BOX_PADDING)
        if localCFrame and size then
            table.insert(bodyBoxes, {
                kind = group.kind,
                recordIndex = group.recordIndex,
                boneName = group.boneName,
                localCFrame = localCFrame,
                size = size,
            })
        end
    end

    local headBox = nil
    if hasHead and headBounds.count > 0 then
        local localCFrame, size = boxFromBounds(headBounds, HEAD_BOX_PADDING)
        if localCFrame and size then
            headBox = {
                kind = "head",
                boneName = headBone.Name,
                localCFrame = localCFrame,
                size = size,
            }
        end
    end

    if #bodyBoxes == 0 and not headBox then
        return nil, "mesh bounds produced no combat hitboxes"
    end

    return {
        broadRadius = broadRadius + BROAD_RADIUS_PADDING,
        bodyBoxes = bodyBoxes,
        headBox = headBox,
        sourceVertexCount = totalVertices,
    }, nil
end

function HitboxDefinitionBuilder.MeshScale(meshPart: MeshPart): Vector3
    return meshScale(meshPart)
end

function HitboxDefinitionBuilder.Resolve(binding: any): (any?, string?)
    local key = definitionCacheKey(binding)
    local cached = definitionCache[key]
    if cached then
        return cached, nil
    end

    local definition, buildError = buildDefinition(binding)
    if not definition then
        return nil, buildError
    end
    definitionCache[key] = definition
    print(("[game1][combat-hitbox] definition cached · %d source vertices · %d body boxes · head=%s")
        :format(definition.sourceVertexCount, #definition.bodyBoxes, tostring(definition.headBox ~= nil)))
    return definition, nil
end

return table.freeze(HitboxDefinitionBuilder)
