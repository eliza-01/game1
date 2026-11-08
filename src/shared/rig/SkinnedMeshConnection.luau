--!strict
-- Shared skin/rigid-assembly connection used by Character and Studio Location.
-- Roblox resolves skinned mesh Bone names across physically connected parts
-- inside ONE Model. Authoring/importer joints remain authoritative: only add
-- a Weld when no existing joint path connects this part to its Bone carrier.
local Connection = {}

local function inAssembly(part: BasePart, model: Model): boolean
    return part:FindFirstAncestorOfClass("Model") == model
end

local function connected(model: Model, carrier: MeshPart, target: MeshPart): boolean
    local neighbours: {[BasePart]: {BasePart}} = {}
    for _, instance in ipairs(model:GetDescendants()) do
        if instance:IsA("JointInstance") or instance:IsA("WeldConstraint") then
            local a, b = instance.Part0, instance.Part1
            if a == nil or b == nil or a == b or not inAssembly(a, model)
                or not inAssembly(b, model) then
                error("skinned assembly contains an invalid or external joint: " .. instance.Name)
            end
            if neighbours[a] == nil then neighbours[a] = {} end
            if neighbours[b] == nil then neighbours[b] = {} end
            table.insert(neighbours[a], b)
            table.insert(neighbours[b], a)
        end
    end
    local seen: {[BasePart]: boolean} = {[carrier] = true}
    local queue: {BasePart} = {carrier}
    local head = 1
    while head <= #queue do
        local part = queue[head]
        head += 1
        if part == target then return true end
        for _, other in ipairs(neighbours[part] or {}) do
            if not seen[other] then
                seen[other] = true
                table.insert(queue, other)
            end
        end
    end
    return false
end

-- The published/imported mesh retains its authored skin weights; this helper
-- only supplies the assembly path to the already authored canonical Bones.
-- It neither copies Bones nor changes CFrames, collision flags or anchors.
function Connection.Connect(model: Model, carrier: MeshPart, mesh: MeshPart, weldName: string): boolean
    assert(model:IsA("Model") and carrier:IsA("MeshPart") and mesh:IsA("MeshPart"),
        "skinned connection requires a Model and two MeshParts")
    assert(carrier ~= mesh and inAssembly(carrier, model) and inAssembly(mesh, model),
        "skinned mesh and carrier must belong to the same direct Model")
    assert(type(weldName) == "string" and weldName ~= "", "missing skin weld name")
    if connected(model, carrier, mesh) then return false end
    local weld = Instance.new("Weld")
    weld.Name = weldName
    weld.Part0 = carrier
    weld.Part1 = mesh
    weld.C0 = carrier.CFrame:ToObjectSpace(mesh.CFrame)
    weld.C1 = CFrame.identity
    weld.Parent = mesh
    return true
end

return table.freeze(Connection)
