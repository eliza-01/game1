-- Restore source-FBX mesh centres after independent Model Asset import.
-- One authored house coordinate frame; never apply hand-tuned part offsets.
-- Legacy manifests without placement data are left untouched.
local Placement = {}

local function triple(value: any, label: string): Vector3
    if typeof(value) ~= "table" or #value ~= 3 then
        error("Real Estate " .. label .. ": expected three numeric coordinates")
    end
    local components = {}
    for i = 1, 3 do
        local number = value[i]
        if typeof(number) ~= "number" or number ~= number or math.abs(number) == math.huge then
            error("Real Estate " .. label .. ": invalid numeric coordinate")
        end
        components[i] = number
    end
    return Vector3.new(components[1], components[2], components[3])
end

local function frame(raw: any, label: string): (Vector3, Vector3)
    if typeof(raw) ~= "table" or (raw.version ~= 1 and raw.version ~= 2) then
        error("Real Estate " .. label .. ": unsupported authored placement contract")
    end
    local center = triple(raw.centerInHouse, label .. " center")
    -- M184 v1 assumed (x,z,-y). Our actual FBX -> Roblox asset convention
    -- is (-x,z,y). Convert stored v1 offsets without rewriting SQLite.
    if raw.version == 1 then
        center = Vector3.new(-center.X, center.Y, -center.Z)
    end
    local size = triple(raw.size, label .. " size")
    if size.X <= 0 or size.Y <= 0 or size.Z <= 0 then
        error("Real Estate " .. label .. ": invalid authored size")
    end
    return center, size
end

local function close(a: number, b: number, tolerance: number): boolean
    return math.abs(a - b) <= tolerance
end

function Placement.Align(rig: Model, mesh: MeshPart, house: MeshPart,
    authored: any, authoredHouse: any, part: string): boolean
    -- Old houses and standalone mesh revisions cannot be assigned guessed
    -- transforms. Their existing placement behaviour is deliberately retained.
    if authored == nil or authoredHouse == nil then
        return false
    end
    local center, size = frame(authored, part)
    local _, houseSize = frame(authoredHouse, "house")
    local ratio = house.Size.X / houseSize.X
    if ratio <= 0 or not close(house.Size.Y / houseSize.Y, ratio, ratio * 0.04)
        or not close(house.Size.Z / houseSize.Z, ratio, ratio * 0.04) then
        error("Real Estate " .. part .. ": published house dimensions differ from FBX proportions; refusing placement")
    end
    local tolerance = math.max(0.04, ratio * 0.04)
    if not close(mesh.Size.X, size.X * ratio, tolerance * size.X)
        or not close(mesh.Size.Y, size.Y * ratio, tolerance * size.Y)
        or not close(mesh.Size.Z, size.Z * ratio, tolerance * size.Z) then
        error("Real Estate " .. part .. ": published mesh dimensions differ from authored FBX; refusing placement")
    end
    local targetPosition = house.CFrame:PointToWorldSpace(center * ratio)
    local delta = targetPosition - mesh.Position
    local placementMode = "already-aligned"
    if delta.Magnitude > 0.025 then
        -- The Roblox FBX importer may shift a skinned MeshPart origin while
        -- retaining the correct world rest frame of its root Bone. Moving the
        -- entire rig would then move an already-correct hinge and sockets.
        -- Instead rebase the mesh origin and its direct root attachments so
        -- bone world-rest frames remain unchanged, including all child sockets.
        local roots = {}
        local boneCount = 0
        for _, descendant in rig:GetDescendants() do
            if descendant:IsA("Bone") then
                boneCount += 1
            elseif descendant:IsA("BasePart") and descendant ~= mesh then
                error("Real Estate " .. part .. ": cannot rebase a multi-part skinned rig")
            end
        end
        for _, child in mesh:GetChildren() do
            if child:IsA("Attachment") then
                table.insert(roots, {attachment = child, world = child.WorldCFrame})
            end
        end
        if boneCount > 0 then
            placementMode = "skinned-root-rebase"
            if #roots == 0 then
                error("Real Estate " .. part .. ": skinned mesh has no root attachments to rebase")
            end
            local oldMesh = mesh.CFrame
            mesh.CFrame = CFrame.new(delta) * oldMesh
            for _, entry in roots do
                entry.attachment.CFrame = mesh.CFrame:ToObjectSpace(entry.world)
            end
            for _, entry in roots do
                if (entry.attachment.WorldCFrame.Position - entry.world.Position).Magnitude > 0.001
                    or (entry.attachment.WorldCFrame.LookVector - entry.world.LookVector).Magnitude > 0.001
                    or (entry.attachment.WorldCFrame.UpVector - entry.world.UpVector).Magnitude > 0.001 then
                    error("Real Estate " .. part .. ": root attachment moved during mesh origin recovery")
                end
            end
        else
            placementMode = "static-model-pivot"
            -- Static parts have no bone rest frames to protect.
            rig:PivotTo(CFrame.new(delta) * rig:GetPivot())
        end
    end
    if (mesh.Position - targetPosition).Magnitude > 0.025 then
        error("Real Estate " .. part .. ": authored mesh position not restored")
    end
    -- Visible in the existing Studio house diagnostic without extra scripts.
    rig:SetAttribute("Game1AuthoredPlacementMode", placementMode)
    rig:SetAttribute("Game1AuthoredPlacementDelta", delta)
    rig:SetAttribute("Game1AuthoredPlacementVersion", authored.version)
    return true
end

return table.freeze(Placement)
