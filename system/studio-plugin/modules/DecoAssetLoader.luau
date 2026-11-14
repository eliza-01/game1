local StudioTextureAppearance = require(script.Parent.StudioTextureAppearance)
local MeshPhysics = require(script.Parent.StudioMeshPhysicsCore)
local RetiredCleanup = require(script.Parent.StudioRetiredColMeshCleanup)
local MeshNames = require(script.Parent.StudioLocationMeshNames)
local Carrier = require(script.Parent.StudioLocationRigCarrier)
local SkinConnection = require(script.Parent.StudioSkinnedMeshConnection)
local PublishedRigNormalize = require(script.Parent.StudioLocationPublishedRigNormalize)
local DecoAssetLoader = {}
DecoAssetLoader.__index = DecoAssetLoader

local function canonicalModel(loaded: Instance): Model
    local imported: Instance = loaded
    local children = loaded:GetChildren()
    if loaded:IsA("Model") and #children == 1 then
        imported = children[1]
        imported.Parent = nil
        loaded:Destroy()
    end
    if imported:IsA("Model") then
        return imported
    end
    local model = Instance.new("Model")
    model.Name = "ImportedDeco"
    imported.Parent = model
    return model
end

local function sanitize(model: Model)
    -- Location assets are static decoration. Animation runtime objects and the
    -- importer-generated InitialPoses cache are not part of the authored asset
    -- and make transient placement clones unnecessarily fragile. Keep Bones,
    -- because a skinned MeshPart can still need its bind skeleton for rendering.
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("Script") or descendant:IsA("LocalScript") or descendant:IsA("AnimationController") or descendant:IsA("Animator") then
            descendant:Destroy()
        elseif descendant:IsA("Folder") and descendant.Name == "InitialPoses" then
            descendant:Destroy()
        elseif descendant:IsA("BasePart") then
            descendant.Anchored = true
            descendant.CanTouch = false
        end
    end
end

local function applyTexture(model: Model, textureAssetId: string, alphaEnabled: boolean)
    local numericId = tonumber(textureAssetId)
    if numericId == nil or numericId <= 0 then
        return 0
    end
    local uri = "rbxassetid://" .. tostring(math.floor(numericId))
    local applied = 0
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("MeshPart") then
            if Carrier.IsCarrier(descendant) then
                -- Carrier is a real published mesh, never an Atlas consumer.
                Carrier.Prepare(descendant)
            else
                StudioTextureAppearance.ApplyLocation(descendant, uri, alphaEnabled)
                applied += 1
            end
        end
    end
    return applied
end

function DecoAssetLoader.new(config: any)
    return setmetatable({
        HttpService = config.HttpService,
        AssetService = config.AssetService,
        agentBaseUrl = config.agentBaseUrl,
        agentToken = config.agentToken,
    }, DecoAssetLoader)
end

function DecoAssetLoader:fetchRegistry(): any
    local response = self.HttpService:RequestAsync({
        Url = self.agentBaseUrl .. "/api/location-assets",
        Method = "GET",
        Headers = { ["X-Control-Token"] = self.agentToken },
    })
    if not response.Success then
        error(("Location Assets registry HTTP %d: %s"):format(response.StatusCode, response.Body))
    end
    local decoded = self.HttpService:JSONDecode(response.Body)
    if type(decoded) ~= "table" or type(decoded.items) ~= "table" then
        error("Location Assets registry returned an invalid payload")
    end
    return decoded
end

function DecoAssetLoader:loadPublished(row: any): Model
    if type(row) ~= "table" or tostring(row.status or "") ~= "PUBLISHED" then
        error("DecoManager can load only PUBLISHED location assets")
    end
    local assetId = tonumber(row.model_asset_id)
    if assetId == nil or assetId <= 0 then
        error("selected location asset has no published model Asset ID")
    end

    local loaded: Instance? = nil
    local lastError = ""
    for _ = 1, 6 do
        local ok, value = pcall(function()
            return self.AssetService:LoadAssetAsync(assetId)
        end)
        if ok and value ~= nil then
            loaded = value
            break
        end
        lastError = tostring(value)
        task.wait(0.4)
    end
    if loaded == nil then
        error("could not load location asset " .. tostring(assetId) .. ": " .. lastError)
    end

    local model = canonicalModel(loaded)
    model.Name = tostring(row.slug or "deco_asset")
    sanitize(model)
    -- A static FBX has no Bones and must not acquire a carrier. Legacy static
    -- publications are allowed only after SHA-bound source inspection, then
    -- independently validated against the loaded Roblox Model.
    -- LoadAssetAsync can wrap a valid Blender-authored carrier rig in an inert
    -- RootPart + Motor6D assembly. Normalize only this detached fresh clone;
    -- placed Models are replaced transactionally and are never edited in situ.
    PublishedRigNormalize.Apply(model, row.rigManifest)
    RetiredCleanup.CleanLocation(model)
    local carrier = Carrier.Validate(model, row.rigManifest, row.legacyStaticPublication)
    if carrier then
        -- The outer Roblox Model pivot can belong to an importer wrapper or
        -- a deleted RootPart. It is NOT the authored rig pivot. Capture the
        -- native MeshPart pivot before adjusting the assembly.
        local nativeCarrierPivot = carrier:GetPivot()
        local nativeCarrierOffset = carrier.PivotOffset
        Carrier.Prepare(carrier)
        -- Roblox skinning finds Bones on connected MeshParts within one Model.
        -- Importer Motor6Ds may already form a valid assembly; retain those.
        -- RootPart normalization can also leave disconnected visual/COL parts.
        -- Complete only missing paths on this detached clone, never on Place.
        for _, part in ipairs(model:GetDescendants()) do
            if part:IsA("MeshPart") and part ~= carrier then
                SkinConnection.Connect(model, carrier, part, "LocationSkinWeld")
            end
        end
        -- Promote the actual imported rig_carrier to PrimaryPart without
        -- rebasing its PivotOffset to the unrelated outer Model pivot. Both
        -- DecoManager and Landscape Painter must use this unchanged rig origin.
        model.PrimaryPart = carrier
        if carrier.PivotOffset ~= nativeCarrierOffset
            or carrier:GetPivot() ~= nativeCarrierPivot
            or model:GetPivot() ~= nativeCarrierPivot then
            error("published rig_carrier pivot changed during Location assembly")
        end
    end
    applyTexture(model, tostring(row.texture_asset_id or ""), row.alphaEnabled)
    MeshPhysics.ApplyLocationModel(model, nil, row.meshOptions)
    MeshPhysics.ApplyLocationSurfaceMaterial(model,row.surfaceMaterial,row.robloxMaterial or (row.materialDefinition and row.materialDefinition.robloxMaterial))
    -- Version-2 authored names belong to the immutable publication manifest.
    -- Renaming a visual to the current slug would silently invalidate it.
    return model
end

function DecoAssetLoader:loadForMeshInventory(modelId: string, slug: string): Model
    -- Geometry and Mesh ID inventory are read from immutable published Models.
    -- No separate image publication is performed.
    -- Only historical forensics: older immutable Model publications may have
    -- RootPart and no carrier. No normalization or staging mutation is allowed.
    local id = tonumber(modelId)
    if not id or id <= 0 then error("invalid historical Model ID") end
    local asset = self.AssetService:LoadAssetAsync(id)
    local model = canonicalModel(asset)
    model.Name = slug
    return model
end

return DecoAssetLoader
