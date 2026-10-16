local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local CombatShared = Shared:WaitForChild("combat")
local SkeletonHeadResolver = require(CombatShared:WaitForChild("SkeletonHeadResolver"))
local HitboxMeshGeometryCache = require(script.Parent:WaitForChild("HitboxMeshGeometryCache"))
local HitboxDefinitionBuilder = require(script.Parent:WaitForChild("HitboxDefinitionBuilder"))
local HitboxSpatialQueries = require(script.Parent:WaitForChild("HitboxSpatialQueries"))

local EntityHitboxService = {}
local started = false
local frameSerial = 0
local bindings: { [Model]: any } = {}

local DEBUG_FOLDER_NAME = "CombatHitboxDebugData"

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
        local geometry = HitboxMeshGeometryCache.Read(meshPart)
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
            scale = HitboxDefinitionBuilder.MeshScale(meshPart),
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

    local definition, buildError = HitboxDefinitionBuilder.Resolve(binding)
    if not definition then
        entity:SetAttribute("CombatHitboxMode", "unavailable")
        entity:SetAttribute("CombatHitboxCount", 0)
        warn(("[game1][combat-hitbox] %s hitbox build failed: %s")
            :format(entity:GetFullName(), tostring(buildError)))
        return { count = 0, headBoneName = "", hasHead = false }
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
            local hit = HitboxSpatialQueries.BoxContact(binding, boxCFrame, boxSize, originPosition, frameSerial)
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
            local hit = HitboxSpatialQueries.AimContact(binding, rayOrigin, direction, distanceLimit, frameSerial)
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
