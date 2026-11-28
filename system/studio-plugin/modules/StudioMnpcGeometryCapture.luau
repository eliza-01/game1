-- Edit-only read of actual published mesh topology/skin weights. No runtime dependency.
-- The skinning equation uses the same scaled mesh-space bind convention as
-- HitboxDefinitionBuilder, but consumes all influences, not OBBs.
local AssetService = game:GetService("AssetService")
local Geometry = {}
local MAX_TRIANGLES = 30000 -- bounded JSON transport; fail, never truncate
local function scale(v, s) return Vector3.new(v.X*s.X, v.Y*s.Y, v.Z*s.Z) end
local function quantize(n) return math.round(n*100000)/100000 end
local function xyz(v) return {quantize(v.X), quantize(v.Y), quantize(v.Z)} end

local function boneByName(scope, name)
    local found = nil
    for _, node in scope:GetDescendants() do
        if node:IsA("Bone") and node.Name == name then
            assert(not found, "MNPC ambiguous skin bone " .. name .. " in " .. scope.Name)
            found = node
        end
    end
    return found
end

function Geometry.Read(part, owner, rootFrame, remaining)
    local editable = nil
    local ok, result = xpcall(function()
        editable = assert(AssetService:CreateEditableMeshAsync(part.MeshContent, {FixedSize = true}),
            "MNPC cannot read mesh " .. part.Name .. "; check asset ownership / EditableMesh access")
        local faces = editable:GetFaces()
        assert(#faces > 0 and #faces <= remaining and #faces <= MAX_TRIANGLES, "MNPC captured geometry exceeds triangle budget")
        local meshSize = part.MeshSize
        assert(meshSize.X > 0 and meshSize.Y > 0 and meshSize.Z > 0, "MNPC invalid mesh size")
        local s = Vector3.new(part.Size.X/meshSize.X, part.Size.Y/meshSize.Y, part.Size.Z/meshSize.Z)
        local boneFrames, vertices, uvs, triangles = {}, {}, {}, {}
        local vertexIndices, uvIndices = {}, {}
        local function bind(boneId)
            if boneFrames[boneId] then return boneFrames[boneId] end
            local name = editable:GetBoneName(boneId)
            local bone = boneByName(part, name) or boneByName(owner, name)
            assert(bone, "MNPC missing skin bone: " .. name .. " in " .. part.Name)
            local raw = editable:GetBoneCFrame(boneId)
            local bindFrame = CFrame.new(scale(raw.Position,s))*raw.Rotation
            -- Refuse incompatible/ambiguous bind spaces rather than produce a distorted LOD.
            local delta = (part.CFrame*bindFrame):ToObjectSpace(bone.WorldCFrame)
            local _, angle = delta:ToAxisAngle()
            assert(delta.Position.Magnitude <= 0.05 and math.abs(angle) <= math.rad(2),
                "MNPC skin bind mismatch: " .. part.Name .. "/" .. name)
            local item = {bind = bindFrame, posed = rootFrame:ToObjectSpace(bone.TransformedWorldCFrame)}
            boneFrames[boneId] = item
            return item
        end
        local function vertex(id)
            if vertexIndices[id] then return vertexIndices[id] end
            local p = scale(editable:GetPosition(id),s)
            local ids, weights = editable:GetVertexBones(id), editable:GetVertexBoneWeights(id)
            assert(#ids == #weights and #ids <= 4, "MNPC invalid skin influence list")
            local out, total = Vector3.zero, 0
            for i, bid in ids do
                local w = weights[i]
                assert(w >= 0 and w <= 1, "MNPC invalid skin weight")
                if w > 0 then
                    local b = bind(bid)
                    out += b.posed:PointToWorldSpace(b.bind:PointToObjectSpace(p))*w
                    total += w
                end
            end
            if #ids > 0 then
                assert(total > 0.000001, "MNPC vertex has zero skin weight")
                out /= total
            else
                out = rootFrame:PointToObjectSpace(part.CFrame:PointToWorldSpace(p))
            end
            table.insert(vertices, xyz(out)); vertexIndices[id] = #vertices
            return #vertices
        end
        local function uv(id)
            if uvIndices[id] then return uvIndices[id] end
            local p = assert(editable:GetUV(id), "MNPC missing UV")
            table.insert(uvs, {quantize(p.X),quantize(p.Y)}); uvIndices[id] = #uvs
            return #uvs
        end
        local appearance = part:FindFirstChildOfClass("SurfaceAppearance")
        local textured = part.TextureID ~= "" or (appearance and appearance.ColorMap ~= "")
        if not textured then uvs[1] = {0.5,0.5} end
        for _, faceId in faces do
            local v = editable:GetFaceVertices(faceId)
            assert(#v == 3, "MNPC requires triangle topology")
            local u = if textured then editable:GetFaceUVs(faceId) else nil
            assert(not textured or #u == 3, "MNPC missing corner UVs")
            -- Non-white vertex tint cannot be silently lost by the color atlas.
            for _, cid in editable:GetFaceColors(faceId) do
                local c = editable:GetColor(cid)
                assert(c and c.R >= 0.999 and c.G >= 0.999 and c.B >= 0.999 and editable:GetColorAlpha(cid) >= 0.999,
                    "MNPC vertex colors/alpha require a separate bake: " .. part.Name)
            end
            table.insert(triangles, {vertex(v[1]),vertex(v[2]),vertex(v[3]),
                if textured then uv(u[1]) else 1, if textured then uv(u[2]) else 1, if textured then uv(u[3]) else 1})
        end
        local color = if appearance and appearance.ColorMap ~= "" then appearance.Color else part.Color
        return {vertices=vertices, uvs=uvs, triangles=triangles, tint={color.R,color.G,color.B},
            alphaMode=if appearance and appearance.ColorMap ~= "" then appearance.AlphaMode.Name else "Texture"}
    end, debug.traceback)
    if editable then editable:Destroy() end
    assert(ok, tostring(result))
    return result
end
Geometry.MaxTriangles = MAX_TRIANGLES
return table.freeze(Geometry)
