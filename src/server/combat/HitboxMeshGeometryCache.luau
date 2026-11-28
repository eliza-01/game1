-- Source-mesh reader and per-MeshId in-flight cache. The EditableMesh exists only
-- during the initial read; queries never access AssetService.
local AssetService = game:GetService("AssetService")

local HitboxMeshGeometryCache = {}
local geometryCache: { [string]: any } = {}

function HitboxMeshGeometryCache.Key(meshPart: MeshPart): string
    local meshId = tostring(meshPart.MeshId or "")
    if meshId ~= "" then
        return meshId
    end
    local ok, content = pcall(function()
        return meshPart.MeshContent
    end)
    return ok and tostring(content) or meshPart:GetFullName()
end

function HitboxMeshGeometryCache.Read(meshPart: MeshPart, retryFailed: boolean?): any
    local key = HitboxMeshGeometryCache.Key(meshPart)
    local cached = geometryCache[key]
    if retryFailed and cached and cached.state == "failed" and cached.users == 0 then
        geometryCache[key] = nil
        cached = nil
    end
    if cached then
        cached.users += 1
        while cached.state == "loading" do
            task.wait()
        end
        return cached
    end

    cached = {
        key = key,
        state = "loading",
        users = 1,
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
    print(("[game1][combat-hitbox] source mesh read · %s · %d vertices")
        :format(key, payload.vertexCount))
    return cached
end

-- Ready geometry is shared only by overlapping builders. Failed reads retain
-- just their small diagnostic record, preserving the existing permission policy.
function HitboxMeshGeometryCache.Release(cached: any)
    assert(cached.users > 0, "hitbox geometry lease released twice")
    cached.users -= 1
    if cached.users == 0 and cached.state == "ready" then
        geometryCache[cached.key] = nil
        cached.vertices = nil
    end
end

return table.freeze(HitboxMeshGeometryCache)
