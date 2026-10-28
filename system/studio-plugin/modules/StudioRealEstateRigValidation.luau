-- Validate an already-published Real Estate Model Asset as actually loaded by Roblox.
-- Blender/FBX manifests are authoring expectations, not proof of what survived
-- publication. All authored bones are required, including unweighted source sockets.
local Validation = {}

local DOOR_HINGE = "door_01_hinge_socket"
local DOOR_CHILD_SOCKETS = {
    door_01_handle_inside_socket = true,
    door_01_handle_outside_socket = true,
    door_01_padlock_01_socket = true,
}

function Validation.FindMesh(root: Model, expected: string): MeshPart
    local match: MeshPart? = nil
    for _, instance in root:GetDescendants() do
        if instance:IsA("MeshPart") then
            if instance.Name:lower() ~= expected:lower() then
                error("Real Estate " .. expected .. " rig contains unexpected mesh " .. instance.Name)
            end
            if match then
                error("Real Estate rig contains duplicate mesh " .. expected)
            end
            match = instance
        end
    end
    if not match then
        error("Published Real Estate rig is missing mesh " .. expected)
    end
    return match :: MeshPart
end

function Validation.Verify(root: Model, part: string, expected: any): (MeshPart, any)
    if typeof(expected) ~= "table" then
        error("Missing registered mesh manifest for " .. part)
    end

    local mesh = Validation.FindMesh(root, part)
    local authored: {[string]: boolean} = {}
    local socketCount = 0
    for _, name in expected do
        if typeof(name) ~= "string" or name == "" or authored[name] then
            error(part .. ": invalid registered bone manifest")
        end
        authored[name] = true
        if name:sub(-7) == "_socket" then
            socketCount += 1
        end
    end

    local imported: {[string]: Bone} = {}
    local boneNames = {}
    local boneCount = 0
    for _, instance in root:GetDescendants() do
        if instance:IsA("Bone") then
            boneCount += 1
            table.insert(boneNames, instance.Name)
        end
        if instance:IsA("Bone") and authored[instance.Name] then
            if not instance:IsDescendantOf(mesh) then
                error(part .. ": bone outside expected mesh " .. instance.Name)
            end
            if imported[instance.Name] then
                error(part .. ": duplicate imported marker " .. instance.Name)
            end
            imported[instance.Name] = instance
        end
    end
    table.sort(boneNames)
    local missing = {}
    for name in authored do
        if not imported[name] then
            table.insert(missing, name)
        end
    end
    table.sort(missing)

    if #missing > 0 then
        error(part .. ": published Model Asset lost authored Bones: " .. table.concat(missing, ", ")
            .. "; republish the model before Studio Sync")
    end
    local warnings = {}
    -- Hinge is structural: without the imported Bone, PivotTo would use a
    -- fabricated origin. Never replace a working template in that situation.
    if part == "door" and authored[DOOR_HINGE] then
        local hinge = imported[DOOR_HINGE]
        if not hinge or not hinge:IsA("Bone") then
            error("door: required hinge Bone " .. DOOR_HINGE
                .. " is absent in the published Roblox Model Asset (imported Bones: "
                .. table.concat(boneNames, ", ") .. ")")
        end
        if not hinge:IsDescendantOf(mesh) then
            error("door hinge must be a descendant of the door MeshPart")
        end
        if hinge.Parent and hinge.Parent:IsA("Bone") then
            error("door hinge must be a root bone")
        end
        for name in DOOR_CHILD_SOCKETS do
            local socket = imported[name]
            if authored[name] and socket and socket.Parent ~= hinge then
                error("door socket " .. name .. " must be a child of " .. DOOR_HINGE)
            end
        end
    elseif part == "door" then
        table.insert(warnings, "door: no authored hinge pivot; DoorAssembly not created")
    end

    return mesh, {
        boneCount = boneCount,
        socketCount = socketCount,
        missingSockets = missing,
        warnings = warnings,
    }
end

return table.freeze(Validation)
