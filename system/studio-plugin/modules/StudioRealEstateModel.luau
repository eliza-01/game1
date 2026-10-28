-- Studio assembly for any number of independent Real Estate MeshPart rigs.
-- This adapter validates the complete template before touching ServerStorage.
local HttpService = game:GetService("HttpService")
local StudioTextureAppearance = require(script.Parent.StudioTextureAppearance)
local StudioRealEstateRigValidation = require(script.Parent.StudioRealEstateRigValidation)
local StudioRealEstateCollisionPolicy = require(script.Parent.StudioRealEstateCollisionPolicy)
local StudioRealEstatePlacedCollisionSync = require(script.Parent.StudioRealEstatePlacedCollisionSync)
local StudioRealEstatePlacedVisualSync = require(script.Parent.StudioRealEstatePlacedVisualSync)
local PlacedTargets = require(script.Parent.StudioRealEstatePlacedTargets)
local HouseFrame = require(script.Parent.StudioRealEstateHouseFrame)
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

local function orderedParts(manifests: any): {string}
    if typeof(manifests) ~= "table" or typeof(manifests.house) ~= "table" then
        error("Real Estate requires an authored house mesh and its bone manifest")
    end
    local result = {"house"}
    for part, manifest in manifests do
        if typeof(part) ~= "string" or typeof(manifest) ~= "table" then
            error("Invalid Real Estate mesh manifest")
        end
        if part ~= "house" then
            table.insert(result, part)
        end
    end
    table.sort(result, function(a, b)
        if a == "house" then return true end
        if b == "house" then return false end
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
                local part = string.lower(child.Name)
                local settings = meshOptions[part]
                if imageAssets[part] then
                    StudioTextureAppearance.Apply(child, "rbxassetid://" .. imageAssets[part], imageAlpha[part])
                    setGlassAppearance(child, typeof(settings) == 'table' and settings.glass == true)
                end
                if imageAssets[part] or StudioRealEstateCollisionPolicy.IsCollider(part) then
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
    local parts = orderedParts(manifests)
    local rigIds = metadata.rigAssetIds
    if typeof(rigIds) ~= "table" or tonumber(rigIds.house) ~= assetId then
        error("Studio Sync requires published Model Asset IDs for every Real Estate mesh")
    end
    local meshOptions = typeof(metadata.meshOptions) == 'table' and metadata.meshOptions or {}
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
        if not id or id <= 0 or seenModels[id]
            or (not StudioRealEstateCollisionPolicy.IsCollider(part) and not imageAssets[part]) then
            error("Real Estate " .. part .. " requires a published Model Asset"
                .. (StudioRealEstateCollisionPolicy.IsCollider(part) and "" or " and Image Asset"))
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
    local textureCount = 0
    local activePart = "house"
    local ok, problem = pcall(function()
        for _, part in parts do
            activePart = part
            local rig = part == "house" and imported
                or loadIndependentRig(assetService, tonumber(rigIds[part]) :: number, part)
            table.insert(staged, {part = part, rig = rig})
            local mesh, inspection = StudioRealEstateRigValidation.Verify(rig, part, manifests[part])
            meshes[part] = mesh
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
    local wrapper = Instance.new("Model")
    wrapper.Name = slug
    for _, entry in staged do
        local part = entry.part
        local rigName = part:sub(1, 1):upper() .. part:sub(2) .. "Rig"
        entry.rig.Name = rigName
        if StudioRealEstateCollisionPolicy.IsCollider(part) then
            entry.rig:SetAttribute("Game1RealEstatePhysicsRig", true)
            entry.rig:SetAttribute("Game1RealEstatePhysicsMeshName", part)
        end
        -- DoorAssembly is the only moving unit. Do not edit Bone.Transform:
        -- the hinge Bone identifies the world-space pivot for Model:PivotTo().
        if part == "door" and meshes[part]:FindFirstChild(DOOR_HINGE, true) then
            local hinge = meshes[part]:FindFirstChild(DOOR_HINGE, true) :: Bone
            local assembly = Instance.new("Model")
            assembly.Name = "DoorAssembly"
            assembly.Parent = wrapper
            entry.rig.Parent = assembly
            -- New Model has no PrimaryPart: WorldPivot sets the pivot without
            -- displacing any MeshPart or changing an authored bone pose.
            assembly.WorldPivot = hinge.TransformedWorldCFrame
            assembly:SetAttribute("Game1DoorHingeSocket", DOOR_HINGE)
            assembly:SetAttribute("Game1DoorPivotMode", "rigid_model")
            local closedLocal = meshes.house.CFrame:ToObjectSpace(assembly:GetPivot())
            assembly:SetAttribute("Game1DoorClosedLocalPivot",
                HttpService:JSONEncode({closedLocal:GetComponents()}))
        else
            entry.rig.Parent = wrapper
        end
        local settings = meshOptions[part]
        if not StudioRealEstateCollisionPolicy.IsCollider(part) then
            StudioTextureAppearance.Apply(meshes[part], "rbxassetid://" .. imageAssets[part], imageAlpha[part])
            setGlassAppearance(meshes[part], typeof(settings) == 'table' and settings.glass == true)
            textureCount += 1
        end
        StudioRealEstateCollisionPolicy.Apply(meshes[part], part, settings)
    end
    -- Align the new complete assembly to the previously registered house
    -- origin before swapping templates. A changed house geometry centre must
    -- not move the entire estate relative to existing placed copies.
    if previous then
        local previousHouse = HouseFrame.Find(previous)
        if not previousHouse then
            wrapper:Destroy()
            error("Full house sync: existing template house anchor is missing or ambiguous")
        end
        HouseFrame.Align(wrapper, meshes.house, previousHouse:GetPivot(), "full template house")
    end
    wrapper:SetAttribute("Game1RealEstateSocketContractComplete", #missingSockets == 0)
    wrapper:SetAttribute("Game1MissingRealEstateSockets", HttpService:JSONEncode(missingSockets))
    wrapper:SetAttribute("Game1RealEstateTemplate", true)
    wrapper:SetAttribute("Game1ModelAssetId", tostring(assetId))
    wrapper:SetAttribute("Game1HouseModelAssetId", tostring(assetId))
    if rigIds.door then
        wrapper:SetAttribute("Game1DoorModelAssetId", tostring(rigIds.door))
    end
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
    -- Retrofit managed physics rigs into existing placed houses, preserving
    -- their CFrame and all user-owned models / furnishings.
    local placedTargets = PlacedTargets.List(slug)
    local collisionUpdated, collisionWarnings = StudioRealEstatePlacedCollisionSync.Update(wrapper, slug, placedTargets)
    for _, warning in collisionWarnings do
        table.insert(rigWarnings, warning)
    end
    local visualUpdated, visualFound, visualWarnings = StudioRealEstatePlacedVisualSync.Update(wrapper, slug, placedTargets)
    for _, warning in visualWarnings do
        table.insert(rigWarnings, warning)
    end
    -- Apply appearance independently; visual replacement may have been skipped
    -- safely for an incomplete/unmanaged placed house.
    local textureUpdated = select(1, refreshPlaced(slug, imageAssets, imageAlpha, meshOptions, placedTargets))
    return wrapper, {bonesValidated = true, rigsValidated = #parts,
        alignment = "authored-house-pivot",
        texturesApplied = textureCount, placedSyncVersion = 2, workspaceModelsUpdated = visualUpdated,
        workspaceModelsFound = visualFound,
        workspaceTextureModelsUpdated = textureUpdated,
        workspaceCollisionRigsUpdated = collisionUpdated,
        boneCount = bones, socketCount = socketCount,
        socketContractComplete = #missingSockets == 0,
        missingSockets = missingSockets, rigWarnings = rigWarnings}
end

return table.freeze(StudioRealEstateModel)
