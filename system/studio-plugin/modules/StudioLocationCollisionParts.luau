-- M343C: collision geometry from the saved Location Asset Blueprint.
-- Authored Parts can be selected anywhere. Only GENERATED Parts are owned here;
-- never delete hand-made Parts or mutate the original Blender/Roblox pivot.
local Collision = {}

local OWNED = "Game1LocationCollisionOwned"
local PART_ID = "Game1LocationCollisionPartId"
local REVISION = "Game1LocationCollisionRevision"
local SHA = "Game1LocationCollisionSha256"

local function recipes(blueprint: any): {any}
    if type(blueprint) ~= "table" or blueprint.schemaVersion ~= 1
        or blueprint.pivot ~= "Model:GetPivot()" or type(blueprint.parts) ~= "table"
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

-- Model:ScaleTo() preserves an authored pivot but scales offsets/sizes.
-- Capture is unscaled; each placed instance may have its own uniform Model scale.
local function frameFor(root: Model, recipe: any): CFrame
    local localFrame = CFrame.new(table.unpack(recipe.localCFrame))
    return root:GetPivot() * CFrame.new(localFrame.Position * root:GetScale()) * localFrame.Rotation
end

local function sizeFor(root: Model, recipe: any): Vector3
    return Vector3.new(table.unpack(recipe.size)) * root:GetScale()
end

local function ownedParts(root: Model): {BasePart}
    local result = {}
    for _, child in ipairs(root:GetChildren()) do
        if child:GetAttribute(OWNED) == true then
            if not child:IsA("BasePart") or child:IsA("MeshPart") then
                error("Managed collision marker on non-primitive child; refusing mutation")
            end
            table.insert(result, child)
        end
    end
    return result
end

function Collision.IsOwned(part: Instance): boolean
    return part:GetAttribute(OWNED) == true
end

function Collision.Current(root: Model, blueprint: any, revision: any, sha: any): boolean
    if type(revision) ~= "number" or revision < 1 then return true end
    if root:GetAttribute(REVISION) ~= revision or root:GetAttribute(SHA) ~= sha then return false end
    local actual = ownedParts(root)
    if type(blueprint) ~= "table" or type(blueprint.parts) ~= "table"
        or #actual ~= #blueprint.parts then return false end
    local byId = {}
    for _, part in ipairs(actual) do
        local partId = part:GetAttribute(PART_ID)
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
        local expected = frameFor(root, recipe)
        if (part.Size - sizeFor(root, recipe)).Magnitude > 0.002
            or (part.Position - expected.Position).Magnitude > 0.003
            or part.CFrame.LookVector:Dot(expected.LookVector) < 0.99999
            or part.CFrame.UpVector:Dot(expected.UpVector) < 0.99999
            or not part.Anchored or not part.CanCollide or part.Transparency ~= 1
            or not part.CanQuery or part.CanTouch ~= recipe.canTouch
            or part.CollisionGroup ~= recipe.collisionGroup then return false end
    end
    return true
end

function Collision.Prepare(root: Model, blueprint: any, revision: any, sha: any): any
    if not root:IsA("Model") or type(revision) ~= "number" or revision < 1
        or type(sha) ~= "string" or #sha ~= 64 then
        error("Invalid Location Collision publication")
    end
    local pivot = root:GetPivot()
    local stage = {}
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
            part:SetAttribute(OWNED, true)
            part:SetAttribute(PART_ID, recipe.id)
            part.Size = sizeFor(root, recipe)
            part.CFrame = frameFor(root, recipe)
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
    return {root = root, pivot = pivot, stage = stage,
        prior = ownedParts(root), revision = revision, sha = sha,
        oldRevision = root:GetAttribute(REVISION), oldSha = root:GetAttribute(SHA), committed = false}
end

function Collision.Commit(transaction: any)
    local root = transaction.root
    if root:GetPivot() ~= transaction.pivot then error("Location pivot changed before collision commit") end
    for _, part in ipairs(transaction.prior) do part.Parent = nil end
    -- Mark committed before mutation so rollback can restore a partial commit.
    transaction.committed = true
    for _, part in ipairs(transaction.stage) do part.Parent = root end
    root:SetAttribute(REVISION, transaction.revision)
    root:SetAttribute(SHA, transaction.sha)
    if root:GetPivot() ~= transaction.pivot then error("Collision Parts changed the authored Pivot") end
end

function Collision.Rollback(transaction: any)
    for _, part in ipairs(transaction.stage) do part:Destroy() end
    if transaction.committed then
        for _, part in ipairs(transaction.prior) do part.Parent = transaction.root end
        transaction.root:SetAttribute(REVISION, transaction.oldRevision)
        transaction.root:SetAttribute(SHA, transaction.oldSha)
    end
end

function Collision.Finalize(transaction: any)
    for _, part in ipairs(transaction.prior) do part:Destroy() end
end

return table.freeze(Collision)
