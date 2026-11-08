-- Location-only normalization of Roblox importer scaffolding on a FRESH,
-- detached LoadAssetAsync clone. Never run this on a placed Model.
local Normalize = {}

local function closeFrame(a: CFrame, b: CFrame): boolean
    return (a.Position - b.Position).Magnitude < 0.0001
        and a.LookVector:Dot(b.LookVector) > 0.999999
        and a.UpVector:Dot(b.UpVector) > 0.999999
end

function Normalize.Apply(model: Model, manifest: any): CFrame
    if model.Parent ~= nil then
        error("published Location normalization requires a detached Model")
    end
    local authoredPivot = model:GetPivot()
    local roots = {}
    for _, obj in ipairs(model:GetDescendants()) do
        if obj.Name == "RootPart" then table.insert(roots, obj) end
    end
    if #roots == 0 then return authoredPivot end
    if #roots ~= 1 or not roots[1]:IsA("Part") or roots[1].Parent ~= model then
        error("published Location asset has an unsupported importer RootPart")
    end
    if type(manifest) ~= "table" or manifest.schemaVersion ~= 2
        or manifest.rigKind ~= "skinned" or manifest.carrierName ~= "rig_carrier" then
        error("importer RootPart normalization requires a skinned v2 manifest")
    end
    local root = roots[1] :: Part
    if root.Transparency < 0.99 then
        error("published Location RootPart is visible authored geometry")
    end
    local expected = {}
    for _, row in ipairs(manifest.parts or {}) do
        if type(row.name) ~= "string" or expected[row.name] ~= nil then
            error("invalid Location manifest during importer normalization")
        end
        expected[row.name] = row.role
    end
    local hasCollider = false
    for name, role in pairs(expected) do
        if role == "collider" then
            local collider = model:FindFirstChild(name)
            hasCollider = collider ~= nil and collider:IsA("MeshPart")
            if hasCollider then break end
        end
    end
    -- Roblox import currently leaves CanCollide/CanQuery enabled on its
    -- transparent assembly RootPart. Those flags are importer defaults, not
    -- authored physics. Removal is safe only when the same immutable manifest
    -- supplies a real collider that survives normalization and is configured
    -- by StudioMeshPhysicsCore immediately after validation.
    if not hasCollider then
        error("published Location RootPart has no authored collider replacement")
    end
    local carrier = model:FindFirstChild("rig_carrier")
    if not carrier or not carrier:IsA("MeshPart") or expected[carrier.Name] ~= "rig_carrier" then
        error("importer RootPart has no authored rig_carrier target")
    end
    local rootBones = {}
    for _, child in ipairs(root:GetChildren()) do
        if child:IsA("Bone") then
            table.insert(rootBones, child)
        elseif not child:IsA("Motor6D") then
            error("importer RootPart contains unsupported child: " .. child.ClassName)
        end
    end
    local rootMotors = {}
    for _, obj in ipairs(model:GetDescendants()) do
        if obj:IsA("JointInstance") and (obj.Part0 == root or obj.Part1 == root) then
            if not obj:IsA("Motor6D") then
                error("importer RootPart contains unsupported joint: " .. obj.ClassName)
            end
            local other = if obj.Part0 == root then obj.Part1 else obj.Part0
            if not other or not other:IsA("MeshPart") or not other:IsDescendantOf(model)
                or expected[other.Name] == nil then
                error("importer RootPart Motor6D has an unsafe endpoint")
            end
            table.insert(rootMotors, obj)
        end
    end
    local partState = {}
    for _, obj in ipairs(model:GetDescendants()) do
        if obj:IsA("MeshPart") then
            partState[obj] = {frame = obj.CFrame, size = obj.Size}
        end
    end
    local boneState = {}
    for _, bone in ipairs(rootBones) do
        boneState[bone] = {world = bone.WorldCFrame, transform = bone.Transform}
    end
    if model.PrimaryPart == root then model.PrimaryPart = nil end
    for _, motor in ipairs(rootMotors) do motor:Destroy() end
    for _, bone in ipairs(rootBones) do
        local state = boneState[bone]
        bone.Parent = carrier
        bone.CFrame = carrier.CFrame:ToObjectSpace(state.world)
        bone.Transform = state.transform
    end
    root:Destroy()
    if model.PrimaryPart == nil then model.WorldPivot = authoredPivot end
    for part, state in pairs(partState) do
        if part.Parent == nil or part.CFrame ~= state.frame or part.Size ~= state.size then
            error("importer normalization changed published MeshPart transform")
        end
    end
    for bone, state in pairs(boneState) do
        if bone.Parent == nil or not closeFrame(bone.WorldCFrame, state.world)
            or bone.Transform ~= state.transform then
            error("importer normalization changed published Bone pose")
        end
    end
    if not closeFrame(model:GetPivot(), authoredPivot) then
        error("importer normalization changed published Model pivot")
    end
    return authoredPivot
end

return table.freeze(Normalize)
