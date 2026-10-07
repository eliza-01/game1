local AssetService = game:GetService("AssetService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local SkeletonHeadResolver = require(CombatShared:WaitForChild("SkeletonHeadResolver"))

local EntityHitboxService = {}
local started = false
local frameSerial = 0
local bindings: { [Model]: any } = {}
local geometryCache: { [string]: any } = {}
local definitionCache: { [string]: any } = {}

local DEBUG_FOLDER_NAME = "CombatHitboxDebugData"
local MIN_BOX_AXIS = 0.05
local BODY_BOX_PADDING = 0.035
local HEAD_BOX_PADDING = 0.015
local BROAD_RADIUS_PADDING = 0.25
local SAT_EPSILON = 1e-6

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

local function meshCacheKey(meshPart: MeshPart): string
    local meshId = tostring(meshPart.MeshId or "")
    if meshId ~= "" then
        return meshId
    end
    local ok, content = pcall(function()
        return meshPart.MeshContent
    end)
    return ok and tostring(content) or meshPart:GetFullName()
end

local function relativePath(instance: Instance, root: Instance): string
    local names = {}
    local cursor: Instance? = instance
    while cursor and cursor ~= root do
        table.insert(names, 1, cursor.Name)
        cursor = cursor.Parent
    end
    return table.concat(names, "/")
end

local function runtimeBones(container: Instance): { [string]: Bone }
    local result = {}
    for _, descendant in ipairs(container:GetDescendants()) do
        if descendant:IsA("Bone") and result[descendant.Name] == nil then
            result[descendant.Name] = descendant
        end
    end
    return result
end

local function meshPartsForVisual(visual: Model): { MeshPart }
    local result = {}
    for _, descendant in ipairs(visual:GetDescendants()) do
        if descendant:IsA("MeshPart")
            and descendant.Name ~= "RootCollider"
            and descendant.Name ~= "NavigationRoot"
            and descendant.Name ~= "GroundSensorPart"
        then
            table.insert(result, descendant)
        end
    end
    table.sort(result, function(left, right)
        return relativePath(left, visual) < relativePath(right, visual)
    end)
    return result
end

local function loadGeometry(meshPart: MeshPart): any
    local key = meshCacheKey(meshPart)
    local cached = geometryCache[key]
    if cached then
        while cached.state == "loading" do
            task.wait()
        end
        return cached
    end

    cached = {
        key = key,
        state = "loading",
        vertices = nil,
        vertexCount = 0,
        error = nil,
    }
    geometryCache[key] = cached

    local editable = nil
    local ok, payload = pcall(function()
        editable = AssetService:CreateEditableMeshAsync(meshPart.MeshContent, { FixedSize = true })
        if not editable then
            error("CreateEditableMeshAsync returned nil")
        end

        local vertices = {}
        for _, faceId in ipairs(editable:GetFaces()) do
            for _, vertexId in ipairs(editable:GetFaceVertices(faceId)) do
                if vertices[vertexId] == nil then
                    local influences = {}
                    local boneIds = editable:GetVertexBones(vertexId)
                    local weights = editable:GetVertexBoneWeights(vertexId)
                    local totalWeight = 0
                    for index, boneId in ipairs(boneIds) do
                        local weight = math.max(0, tonumber(weights[index]) or 0)
                        if weight > 0 then
                            table.insert(influences, {
                                boneName = editable:GetBoneName(boneId),
                                bindCFrame = editable:GetBoneCFrame(boneId),
                                weight = weight,
                            })
                            totalWeight += weight
                        end
                    end
                    if totalWeight > 1e-6 then
                        for _, influence in ipairs(influences) do
                            influence.weight /= totalWeight
                        end
                    end
                    vertices[vertexId] = {
                        position = editable:GetPosition(vertexId),
                        influences = influences,
                    }
                end
            end
        end

        local vertexCount = 0
        for _ in pairs(vertices) do
            vertexCount += 1
        end
        return {
            vertices = vertices,
            vertexCount = vertexCount,
        }
    end)

    if editable then
        pcall(function()
            editable:Destroy()
        end)
    end

    if not ok or type(payload) ~= "table" or (tonumber(payload.vertexCount) or 0) <= 0 then
        cached.state = "failed"
        cached.error = tostring(payload)
        warn(("[game1][combat-hitbox] cannot read mesh geometry %s: %s")
            :format(key, cached.error))
        return cached
    end

    cached.vertices = payload.vertices
    cached.vertexCount = payload.vertexCount
    cached.state = "ready"
    print(("[game1][combat-hitbox] source mesh cached · %s · %d vertices")
        :format(key, payload.vertexCount))
    return cached
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

local function resolveRuntimeBox(binding: any, definitionBox: any): (any?, string?)
    local anchor = nil
    if definitionBox.kind == "head" then
        anchor = binding.headBone
    elseif definitionBox.kind == "bone" then
        local record = binding.records[definitionBox.recordIndex]
        anchor = record and (record.bonesByName[definitionBox.boneName] or binding.bonesByName[definitionBox.boneName]) or nil
    elseif definitionBox.kind == "mesh" then
        local record = binding.records[definitionBox.recordIndex]
        anchor = record and record.meshPart or nil
    end
    if not anchor or not anchor.Parent then
        return nil, ("cannot resolve hitbox anchor %s"):format(tostring(definitionBox.boneName or definitionBox.kind))
    end
    return {
        anchor = anchor,
        localCFrame = definitionBox.localCFrame,
        size = definitionBox.size,
    }, nil
end

local function publishDebugData(binding: any)
    if not RunService:IsStudio() then
        return
    end
    local previous = binding.entity:FindFirstChild(DEBUG_FOLDER_NAME)
    if previous then
        previous:Destroy()
    end

    local folder = Instance.new("Folder")
    folder.Name = DEBUG_FOLDER_NAME
    folder.Parent = binding.entity

    local function addRecord(name: string, zone: string, box: any)
        local item = Instance.new("Folder")
        item.Name = name
        item:SetAttribute("Zone", zone)
        item:SetAttribute("LocalCFrame", box.localCFrame)
        item:SetAttribute("Size", box.size)
        local anchor = Instance.new("ObjectValue")
        anchor.Name = "Anchor"
        anchor.Value = box.anchor
        anchor.Parent = item
        item.Parent = folder
    end

    if binding.headBox then
        addRecord("Head", "head", binding.headBox)
    end
    for index, box in ipairs(binding.bodyBoxes) do
        addRecord(("Body%03d"):format(index), "body", box)
    end
end

local function applyDefinition(binding: any, definition: any): (boolean, string?)
    local bodyBoxes = {}
    for _, definitionBox in ipairs(definition.bodyBoxes or {}) do
        local runtimeBox, runtimeError = resolveRuntimeBox(binding, definitionBox)
        if not runtimeBox then
            return false, runtimeError
        end
        table.insert(bodyBoxes, runtimeBox)
    end

    local headBox = nil
    if definition.headBox then
        local runtimeHead, runtimeError = resolveRuntimeBox(binding, definition.headBox)
        if not runtimeHead then
            return false, runtimeError
        end
        headBox = runtimeHead
    end

    binding.definition = definition
    binding.bodyBoxes = bodyBoxes
    binding.headBox = headBox
    binding.worldFrameSerial = -1
    binding.worldHeadCFrame = nil
    binding.worldBodyCFrames = {}
    publishDebugData(binding)
    return true, nil
end

local function boxAnchorFrame(anchor: Instance): CFrame?
    if anchor:IsA("Bone") then
        return transformedBoneFrame(anchor)
    elseif anchor:IsA("BasePart") then
        return anchor.CFrame
    end
    return nil
end

local function refreshWorldFrames(binding: any)
    if binding.worldFrameSerial == frameSerial then
        return
    end
    binding.worldFrameSerial = frameSerial

    if binding.headBox then
        local anchorFrame = boxAnchorFrame(binding.headBox.anchor)
        binding.worldHeadCFrame = anchorFrame and (anchorFrame * binding.headBox.localCFrame) or nil
    else
        binding.worldHeadCFrame = nil
    end

    local frames = binding.worldBodyCFrames
    table.clear(frames)
    for index, box in ipairs(binding.bodyBoxes) do
        local anchorFrame = boxAnchorFrame(box.anchor)
        frames[index] = anchorFrame and (anchorFrame * box.localCFrame) or nil
    end
end

local function obbIntersects(aFrame: CFrame, aSize: Vector3, bFrame: CFrame, bSize: Vector3): boolean
    local a0 = aFrame.RightVector
    local a1 = aFrame.UpVector
    local a2 = -aFrame.LookVector
    local b0 = bFrame.RightVector
    local b1 = bFrame.UpVector
    local b2 = -bFrame.LookVector

    local ah0, ah1, ah2 = aSize.X * 0.5, aSize.Y * 0.5, aSize.Z * 0.5
    local bh0, bh1, bh2 = bSize.X * 0.5, bSize.Y * 0.5, bSize.Z * 0.5

    local r00, r01, r02 = a0:Dot(b0), a0:Dot(b1), a0:Dot(b2)
    local r10, r11, r12 = a1:Dot(b0), a1:Dot(b1), a1:Dot(b2)
    local r20, r21, r22 = a2:Dot(b0), a2:Dot(b1), a2:Dot(b2)
    local ar00, ar01, ar02 = math.abs(r00) + SAT_EPSILON, math.abs(r01) + SAT_EPSILON, math.abs(r02) + SAT_EPSILON
    local ar10, ar11, ar12 = math.abs(r10) + SAT_EPSILON, math.abs(r11) + SAT_EPSILON, math.abs(r12) + SAT_EPSILON
    local ar20, ar21, ar22 = math.abs(r20) + SAT_EPSILON, math.abs(r21) + SAT_EPSILON, math.abs(r22) + SAT_EPSILON

    local delta = bFrame.Position - aFrame.Position
    local t0, t1, t2 = delta:Dot(a0), delta:Dot(a1), delta:Dot(a2)

    if math.abs(t0) > ah0 + bh0 * ar00 + bh1 * ar01 + bh2 * ar02 then return false end
    if math.abs(t1) > ah1 + bh0 * ar10 + bh1 * ar11 + bh2 * ar12 then return false end
    if math.abs(t2) > ah2 + bh0 * ar20 + bh1 * ar21 + bh2 * ar22 then return false end

    if math.abs(t0 * r00 + t1 * r10 + t2 * r20) > ah0 * ar00 + ah1 * ar10 + ah2 * ar20 + bh0 then return false end
    if math.abs(t0 * r01 + t1 * r11 + t2 * r21) > ah0 * ar01 + ah1 * ar11 + ah2 * ar21 + bh1 then return false end
    if math.abs(t0 * r02 + t1 * r12 + t2 * r22) > ah0 * ar02 + ah1 * ar12 + ah2 * ar22 + bh2 then return false end

    if math.abs(t2 * r10 - t1 * r20) > ah1 * ar20 + ah2 * ar10 + bh1 * ar02 + bh2 * ar01 then return false end
    if math.abs(t2 * r11 - t1 * r21) > ah1 * ar21 + ah2 * ar11 + bh0 * ar02 + bh2 * ar00 then return false end
    if math.abs(t2 * r12 - t1 * r22) > ah1 * ar22 + ah2 * ar12 + bh0 * ar01 + bh1 * ar00 then return false end

    if math.abs(t0 * r20 - t2 * r00) > ah0 * ar20 + ah2 * ar00 + bh1 * ar12 + bh2 * ar11 then return false end
    if math.abs(t0 * r21 - t2 * r01) > ah0 * ar21 + ah2 * ar01 + bh0 * ar12 + bh2 * ar10 then return false end
    if math.abs(t0 * r22 - t2 * r02) > ah0 * ar22 + ah2 * ar02 + bh0 * ar11 + bh1 * ar10 then return false end

    if math.abs(t1 * r00 - t0 * r10) > ah0 * ar10 + ah1 * ar00 + bh1 * ar22 + bh2 * ar21 then return false end
    if math.abs(t1 * r01 - t0 * r11) > ah0 * ar11 + ah1 * ar01 + bh0 * ar22 + bh2 * ar20 then return false end
    if math.abs(t1 * r02 - t0 * r12) > ah0 * ar12 + ah1 * ar02 + bh0 * ar21 + bh1 * ar20 then return false end

    return true
end

local function sphereIntersectsBox(center: Vector3, radius: number, boxCFrame: CFrame, boxSize: Vector3): boolean
    local localCenter = boxCFrame:PointToObjectSpace(center)
    local half = boxSize * 0.5
    local closest = Vector3.new(
        math.clamp(localCenter.X, -half.X, half.X),
        math.clamp(localCenter.Y, -half.Y, half.Y),
        math.clamp(localCenter.Z, -half.Z, half.Z)
    )
    return (localCenter - closest).Magnitude <= radius
end

local function closestPointOnBox(boxCFrame: CFrame, boxSize: Vector3, worldPoint: Vector3): Vector3
    local localPoint = boxCFrame:PointToObjectSpace(worldPoint)
    local half = boxSize * 0.5
    return boxCFrame:PointToWorldSpace(Vector3.new(
        math.clamp(localPoint.X, -half.X, half.X),
        math.clamp(localPoint.Y, -half.Y, half.Y),
        math.clamp(localPoint.Z, -half.Z, half.Z)
    ))
end

local function queryBinding(binding: any, weaponCFrame: CFrame, weaponSize: Vector3, originPosition: Vector3?): any?
    if not sphereIntersectsBox(binding.root.Position, binding.definition.broadRadius, weaponCFrame, weaponSize) then
        return nil
    end
    refreshWorldFrames(binding)

    if binding.headBox and binding.worldHeadCFrame
        and obbIntersects(weaponCFrame, weaponSize, binding.worldHeadCFrame, binding.headBox.size)
    then
        local hitPosition = closestPointOnBox(binding.worldHeadCFrame, binding.headBox.size, weaponCFrame.Position)
        return {
            boneName = binding.headBone and binding.headBone.Name or "",
            geometryRole = "head",
            hitPosition = hitPosition,
        }
    end

    local bestPosition = nil
    local bestDistance = math.huge
    local bestBoneName = ""
    for index, bodyBox in ipairs(binding.bodyBoxes) do
        local worldCFrame = binding.worldBodyCFrames[index]
        if worldCFrame and obbIntersects(weaponCFrame, weaponSize, worldCFrame, bodyBox.size) then
            local contact = closestPointOnBox(worldCFrame, bodyBox.size, weaponCFrame.Position)
            local distance = if typeof(originPosition) == "Vector3"
                then (contact - originPosition).Magnitude
                else (contact - weaponCFrame.Position).Magnitude
            if distance < bestDistance then
                bestDistance = distance
                bestPosition = contact
                bestBoneName = if bodyBox.anchor:IsA("Bone") then bodyBox.anchor.Name else ""
            end
        end
    end

    if not bestPosition then
        return nil
    end
    return {
        boneName = bestBoneName,
        geometryRole = "body",
        hitPosition = bestPosition,
    }
end

local function rayBoxDistance(
    rayOrigin: Vector3,
    rayDirection: Vector3,
    maxDistance: number,
    boxCFrame: CFrame,
    boxSize: Vector3
): number?
    local localOrigin = boxCFrame:PointToObjectSpace(rayOrigin)
    local localDirection = boxCFrame:VectorToObjectSpace(rayDirection)
    local half = boxSize * 0.5
    local tMin = 0
    local tMax = maxDistance

    local function clipAxis(originAxis: number, directionAxis: number, halfAxis: number): boolean
        if math.abs(directionAxis) <= 1e-8 then
            return math.abs(originAxis) <= halfAxis
        end
        local inverse = 1 / directionAxis
        local near = (-halfAxis - originAxis) * inverse
        local far = (halfAxis - originAxis) * inverse
        if near > far then
            near, far = far, near
        end
        tMin = math.max(tMin, near)
        tMax = math.min(tMax, far)
        return tMin <= tMax
    end

    if not clipAxis(localOrigin.X, localDirection.X, half.X)
        or not clipAxis(localOrigin.Y, localDirection.Y, half.Y)
        or not clipAxis(localOrigin.Z, localDirection.Z, half.Z)
    then
        return nil
    end
    return tMin
end

local function raySegmentNearSphere(
    rayOrigin: Vector3,
    rayDirection: Vector3,
    maxDistance: number,
    center: Vector3,
    radius: number
): boolean
    local along = math.clamp((center - rayOrigin):Dot(rayDirection), 0, maxDistance)
    local closest = rayOrigin + rayDirection * along
    return (center - closest).Magnitude <= radius
end

local function queryAimBinding(
    binding: any,
    rayOrigin: Vector3,
    rayDirection: Vector3,
    maxDistance: number
): any?
    if not raySegmentNearSphere(
        rayOrigin,
        rayDirection,
        maxDistance,
        binding.root.Position,
        binding.definition.broadRadius
    ) then
        return nil
    end

    refreshWorldFrames(binding)
    local bestDistance = math.huge
    local bestZone = nil
    local bestBoneName = ""

    -- Head is tested first and wins exact boundary ties. This does not deal
    -- damage by itself; it only classifies the first combat hitbox under the
    -- center-screen aim line.
    if binding.headBox and binding.worldHeadCFrame then
        local distance = rayBoxDistance(
            rayOrigin,
            rayDirection,
            maxDistance,
            binding.worldHeadCFrame,
            binding.headBox.size
        )
        if distance ~= nil then
            bestDistance = distance
            bestZone = "head"
            bestBoneName = binding.headBone and binding.headBone.Name or ""
        end
    end

    for index, bodyBox in ipairs(binding.bodyBoxes) do
        local worldCFrame = binding.worldBodyCFrames[index]
        if worldCFrame then
            local distance = rayBoxDistance(rayOrigin, rayDirection, maxDistance, worldCFrame, bodyBox.size)
            if distance ~= nil and distance < bestDistance - SAT_EPSILON then
                bestDistance = distance
                bestZone = "body"
                bestBoneName = if bodyBox.anchor:IsA("Bone") then bodyBox.anchor.Name else ""
            end
        end
    end

    if not bestZone then
        return nil
    end
    return {
        zone = bestZone,
        boneName = bestBoneName,
        distance = bestDistance,
        hitPosition = rayOrigin + rayDirection * bestDistance,
    }
end

local function clearAttributes(entity: Model)
    entity:SetAttribute("CombatHitboxMode", nil)
    entity:SetAttribute("CombatHitboxCount", nil)
    entity:SetAttribute("CombatHeadBoneName", nil)
    entity:SetAttribute("CombatTargetGeometry", nil)
end

function EntityHitboxService.Detach(entity: Model)
    bindings[entity] = nil
    local debugFolder = entity:FindFirstChild(DEBUG_FOLDER_NAME)
    if debugFolder then
        debugFolder:Destroy()
    end
    clearAttributes(entity)
end

function EntityHitboxService.Attach(entity: Model, visual: Model): any
    EntityHitboxService.Detach(entity)

    local root = entity:FindFirstChild("RootCollider")
    if not root or not root:IsA("BasePart") then
        entity:SetAttribute("CombatHitboxMode", "unavailable")
        entity:SetAttribute("CombatHitboxCount", 0)
        warn(("[game1][combat-hitbox] %s has no RootCollider; combat hitboxes were not built")
            :format(entity:GetFullName()))
        return { count = 0, headBoneName = "", hasHead = false }
    end

    local resolved = SkeletonHeadResolver.Resolve(visual)
    local records = {}
    for _, meshPart in ipairs(meshPartsForVisual(visual)) do
        local geometry = loadGeometry(meshPart)
        if geometry.state ~= "ready" then
            entity:SetAttribute("CombatHitboxMode", "unavailable")
            entity:SetAttribute("CombatHitboxCount", 0)
            warn(("[game1][combat-hitbox] %s could not build hitboxes because %s is unreadable")
                :format(entity:GetFullName(), meshPart:GetFullName()))
            return { count = 0, headBoneName = "", hasHead = false }
        end
        table.insert(records, {
            meshPart = meshPart,
            path = relativePath(meshPart, visual),
            geometry = geometry,
            scale = meshScale(meshPart),
            bonesByName = runtimeBones(meshPart),
            preparedVertices = nil,
        })
    end

    if #records == 0 then
        entity:SetAttribute("CombatHitboxMode", "unavailable")
        entity:SetAttribute("CombatHitboxCount", 0)
        warn(("[game1][combat-hitbox] %s has no visual MeshPart; combat hitboxes were not built")
            :format(entity:GetFullName()))
        return { count = 0, headBoneName = "", hasHead = false }
    end

    local binding = {
        entity = entity,
        visual = visual,
        root = root,
        records = records,
        bonesByName = runtimeBones(visual),
        headBone = resolved.headBone,
        headParentBone = resolved.headParentBone,
    }

    local cacheKey = definitionCacheKey(binding)
    local definition = definitionCache[cacheKey]
    if not definition then
        local buildError = nil
        definition, buildError = buildDefinition(binding)
        if not definition then
            entity:SetAttribute("CombatHitboxMode", "unavailable")
            entity:SetAttribute("CombatHitboxCount", 0)
            warn(("[game1][combat-hitbox] %s hitbox build failed: %s")
                :format(entity:GetFullName(), tostring(buildError)))
            return { count = 0, headBoneName = "", hasHead = false }
        end
        definitionCache[cacheKey] = definition
        print(("[game1][combat-hitbox] definition cached · %d source vertices · %d body boxes · head=%s")
            :format(definition.sourceVertexCount, #definition.bodyBoxes, tostring(definition.headBox ~= nil)))
    end

    local applied, applyError = applyDefinition(binding, definition)
    if not applied then
        entity:SetAttribute("CombatHitboxMode", "unavailable")
        entity:SetAttribute("CombatHitboxCount", 0)
        warn(("[game1][combat-hitbox] %s cached definition could not bind: %s")
            :format(entity:GetFullName(), tostring(applyError)))
        return { count = 0, headBoneName = "", hasHead = false }
    end

    bindings[entity] = binding
    local count = #binding.bodyBoxes + (if binding.headBox then 1 else 0)
    entity:SetAttribute("CombatHitboxMode", "precomputed_bone_boxes")
    entity:SetAttribute("CombatHitboxCount", count)
    entity:SetAttribute("CombatHeadBoneName", binding.headBone and binding.headBone.Name or "")
    entity:SetAttribute("CombatTargetGeometry", "precomputed_mesh_bounds")

    return {
        count = count,
        headBoneName = binding.headBone and binding.headBone.Name or "",
        hasHead = binding.headBox ~= nil,
    }
end

function EntityHitboxService.QueryDamageablesInBox(
    exclude: Model?,
    boxCFrame: CFrame,
    boxSize: Vector3,
    excludedTargets: { [Model]: boolean }?
): { any }
    local results = {}
    local originPosition = nil
    if exclude then
        local root = exclude:FindFirstChild("RootCollider")
        if root and root:IsA("BasePart") then
            originPosition = root.Position
        end
    end

    for entity, binding in pairs(bindings) do
        if entity ~= exclude
            and (not excludedTargets or excludedTargets[entity] ~= true)
            and entity.Parent ~= nil
            and binding.visual.Parent ~= nil
            and entity:GetAttribute("Damageable") == true
        then
            local hit = queryBinding(binding, boxCFrame, boxSize, originPosition)
            if hit then
                table.insert(results, {
                    model = entity,
                    hit = hit,
                    mode = "precomputed_bone_boxes",
                })
            end
        end
    end
    return results
end


function EntityHitboxService.RaycastAimRegions(
    exclude: Model?,
    rayOrigin: Vector3,
    rayDirection: Vector3,
    maxDistance: number
): any?
    if typeof(rayOrigin) ~= "Vector3" or typeof(rayDirection) ~= "Vector3" then
        return nil
    end
    local distanceLimit = math.max(0, tonumber(maxDistance) or 0)
    local magnitude = rayDirection.Magnitude
    if distanceLimit <= 0 or magnitude <= 1e-6 then
        return nil
    end
    local direction = rayDirection / magnitude

    local best = nil
    local bestDistance = math.huge
    for entity, binding in pairs(bindings) do
        if entity ~= exclude
            and entity.Parent ~= nil
            and binding.visual.Parent ~= nil
            and entity:GetAttribute("Damageable") == true
        then
            local hit = queryAimBinding(binding, rayOrigin, direction, distanceLimit)
            if hit and hit.distance < bestDistance then
                bestDistance = hit.distance
                best = {
                    model = entity,
                    zone = hit.zone,
                    boneName = hit.boneName,
                    hitPosition = hit.hitPosition,
                    distance = hit.distance,
                    mode = "precomputed_bone_boxes",
                }
            end
        end
    end
    return best
end

function EntityHitboxService.Start()
    if started then
        return
    end
    started = true
    RunService.Heartbeat:Connect(function()
        frameSerial += 1
    end)
    print("[game1][combat-hitbox] precomputed bone-local mesh bounds ready")
end

return table.freeze(EntityHitboxService)
