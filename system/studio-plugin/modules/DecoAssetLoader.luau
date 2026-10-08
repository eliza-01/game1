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

local function applyTexture(model: Model, textureAssetId: string)
    local numericId = tonumber(textureAssetId)
    if numericId == nil or numericId <= 0 then
        return 0
    end
    local uri = "rbxassetid://" .. tostring(math.floor(numericId))
    local applied = 0
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("MeshPart") then
            descendant.TextureID = uri
            applied += 1
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
    applyTexture(model, tostring(row.texture_asset_id or ""))
    return model
end

return DecoAssetLoader
