-- Studio assembly for any number of independent Real Estate MeshPart rigs.
-- This adapter validates the complete template before touching ServerStorage.
local HttpService = game:GetService("HttpService")
local StudioRealEstateAppearance = require(script.Parent.StudioRealEstateAppearance)
local StudioRealEstateRigValidation = require(script.Parent.StudioRealEstateRigValidation)
local StudioRealEstateCollisionPolicy = require(script.Parent.StudioRealEstateCollisionPolicy)
local RetiredCleanup = require(script.Parent.StudioRetiredColMeshCleanup)
local StudioRealEstatePlacedVisualSync = require(script.Parent.StudioRealEstatePlacedVisualSync)
local PlacedTargets = require(script.Parent.StudioRealEstatePlacedTargets)
local HouseFrame = require(script.Parent.StudioRealEstateHouseFrame)
local PartPlacement = require(script.Parent.StudioRealEstatePartPlacement)
local SkinConnection = require(script.Parent.StudioSkinnedMeshConnection)
local StudioRealEstateModel = {}

-- Every authored bone must survive publication before a template is replaced.
local DOOR_HINGE = "door_01_hinge_socket"

local function loadIndependentRig(assetService: any, assetId: number, part: string): Model
    local lastError = ""
    for _ = 1, 8 do
        local ok, loaded = pcall(function()
            return assetService:LoadAssetAsync(assetId)
        end)
        if ok and loaded ~= nil then
            if loaded:IsA("Model") then
                return loaded
            end
            local container = Instance.new("Model")
            loaded.Parent = container
            return container
        end
        lastError = tostring(loaded)
        task.wait(2)
    end
    error("Real Estate " .. part .. " Model Asset ID " .. tostring(assetId)
        .. " could not be loaded: " .. lastError)
end

local function orderedParts(manifests: any, primary: string): {string}
    if primary ~= "rig_carrier" or typeof(manifests) ~= "table" then
        error("Real Estate v4 requires an independent rig_carrier Model Asset")
    end
    local result = {}
    for part, manifest in manifests do
        if typeof(part) ~= "string" or typeof(manifest) ~= "table" then
            error("Invalid Real Estate mesh manifest")
        end
        table.insert(result, part)
    end
    table.sort(result, function(a, b)
        return a:lower() < b:lower()
    end)
    return result
end

-- Texture-only refresh for managed Estate copies already placed in Workspace.
-- Never replace models or touch pivots/part transforms during atlas selection.
local function setGlassAppearance(mesh: MeshPart, enabled: boolean)
    if enabled then
        mesh.Transparency = 0.02
        mesh:SetAttribute('Game1RealEstateGlassApplied', true)
    elseif mesh:GetAttribute('Game1RealEstateGlassApplied') == true then
        mesh.Transparency = 0
        mesh:SetAttribute('Game1RealEstateGlassApplied', nil)
    end
end

local function refreshPlaced(slug: string, imageAssets: {[string]: string}, imageAlpha: {[string]: any}, meshOptions: any, placedTargets: {Model}): (number,number)
    local changed = 0
    local found = 0
    for _, instance in placedTargets do
        found += 1
        local applied = false
        for _, child in instance:GetDescendants() do
            if child:IsA("MeshPart") then
                local part = child.Name
                local settings = meshOptions[part] or meshOptions[string.lower(part)]
                if typeof(settings) == "table" then
                    StudioRealEstateAppearance.Apply(child, settings,
                        imageAssets[part] or imageAssets[string.lower(part)],
                        imageAlpha[part] or imageAlpha[string.lower(part)])
                    setGlassAppearance(child, settings.glass == true)
                    StudioRealEstateCollisionPolicy.Apply(child, part, settings)
                    applied = true
                end
            end
        end
        if applied then
            instance:SetAttribute("Game1TextureAssetIds", HttpService:JSONEncode(imageAssets))
            changed += 1
        end
    end
    return changed, found
end

function StudioRealEstateModel.Place(imported: Model, destination: Instance, slug: string,
    assetId: number, metadata: any, assetService: any): (Model, any)
    if slug == "" or slug == "." or slug == ".." or slug:find("[/\\]") then
        error("Invalid Real Estate slug")
    end
    local manifests = metadata.expectedMeshes
    local primary = tostring(metadata.primaryPart or "")
    local parts = orderedParts(manifests, primary)
    local rigIds = metadata.rigAssetIds
    if typeof(rigIds) ~= "table" or tonumber(rigIds[primary]) ~= assetId then
        error("Studio Sync requires published Model Asset IDs for every Real Estate mesh")
    end
    local authoredPlacements = typeof(metadata.authoredPlacements) == "table" and metadata.authoredPlacements or {}
    local meshOptions = typeof(metadata.meshOptions) == 'table' and metadata.meshOptions or {}
    local movingParts = typeof(metadata.doorParts) == "table" and metadata.doorParts or {}
    local imageAssets = {}
    local imageAlpha = {}
    for _, entry in metadata.textures or {} do
        local part = tostring(entry.slot or "")
        local id = tonumber(entry.assetId)
        if id and id > 0 and manifests[part] ~= nil then
            imageAssets[part] = tostring(math.floor(id))
            imageAlpha[part] = entry.usesAlpha
        end
    end
    local seenModels = {}
    for _, part in parts do
        local id = tonumber(rigIds[part])
        if not id or id <= 0 or id == assetId or seenModels[id] then
            error("Real Estate " .. part .. " requires a published Model Asset")
        end
        local settings = meshOptions[part]
        if typeof(settings) ~= "table" or (settings.appearanceMode ~= "material" and not imageAssets[part]) then
            error("Real Estate " .. part .. " requires an Image Asset in atlas mode")
        end
        seenModels[id] = true
    end
    local previous = destination:FindFirstChild(slug)
    if previous and (not previous:IsA("Model") or previous:GetAttribute("Game1RealEstateTemplate") ~= true) then
        error("refusing to overwrite unmanaged Real Estate instance: " .. slug)
    end

    -- Stage and verify ALL meshes before changing the existing template.
    local staged = {}
    local meshes = {}
    local bones = 0
    local rigWarnings = {}
    local missingSockets = {}
    local socketCount = 0
    local placementsRestored = 0
    local textureCount = 0
    local activePart = primary
    local newStandard = tonumber(metadata.houseAuthoringVersion) == 4
    if not newStandard then
        error("Real Estate requires the independent house_armature/rig_carrier v4 publication. Republish this house.")
    end
    local authoredOrigin: CFrame? = nil
    local rootCarrier: MeshPart? = nil
    local ok, problem = pcall(function()
        local carrierInspection
        rootCarrier, carrierInspection = StudioRealEstateRigValidation.Verify(
            imported, "rig_carrier", metadata.expectedCarrierBones, false)
        rootCarrier:SetAttribute("Game1HouseRigCarrier", true)
        rootCarrier.Transparency = 1
        rootCarrier.CastShadow = false
        rootCarrier.CanCollide = false
        rootCarrier.CanTouch = false
        rootCarrier.CanQuery = false
        rootCarrier.Massless = true
        rootCarrier.TextureID = ""
        for _, child in rootCarrier:GetChildren() do
            if child:IsA("SurfaceAppearance") then child:Destroy() end
        end
        authoredOrigin = rootCarrier:GetPivot()
        bones += carrierInspection.boneCount
        socketCount += carrierInspection.socketCount
        for _, part in parts do
            activePart = part
            local rig = loadIndependentRig(assetService, tonumber(rigIds[part]) :: number, part)
            table.insert(staged, {part = part, rig = rig})
            local mesh, inspection = StudioRealEstateRigValidation.Verify(
                rig, part, manifests[part], false)
            meshes[part] = mesh
            PartPlacement.AlignSharedPivot(rig, mesh, authoredOrigin, part)
            bones += inspection.boneCount
            socketCount += inspection.socketCount
            for _, name in inspection.missingSockets do
                table.insert(missingSockets, part .. "/" .. name)
            end
            for _, warning in inspection.warnings do
                table.insert(rigWarnings, warning)
            end
        end
    end)
    if not ok then
        for _, entry in staged do
            if entry.rig ~= imported then
                entry.rig:Destroy()
            end
        end
        local detail = tostring(problem)
        error("Real Estate " .. activePart .. " Model Asset " .. tostring(rigIds[activePart])
            .. ": " .. detail, 0)
    end

    table.sort(missingSockets)
    if not rootCarrier or not authoredOrigin then
        error("Real Estate publication has no validated original house_armature pivot")
    end
    local wrapper = Instance.new("Model")
    wrapper.Name = slug
    local static = Instance.new("Model")
    static.Name = "StaticAssembly"
    static:SetAttribute("Game1RealEstateManagedRig", true)
    static.Parent = wrapper
    wrapper.WorldPivot = authoredOrigin
    wrapper:SetAttribute("Game1HousePivotMode", "authored-rig-carrier")
    -- The carrier is imported from its own Model Asset, never from a visual FBX.
    rootCarrier.Parent = static
    imported:Destroy()
    local assembly: Model? = nil
    local staticParts = {}
    for _, entry in staged do
        local part = entry.part
        local rigName = part:sub(1, 1):upper() .. part:sub(2) .. "Rig"
        entry.rig.Name = rigName
        entry.rig:SetAttribute("Game1RealEstateManagedRig", true)
        -- DoorAssembly is the only moving unit. Do not edit Bone.Transform:
        -- the hinge Bone identifies the world-space pivot for Model:PivotTo().
        local moving = movingParts[part] == true or (part == "door" and meshes[part]:FindFirstChild(DOOR_HINGE,true) ~= nil)
        if moving then
            local hinge = meshes[part]:FindFirstChild(DOOR_HINGE,true)
            if not hinge or not hinge:IsA("Bone") then
                wrapper:Destroy()
                error(part .. ": moving mesh lost its authored hinge bone")
            end
            if not assembly then
                assembly = Instance.new("Model")
                assembly.Name = "DoorAssembly"
                assembly:SetAttribute("Game1RealEstateManagedRig", true)
                assembly.WorldPivot = hinge.TransformedWorldCFrame
                assembly.Parent = wrapper
                assembly:SetAttribute("Game1DoorHingeSocket",DOOR_HINGE)
                assembly:SetAttribute("Game1DoorPivotMode","rigid_model")
                local housePivot = authoredOrigin
                local localPivot = housePivot:ToObjectSpace(assembly:GetPivot())
                assembly:SetAttribute("Game1DoorClosedLocalPivot",
                    HttpService:JSONEncode({localPivot:GetComponents()}))
            end
            entry.rig.Parent = assembly
        else
            -- Flatten only static publication Parts into their common Model.
            -- This lets the EXISTING shared SkinnedMeshConnection enforce
            -- direct assembly ownership, without changing Characters/Location.
            for _, descendant in entry.rig:GetDescendants() do
                if descendant:IsA("BasePart") then descendant.Parent = static end
            end
            for _, descendant in entry.rig:GetDescendants() do
                if descendant:IsA("JointInstance") or descendant:IsA("WeldConstraint") then
                    descendant.Parent = static
                end
            end
            entry.rig:Destroy()
            table.insert(staticParts, meshes[part])
        end
        local settings = meshOptions[part]
        StudioRealEstateAppearance.Apply(meshes[part], settings, imageAssets[part], imageAlpha[part])
        setGlassAppearance(meshes[part], typeof(settings) == 'table' and settings.glass == true)
        if settings.appearanceMode ~= "material" then textureCount += 1 end
        StudioRealEstateCollisionPolicy.Apply(meshes[part], part, settings)
    end
    -- Canonical technical carrier is the only root. Static meshes are
    -- physically linked as in Characters/Location Assets; no visual part
    -- decides the house origin or receives hand-tuned geometry offsets.
    static.PrimaryPart = rootCarrier
    for _, mesh in staticParts do
        if mesh ~= rootCarrier then
            SkinConnection.Connect(static, rootCarrier, mesh, "HouseStaticSkinWeld")
        end
    end
    wrapper.PrimaryPart = rootCarrier
    if not PartPlacement.SamePivot(wrapper:GetPivot(), authoredOrigin) then
        wrapper:Destroy()
        error("Real Estate original pivot changed during shared assembly")
    end
    -- Align the new complete assembly to the previously registered house
    -- origin before swapping templates. A changed house geometry centre must
    -- not move the entire estate relative to existing placed copies.
    wrapper:SetAttribute("Game1RealEstateSocketContractComplete", #missingSockets == 0)
    wrapper:SetAttribute("Game1MissingRealEstateSockets", HttpService:JSONEncode(missingSockets))
    wrapper:SetAttribute("Game1RealEstateTemplate", true)
    wrapper:SetAttribute("Game1ModelAssetId", tostring(assetId))
    wrapper:SetAttribute("Game1HouseModelAssetId", tostring(assetId))
    if rigIds.door then
        wrapper:SetAttribute("Game1DoorModelAssetId", tostring(rigIds.door))
    end
    wrapper:SetAttribute("Game1PrimaryRigPart", primary)
    wrapper:SetAttribute("Game1RigAssetIds", HttpService:JSONEncode(rigIds))
    wrapper:SetAttribute("Game1TextureAssetIds", HttpService:JSONEncode(imageAssets))
    wrapper:SetAttribute("Game1RealEstateSlug", slug)
    wrapper:SetAttribute("Game1HouseLevel", tonumber(metadata.houseLevel) or 1)
    wrapper:SetAttribute("Game1PurchasePrice", tonumber(metadata.purchasePrice) or 1)
    wrapper:SetAttribute("Game1MinimumLevel", tonumber(metadata.minLevel) or 1)
    wrapper:SetAttribute("Game1SalePrice", tonumber(metadata.salePrice) or 1)
    wrapper.Parent = destination
    if previous then
        previous:Destroy()
    end
    -- Remove obsolete COL geometry from all placed managed houses at Sync.
    local placedTargets = PlacedTargets.List(slug)
    local collisionUpdated = RetiredCleanup.CleanEstate(wrapper)
    for _, root in placedTargets do
        collisionUpdated += RetiredCleanup.CleanEstate(root)
    end
    local visualUpdated, visualFound, visualWarnings = StudioRealEstatePlacedVisualSync.Update(wrapper, slug, placedTargets)
    for _, warning in visualWarnings do
        table.insert(rigWarnings, warning)
    end
    -- Apply appearance independently; visual replacement may have been skipped
    -- safely for an incomplete/unmanaged placed house.
    local textureUpdated = select(1, refreshPlaced(slug, imageAssets, imageAlpha, meshOptions, placedTargets))
    return wrapper, {bonesValidated = true, rigsValidated = #parts + 1,
        alignment = "independent-authored-rig-carrier",
        texturesApplied = textureCount, placedSyncVersion = 3, workspaceModelsUpdated = visualUpdated,
        workspaceModelsFound = visualFound,
        workspaceTextureModelsUpdated = textureUpdated,
        workspaceCollisionRigsUpdated = collisionUpdated,
        boneCount = bones, socketCount = socketCount,
        authoredPlacementsRestored = placementsRestored,
        socketContractComplete = #missingSockets == 0,
        missingSockets = missingSockets, rigWarnings = rigWarnings}
end

return table.freeze(StudioRealEstateModel)
