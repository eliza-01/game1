-- Rebuild authored but unweighted socket Bones after Roblox Model Asset import.
-- Roblox may cull Bones with zero skinned vertices. The registered FBX rest
-- matrices provide parent-relative transforms; imported weighted Bones anchor
-- these transforms in the actual loaded rig. No vertex weights are changed.
-- Never guess locations if an authored transform or imported anchor is missing.
local Recovery = {}

local MAX_BONES = 128
local MAX_COORDINATE = 100000
local MAX_OFFSET = 10000
local REST_TOLERANCE = 0.02

local function authoredCFrame(values: any): CFrame?
    if typeof(values) ~= "table" or #values ~= 16 then
        return nil
    end
    local n = table.create(16)
    for i = 1, 16 do
        local value = values[i]
        if typeof(value) ~= "number" or value ~= value or math.abs(value) > MAX_COORDINATE then
            return nil
        end
        n[i] = value
    end
    if math.abs(n[13]) > 0.001 or math.abs(n[14]) > 0.001
        or math.abs(n[15]) > 0.001 or math.abs(n[16] - 1) > 0.001 then
        return nil
    end
    local x = Vector3.new(n[1], n[5], n[9])
    local y = Vector3.new(n[2], n[6], n[10])
    local z = Vector3.new(n[3], n[7], n[11])
    if math.abs(x.Magnitude - 1) > REST_TOLERANCE
        or math.abs(y.Magnitude - 1) > REST_TOLERANCE
        or math.abs(z.Magnitude - 1) > REST_TOLERANCE
        or math.abs(x:Dot(y)) > REST_TOLERANCE
        or math.abs(x:Dot(z)) > REST_TOLERANCE
        or math.abs(y:Dot(z)) > REST_TOLERANCE
        or (x:Cross(y) - z).Magnitude > REST_TOLERANCE then
        return nil
    end
    return CFrame.fromMatrix(Vector3.new(n[4], n[8], n[12]), x, y, z)
end

local function collect(mesh: MeshPart, authored: any): ({[string]: any}, {[string]: Attachment}, {string})
    local specs: {[string]: any} = {}
    local present: {[string]: Attachment} = {}
    local problems = {}
    if typeof(authored) ~= "table" or #authored > MAX_BONES then
        return specs, present, {"no trustworthy FBX rest-pose manifest"}
    end
    for _, entry in authored do
        if typeof(entry) == "table" and typeof(entry.name) == "string"
            and entry.name:sub(-7) == "_socket" then
            if specs[entry.name] then
                table.insert(problems, "duplicate authored socket " .. entry.name)
            else
                local frame = authoredCFrame(entry.matrixLocal)
                if frame == nil then
                    table.insert(problems, "invalid rest transform for " .. entry.name)
                else
                    specs[entry.name] = {parent = entry.parent or "", frame = frame}
                end
            end
        end
    end
    for _, instance in mesh:GetDescendants() do
        if instance:IsA("Attachment") and specs[instance.Name] then
            if present[instance.Name] then
                table.insert(problems, "duplicate imported socket " .. instance.Name)
            else
                present[instance.Name] = instance
            end
        end
    end
    return specs, present, problems
end

-- The required parent is an already imported Bone or one reconstructed in
-- this pass. Using its imported CFrame avoids inventing a Roblox world origin
-- or deriving transforms from a resized/rotated external Model root.
function Recovery.Restore(mesh: MeshPart, authored: any): ({string}, {string})
    local specs, present, problems = collect(mesh, authored)
    if #problems > 0 then
        return {}, problems
    end
    local restored = {}
    local remaining = {}
    for name in specs do
        if not present[name] then
            remaining[name] = true
        end
    end

    -- Any already imported Attachment is a valid spatial socket. Preserve it
    -- rather than creating a duplicate name in the published rig.
    -- Imported armature roots with positive weights (e.g. door hinge) provide
    -- an absolute Roblox reference. Child offsets are authored in Blender's
    -- shared bone-local coordinate basis, so global FBX axis changes cancel.
    for _ = 1, MAX_BONES do
        local advanced = false
        for name in remaining do
            local spec = specs[name]
            local parent = present[spec.parent]
            if parent and parent:IsA("Bone") and specs[spec.parent] then
                local localFrame = specs[spec.parent].frame:ToObjectSpace(spec.frame)
                if localFrame.Position.Magnitude > MAX_OFFSET then
                    table.insert(problems, name .. ": authored offset exceeds safety limit")
                else
                    local replacement = Instance.new("Bone")
                    replacement.Name = name
                    replacement.CFrame = localFrame
                    replacement:SetAttribute("Game1RecoveredFromFBXRestPose", true)
                    replacement.Parent = parent
                    present[name] = replacement
                    table.insert(restored, name)
                    advanced = true
                end
                remaining[name] = nil
            end
        end
        if not advanced then break end
    end
    -- Other roots/branches cannot be reconstructed safely without a surviving
    -- imported parent. Leave them missing and let the existing validator show
    -- a warning. In particular, do NOT use fake world coordinates for house.
    for name in remaining do
        table.insert(problems, name .. ": imported parent bone unavailable; cannot restore exactly")
    end
    table.sort(restored)
    table.sort(problems)
    return restored, problems
end

return table.freeze(Recovery)
