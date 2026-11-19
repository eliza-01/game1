-- M343C: collision geometry from the saved Location Asset Blueprint.
-- Authored Parts can be selected anywhere. Only GENERATED Parts are owned here;
-- never delete hand-made Parts or mutate the original Blender/Roblox pivot.
local Transform = require(script.Parent.StudioLocationCollisionTransform)
local Collision = {}

local OWNED = "Game1LocationCollisionOwned"
local PART_ID = "Game1LocationCollisionPartId"
local REVISION = "Game1LocationCollisionRevision"
local SHA = "Game1LocationCollisionSha256"
local APPROVED = "Game1LocationCollisionApprovedSha256"
local function keys(blueprint: any)
    if type(blueprint) == "table" and blueprint.schemaVersion == 3 then
        return "Game1HouseCollisionOwned", "Game1HouseCollisionPartId",
            "Game1HouseCollisionRevision", "Game1HouseCollisionSha256",
            "Game1HouseCollisionApprovedSha256"
    end
    return OWNED, PART_ID, REVISION, SHA, APPROVED
end

local function recipes(blueprint: any): {any}
    if type(blueprint) ~= "table" or (blueprint.schemaVersion ~= 2 and blueprint.schemaVersion ~= 3)
        or blueprint.pivot ~= "Model:GetPivot()"
        or (blueprint.schemaVersion == 2 and type(blueprint.anchor) ~= "table")
        or type(blueprint.parts) ~= "table"
        or #blueprint.parts < 1 or #blueprint.parts > 256 then
        error("Invalid Location Collision Blueprint; no Parts changed")
    end
    local ids = {}
    for _, recipe in ipairs(blueprint.parts) do
        if type(recipe) ~= "table" or type(recipe.id) ~= "string" or ids[recipe.id]
            or not recipe.id:match("^[A-Za-z0-9][A-Za-z0-9_%-]*$")
            or type(recipe.localCFrame) ~= "table" or #recipe.localCFrame ~= 12
            or type(recipe.size) ~= "table" or #recipe.size ~= 3
            or type(recipe.collisionGroup) ~= "string"
            or type(recipe.canQuery) ~= "boolean" or type(recipe.canTouch) ~= "boolean" then
            error("Malformed Location Collision Part recipe")
        end
        if recipe.shape ~= "Block" and recipe.shape ~= "Ball" and recipe.shape ~= "Cylinder"
            and recipe.shape ~= "Wedge" and recipe.shape ~= "CornerWedge" then
            error("Location Collision Blueprint supports primitive Parts only")
        end
        if #recipe.id > 64 then error("Invalid Location Collision Part ID") end
        for _, dimension in ipairs(recipe.size) do
            if type(dimension) ~= "number" or dimension <= 0.001 or dimension > 4096 then
                error("Invalid collision Part size")
            end
        end
        for _, component in ipairs(recipe.localCFrame) do
            if type(component) ~= "number" or component ~= component
                or math.abs(component) > 100000 then error("Invalid collision CFrame") end
        end
        ids[recipe.id] = true
    end
    return blueprint.parts
end

-- Coordinate conversion is owned by StudioLocationCollisionTransform. Never
-- infer per-axis visual scale from Model:GetScale() or adjust the old Pivot.
local function ownedParts(root: Model, ownedKey: string?): {BasePart}
    local result = {}
    local attribute = ownedKey or OWNED
    for _, child in ipairs(root:GetChildren()) do
        if child:GetAttribute(attribute) == true then
            if not child:IsA("BasePart") or child:IsA("MeshPart") then
                error("Managed collision marker on non-primitive child; refusing mutation")
            end
            table.insert(result, child)
        end
    end
    return result
end

function Collision.IsOwned(part: Instance): boolean
    return part:GetAttribute(OWNED) == true or part:GetAttribute("Game1HouseCollisionOwned") == true
end

function Collision.Current(root: Model, blueprint: any, revision: any, sha: any): boolean
    if type(revision) ~= "number" or revision < 1 then return true end
    if type(blueprint) ~= "table" or (blueprint.schemaVersion ~= 2 and blueprint.schemaVersion ~= 3) then return false end
    local ownedKey, partKey, revisionKey, shaKey, approvalKey = keys(blueprint)
    if root:GetAttribute(revisionKey) ~= revision or root:GetAttribute(shaKey) ~= sha then return false end
    local resolved, anchor = pcall(Transform.Resolve, root, blueprint)
    if not resolved then return false end
    local validParts, actual = pcall(ownedParts, root, ownedKey)
    if not validParts then return false end
    if type(blueprint) ~= "table" or type(blueprint.parts) ~= "table"
        or #actual ~= #blueprint.parts then return false end
    local byId = {}
    for _, part in ipairs(actual) do
        local partId = part:GetAttribute(partKey)
        if type(partId) ~= "string" or byId[partId] then return false end
        byId[partId] = part
    end
    for _, recipe in ipairs(blueprint.parts) do
        local part = byId[recipe.id]
        if not part or not part:IsA("BasePart") or part:IsA("MeshPart") then return false end
        local expectedShape = recipe.shape
        local class = if expectedShape == "Wedge" then "WedgePart"
            elseif expectedShape == "CornerWedge" then "CornerWedgePart" else "Part"
        if part.ClassName ~= class then return false end
        if part:IsA("Part") then
            local shape = if part.Shape == Enum.PartType.Ball then "Ball"
                elseif part.Shape == Enum.PartType.Cylinder then "Cylinder" else "Block"
            if shape ~= expectedShape then return false end
        end
        -- Explicit Studio inspection may authorize a larger, visible enclosure
        -- for this exact Blueprint SHA. It does not change the default for
        -- unapproved placements or later Blueprint revisions.
        local allowed = root:GetAttribute(approvalKey) == sha
        local okGeometry, expected, expectedSize = pcall(Transform.Part, anchor, recipe, allowed)
        if not okGeometry then return false end
        if (part.Size - expectedSize).Magnitude > 0.002
            or (part.Position - expected.Position).Magnitude > 0.003
            or part.CFrame.LookVector:Dot(expected.LookVector) < 0.99999
            or part.CFrame.UpVector:Dot(expected.UpVector) < 0.99999
            or not part.Anchored or not part.CanCollide or part.Transparency ~= 1
            or not part.CanQuery or part.CanTouch ~= recipe.canTouch
            or part.CollisionGroup ~= recipe.collisionGroup then return false end
    end
    return true
end

function Collision.Prepare(root: Model, blueprint: any, revision: any, sha: any, incoming: Model?, allowExcessive: boolean?): any
    if not root:IsA("Model") or type(revision) ~= "number" or revision < 1
        or type(sha) ~= "string" or #sha ~= 64 then
        error("Invalid Location Collision publication")
    end
    local ownedKey, partKey, revisionKey, shaKey, approvalKey = keys(blueprint)
    local pivot = root:GetPivot()
    local geometry = incoming or root
    local anchor = Transform.Resolve(geometry, blueprint)
    local stage = {}
    local warnings = {}
    local good, failure = pcall(function()
        for _, recipe in ipairs(recipes(blueprint)) do
            local part: BasePart
            if recipe.shape == "Wedge" then
                part = Instance.new("WedgePart")
            elseif recipe.shape == "CornerWedge" then
                part = Instance.new("CornerWedgePart")
            else
                part = Instance.new("Part")
                if recipe.shape == "Ball" then part.Shape = Enum.PartType.Ball end
                if recipe.shape == "Cylinder" then part.Shape = Enum.PartType.Cylinder end
            end
            table.insert(stage, part)
            part.Name = "__Game1Collision_" .. recipe.id
            part:SetAttribute(ownedKey, true)
            part:SetAttribute(partKey, recipe.id)
            local frame, size, warning
            if allowExcessive == true then
                frame, size, warning = Transform.Part(anchor, recipe, true)
            else
                frame, size = Transform.Part(anchor, recipe)
            end
            if warning then table.insert(warnings, warning) end
            part.Size = size
            part.CFrame = frame
            part.Anchored = true
            part.CanCollide = true
            -- CanQuery=false has no effect when CanCollide=true in Roblox.
            part.CanQuery = true
            part.CanTouch = recipe.canTouch
            part.Transparency = 1
            part.CastShadow = false
            part.Material = Enum.Material.SmoothPlastic
            part.CollisionGroup = recipe.collisionGroup
        end
    end)
    if not good then
        for _, part in ipairs(stage) do part:Destroy() end
        error("Collision Parts staging failed: " .. tostring(failure))
    end
    return {root = root, pivot = pivot, stage = stage, warnings = warnings,
        prior = ownedParts(root, ownedKey), revision = revision, sha = sha,
        revisionKey = revisionKey, shaKey = shaKey, approvalKey = approvalKey,
        oldRevision = root:GetAttribute(revisionKey), oldSha = root:GetAttribute(shaKey),
        oldApproval = root:GetAttribute(approvalKey), committed = false}
end

function Collision.Commit(transaction: any)
    local root = transaction.root
    if root:GetPivot() ~= transaction.pivot then error("Location pivot changed before collision commit") end
    for _, part in ipairs(transaction.prior) do part.Parent = nil end
    -- Mark committed before mutation so rollback can restore a partial commit.
    transaction.committed = true
    for _, part in ipairs(transaction.stage) do part.Parent = root end
    root:SetAttribute(transaction.revisionKey, transaction.revision)
    root:SetAttribute(transaction.shaKey, transaction.sha)
    root:SetAttribute(transaction.approvalKey, if #transaction.warnings > 0 then transaction.sha else nil)
    if root:GetPivot() ~= transaction.pivot then error("Collision Parts changed the authored Pivot") end
end

function Collision.Rollback(transaction: any)
    for _, part in ipairs(transaction.stage) do part:Destroy() end
    if transaction.committed then
        for _, part in ipairs(transaction.prior) do part.Parent = transaction.root end
        transaction.root:SetAttribute(transaction.revisionKey, transaction.oldRevision)
        transaction.root:SetAttribute(transaction.shaKey, transaction.oldSha)
        transaction.root:SetAttribute(transaction.approvalKey, transaction.oldApproval)
    end
end

function Collision.Finalize(_transaction: any)
    -- Intentionally no Destroy(): Commit already detached old Parts and the
    -- Studio Undo transaction may need to re-parent them on Ctrl+Z.
end

return table.freeze(Collision)
