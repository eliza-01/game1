-- Detached published Model inspection. Never parent to Workspace or retain a clone.
local AssetService = game:GetService("AssetService")
local Alignment = {}
local function vector(v) return {v.X,v.Y,v.Z} end
function Alignment.Run(data)
    local loaded, editable = nil, nil
    local ok, result = xpcall(function()
        local id = assert(tonumber(data.modelAssetId), "MNPC invalid Model ID")
        assert(id > 0 and id % 1 == 0, "MNPC invalid Model ID")
        loaded = assert(AssetService:LoadAssetAsync(id), "MNPC published Model unavailable")
        local part = nil
        local nodes = loaded:GetDescendants()
        table.insert(nodes,loaded)
        for _, node in nodes do
            assert(not node:IsA("Bone") and not node:IsA("Animator") and not node:IsA("AnimationController")
                and not node:IsA("Humanoid") and not node:IsA("LuaSourceContainer"), "MNPC LOD1 imported non-static content")
            if node:IsA("BasePart") then
                assert(not part and node:IsA("MeshPart") and node.Name == "lod1", "MNPC expected exactly one lod1 MeshPart")
                part = node
            end
        end
        assert(part, "MNPC missing imported lod1 MeshPart")
        local meshId = assert(part.MeshId:match("^rbxassetid://(%d+)$"), "MNPC invalid imported Mesh ID")
        local meshSize, size = part.MeshSize, part.Size
        assert(meshSize.X>0 and meshSize.Y>0 and meshSize.Z>0 and size.X>0 and size.Y>0 and size.Z>0, "MNPC invalid imported size")
        editable = assert(AssetService:CreateEditableMeshAsync(part.MeshContent,{FixedSize=true}), "MNPC cannot read imported mesh; verify asset permissions")
        local faces = editable:GetFaces()
        assert(#faces>0 and #faces<=20000, "MNPC imported triangle budget exceeded")
        local vertices, seen = {}, {}
        local ratio = Vector3.new(size.X/meshSize.X,size.Y/meshSize.Y,size.Z/meshSize.Z)
        for _, faceId in faces do
            local ids = editable:GetFaceVertices(faceId)
            assert(#ids==3,"MNPC imported non-triangle face")
            for _, vertexId in ids do
                if not seen[vertexId] then
                    assert(#vertices<20000,"MNPC imported vertex budget exceeded")
                    assert(#editable:GetVertexBones(vertexId)==0, "MNPC imported skin weights")
                    local v = editable:GetPosition(vertexId)
                    table.insert(vertices,vector(Vector3.new(v.X*ratio.X,v.Y*ratio.Y,v.Z*ratio.Z)))
                    seen[vertexId]=true
                end
            end
        end
        return {meshId=meshId,size=vector(size),meshSize=vector(meshSize),vertices=vertices,triangles=#faces}
    end,debug.traceback)
    if editable then editable:Destroy() end
    if loaded then loaded:Destroy() end
    assert(ok,tostring(result))
    return result
end
return table.freeze(Alignment)
