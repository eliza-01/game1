--!strict
-- One canonical published-Location mounting path for stationary House props.
-- Keeps the authored carrier pivot, per-MeshPart appearance, and internal Bones.
local AssetService = game:GetService("AssetService")
local InsertService = game:GetService("InsertService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local World = Shared:WaitForChild("world")
local Registry = require(World:WaitForChild("LocationAssetRegistry"))
local SpawnOrientation = require(World:WaitForChild("HouseSpawnOrientation"))
local BoneModelMount = require(Shared:WaitForChild("rig"):WaitForChild("BoneModelMount"))
local Visuals = require(script.Parent:WaitForChild("EnvironmentAssetVisuals"))

local Mount = {}
local prototypes: {[string]: Model} = {}
local allowed = table.freeze({firewood_01 = true, embers_01 = true, cooking_pot_01 = true})

local function canonicalModel(loaded: Model): Model
    -- InsertService/AssetService may wrap the FBX model inside an importer Model.
    local children = loaded:GetChildren()
    if #children == 1 and children[1]:IsA("Model") then
        local imported = children[1] :: Model
        imported.Parent = nil
        loaded:Destroy()
        return imported
    end
    return loaded
end

local function prepare(model: Model, definition: any): boolean
    local carrier: MeshPart? = nil
    local onlyVisual: MeshPart? = nil
    local visualCount = 0
    for _, instance in ipairs(model:GetDescendants()) do
        if instance:IsA("Script") or instance:IsA("LocalScript")
            or instance:IsA("ModuleScript") or instance:IsA("AnimationController")
            or instance:IsA("Animator") or instance:IsA("ParticleEmitter")
            or instance:IsA("Fire") or instance:IsA("Smoke") or instance:IsA("Sparkles") then
            instance:Destroy()
        elseif instance:IsA("BasePart") and (instance.Name == "col_mesh"
            or instance.Name:sub(1, 4) == "COL_") then
            -- These published collision bodies are not fireplace visuals.
            -- The decorative mount has no physics and must not display them.
            instance:Destroy()
        elseif instance:IsA("MeshPart") then
            if instance.Name == "rig_carrier" then
                carrier = instance
            else
                visualCount += 1
                onlyVisual = instance
            end
        end
    end
    -- Exact authored pivot. Never use the arbitrary Roblox importer wrapper
    -- pivot or a guessed bounding-box center for a skinned asset.
    if carrier then
        model.PrimaryPart = carrier
    elseif visualCount == 1 and onlyVisual then
        model.PrimaryPart = onlyVisual
    else
        warn("[game1][fireplace] no unambiguous authored pivot in " .. model.Name)
        return false
    end
    for _, part in ipairs(model:GetDescendants()) do
        if part:IsA("BasePart") then
            part.Anchored = true
            part.CanCollide = false
            part.CanQuery = false
            part.CanTouch = false
            part.Massless = true
            if part.Name == "rig_carrier" or part.Name == "RootPart" then
                part.Transparency = 1
                part.CastShadow = false
            end
        end
    end
    Visuals.ApplyModel(model, definition)
    return true
end

local function prototype(slug: string): Model?
    local cached = prototypes[slug]
    if cached then return cached end
    if not allowed[slug] then return nil end
    local definition = Registry.assets[slug]
    if type(definition) ~= "table" or definition.status ~= "PUBLISHED" then return nil end
    local assetId = tonumber(definition.modelAssetId)
    if not assetId or assetId <= 0 then return nil end
    local ok, loaded = pcall(InsertService.LoadAsset, InsertService, assetId)
    if not ok or not loaded then
        ok, loaded = pcall(AssetService.LoadAssetAsync, AssetService, assetId)
    end
    if not ok or not loaded or not loaded:IsA("Model") then
        warn(("[game1][fireplace] published model %s (%s) unavailable: %s")
            :format(slug, tostring(assetId), tostring(loaded)))
        return nil
    end
    local model = canonicalModel(loaded :: Model)
    model.Name = slug
    if not prepare(model, definition) then
        model:Destroy()
        return nil
    end
    prototypes[slug] = model
    return model
end

function Mount.Spawn(slug: string, parent: Instance, socket: Attachment, ownerHeading: Vector3?): (Model?, Attachment?)
    local source = prototype(slug)
    if not source then return nil, nil end
    local model = source:Clone()
    model.Name = slug
    local fromBone = socket:IsA("Bone")
    local socketFrame = if fromBone then (socket :: Bone).TransformedWorldCFrame else socket.WorldCFrame
    -- Like HouseElevatorService and debug spawn: the Bone's -Y axis (TAIL
    -- -> HEAD) is the object's FRONT, while world +Y stays upright. Props
    -- get NO character clearance; the socket HEAD is their exact mount point.
    local targetFrame = SpawnOrientation.Upright(socketFrame, fromBone, 0)
    if not targetFrame and ownerHeading then
        -- Authored campfire cooking_pot_01_socket points vertically in the
        -- current FBX. It has an exact HEAD but cannot encode horizontal yaw.
        -- In this one case use the owning campfire's placed heading, keeping
        -- the HEAD position and WORLD up unchanged (never guess an offset).
        local flat = Vector3.new(ownerHeading.X, 0, ownerHeading.Z)
        if flat.Magnitude > 1e-4 then
            targetFrame = CFrame.lookAlong(socketFrame.Position, flat.Unit, Vector3.yAxis)
        end
    end
    if not targetFrame then
        warn("[game1][fireplace] no horizontal HEAD direction for " .. slug)
        model:Destroy()
        return nil, nil
    end
    -- Reuse the same grip-to-socket solver as rigid hair and weapons. Do not
    -- rely on the imported wrapper's Model pivot or its bounding-box center.
    local reference = model.PrimaryPart
    if not reference then
        model:Destroy()
        return nil, nil
    end
    local grip = BoneModelMount.CreateGrip(reference, "Game1FireplaceMountGrip", reference:GetPivot().Position)
    BoneModelMount.Place(model, grip, targetFrame)
    local actual = grip.WorldCFrame
    if (actual.Position - targetFrame.Position).Magnitude > 0.001
        or actual.LookVector:Dot(targetFrame.LookVector) < 0.99999
        or actual.UpVector:Dot(Vector3.yAxis) < 0.99999 then
        warn("[game1][fireplace] authored mount alignment failed for " .. slug)
        grip:Destroy()
        model:Destroy()
        return nil, nil
    end
    grip:Destroy()
    local innerSocket: Attachment? = nil
    if slug == "cooking_pot_01" then
        local found = model:FindFirstChild("cooking_pot_socket", true)
        if not found or not found:IsA("Attachment") then
            warn("[game1][fireplace] cooking_pot_01 missing its authored cooking_pot_socket")
            model:Destroy()
            return nil, nil
        end
        innerSocket = found
    end
    model.Parent = parent
    return model, innerSocket
end

return table.freeze(Mount)
