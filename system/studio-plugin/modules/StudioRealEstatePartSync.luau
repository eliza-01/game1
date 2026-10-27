-- Atomic, single-rig refresh of a managed Real Estate template.
-- Other rigs, their Asset IDs, and their placed transforms are never rebuilt.
local HttpService = game:GetService("HttpService")
local Validation = require(script.Parent.StudioRealEstateRigValidation)
local Recovery = require(script.Parent.StudioRealEstateSocketRecovery)
local Collision = require(script.Parent.StudioRealEstateCollisionPolicy)
local Texture = require(script.Parent.StudioTextureAppearance)

local PartSync = {}

local function rigName(part: string): string
    return part:sub(1, 1):upper() .. part:sub(2) .. "Rig"
end

local function decodeMap(value: any): any
    if typeof(value) ~= "string" then return {} end
    local ok, decoded = pcall(function() return HttpService:JSONDecode(value) end)
    return if ok and typeof(decoded) == "table" then decoded else {}
end

local function houseMesh(root: Model): MeshPart?
    for _, child in root:GetDescendants() do
        if child:IsA("MeshPart") and child.Name == "house" then
            return child
        end
    end
    return nil
end

local function existingPart(root: Model, part: string): Model?
    local name = if part == "door" and root:FindFirstChild("DoorAssembly")
        then "DoorAssembly" else rigName(part)
    local child = root:FindFirstChild(name)
    if child ~= nil and not child:IsA("Model") then
        error("refusing to replace a non-Model part " .. name)
    end
    return child :: Model?
end

local function applyGlass(mesh: MeshPart, enabled: boolean)
    if enabled then
        mesh.Transparency = 0.02
        mesh:SetAttribute("Game1RealEstateGlassApplied", true)
    end
end

function PartSync.Place(imported: Model, destination: Instance, slug: string,
    assetId: number, metadata: any): (Model, any)
    local part = tostring(metadata.syncPart or "")
    local manifests = metadata.expectedMeshes
    local rigs = metadata.rigAssetIds
    if typeof(manifests) ~= "table" or typeof(rigs) ~= "table"
        or typeof(manifests[part]) ~= "table" or tonumber(rigs[part]) ~= assetId then
        error("targeted Real Estate Sync requires a registered mesh and its published Model Asset")
    end
    local template = destination:FindFirstChild(slug)
    if not template or not template:IsA("Model")
        or template:GetAttribute("Game1RealEstateTemplate") ~= true then
        error("No managed Real Estate template exists; run full Sync Studio first")
    end
    local wrapper = template :: Model
    local old = existingPart(wrapper, part)
    if not old then
        error("Targeted rig " .. part .. " not found in template; run full Sync Studio first")
    end
    local candidate = Validation.FindMesh(imported, part)
    local recovered = {}
    if typeof(metadata.authoredBones) == "table" and metadata.authoredBones[part] then
        recovered = select(1, Recovery.Restore(candidate, metadata.authoredBones[part]))
    end
    local mesh, check = Validation.Verify(imported, part, manifests[part])
    local imageId, usesAlpha = nil, nil
    for _, entry in metadata.textures or {} do
        if tostring(entry.slot) == part then
            imageId = tonumber(entry.assetId)
            usesAlpha = entry.usesAlpha
        end
    end
    if not Collision.IsCollider(part) and (not imageId or imageId <= 0) then
        error("Targeted Real Estate rig " .. part .. " has no published Image Asset")
    end
    local settings = (typeof(metadata.meshOptions) == "table" and metadata.meshOptions[part]) or {}
    if imageId then
        Texture.Apply(mesh, "rbxassetid://" .. tostring(math.floor(imageId)), usesAlpha)
        applyGlass(mesh, typeof(settings) == "table" and settings.glass == true)
    end
    Collision.Apply(mesh, part, settings)
    local replacement: Model = imported
    imported.Name = rigName(part)
    if Collision.IsCollider(part) then
        imported:SetAttribute("Game1RealEstatePhysicsRig", true)
        imported:SetAttribute("Game1RealEstatePhysicsMeshName", part)
    end
    imported:SetAttribute("Game1RealEstateManagedPart", part)
    if part == "door" then
        local hinge = mesh:FindFirstChild("door_01_hinge_socket", true)
        if hinge and hinge:IsA("Bone") then
            local assembly = Instance.new("Model")
            assembly.Name = "DoorAssembly"
            imported.Parent = assembly
            assembly.WorldPivot = hinge.TransformedWorldCFrame
            assembly:SetAttribute("Game1DoorHingeSocket", "door_01_hinge_socket")
            assembly:SetAttribute("Game1DoorPivotMode", "rigid_model")
            local anchor = houseMesh(wrapper)
            if not anchor then error("house anchor missing; target rig not replaced") end
            local localPivot = anchor.CFrame:ToObjectSpace(assembly:GetPivot())
            assembly:SetAttribute("Game1DoorClosedLocalPivot", HttpService:JSONEncode({localPivot:GetComponents()}))
            replacement = assembly
        end
    end
    -- Validate and prepare before replacing anything; name collision is
    -- transient only after the staged assembly is accepted.
    local oldName = old.Name
    local stagedName = oldName .. "_m140_old"
    if wrapper:FindFirstChild(stagedName) then
        error("Unresolved previous targeted sync staging: " .. stagedName)
    end
    old.Name = stagedName
    local ok, problem = pcall(function()
        replacement.Name = oldName
        replacement.Parent = wrapper
    end)
    if not ok then
        old.Name = oldName
        replacement:Destroy()
        error("Real Estate targeted rig swap failed: " .. tostring(problem))
    end
    old:Destroy()
    local savedIds = decodeMap(wrapper:GetAttribute("Game1RigAssetIds"))
    savedIds[part] = tostring(assetId)
    wrapper:SetAttribute("Game1RigAssetIds", HttpService:JSONEncode(savedIds))
    if part == "house" then
        wrapper:SetAttribute("Game1HouseModelAssetId", tostring(assetId))
        wrapper:SetAttribute("Game1ModelAssetId", tostring(assetId))
    elseif part == "door" then
        wrapper:SetAttribute("Game1DoorModelAssetId", tostring(assetId))
    end
    if imageId then
        local savedTextures = decodeMap(wrapper:GetAttribute("Game1TextureAssetIds"))
        savedTextures[part] = tostring(math.floor(imageId))
        wrapper:SetAttribute("Game1TextureAssetIds", HttpService:JSONEncode(savedTextures))
    end
    -- Only this mesh is updated on author-managed placed houses. Use the house
    -- anchor to preserve each house's existing world transform; never rebuild
    -- unrelated meshes or player-owned furniture.
    local placedCount = 0
    local warnings = {}
    local referenceHouse = houseMesh(wrapper)
    if referenceHouse then
        for _, root in workspace:GetDescendants() do
            if root:IsA("Model") and root:GetAttribute("Game1RealEstateSlug") == slug
                and root:GetAttribute("Game1RealEstateTemplate") ~= true then
                local placed = houseMesh(root)
                local placedOld = existingPart(root, part)
                if placed and placedOld then
                    local transform = placed.CFrame * referenceHouse.CFrame:Inverse()
                    local cloned: Model? = nil
                    local success, cause = pcall(function()
                        local staged = replacement:Clone()
                        cloned = staged
                        staged:PivotTo(transform * replacement:GetPivot())
                        staged.Name = placedOld.Name
                        staged.Parent = root
                    end)
                    if success then
                        placedOld:Destroy()
                        placedCount += 1
                    else
                        if cloned then cloned:Destroy() end
                        table.insert(warnings, root:GetFullName() .. ": " .. tostring(cause))
                    end
                else
                    table.insert(warnings, root:GetFullName() .. ": part or house anchor not managed")
                end
            end
        end
    end
    return wrapper, {bonesValidated = true, rigsValidated = 1,
        texturesApplied = if imageId then 1 else 0,
        partialSync = true, part = part, workspaceModelsUpdated = placedCount,
        boneCount = check.boneCount, recoveredSockets = recovered,
        missingSockets = check.missingSockets, rigWarnings = warnings}
end

return table.freeze(PartSync)
