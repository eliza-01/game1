-- M216: scoped, ID-only Location Asset Studio synchronization.
-- CRITICAL: Never replace, re-parent, ScaleTo, PivotTo, ApplyMesh or Destroy a
-- placed Model / MeshPart. A published Model asset is NOT a writable MeshId.
local StudioTextureAppearance = require(script.Parent.StudioTextureAppearance)

local DecoPlacedAssetSync = {}
local SLUG_ATTRIBUTE = "Game1DecoAssetSlug"
local HISTORY_ATTRIBUTE = "Game1DecoSyncHistory"
local REGISTRY_MODEL_ID_ATTRIBUTE = "Game1DecoRegistryModelAssetId"

local function assetId(value: any): string
    local parsed = tonumber(value)
    if not parsed or parsed <= 0 or parsed ~= math.floor(parsed) then
        error("invalid published Location Asset ID")
    end
    return tostring(math.floor(parsed))
end

local function findRow(registry: any, slug: string): any
    if type(registry) ~= "table" or type(registry.items) ~= "table" then
        error("invalid Location Assets registry")
    end
    for _, row in ipairs(registry.items) do
        if tostring(row.slug or "") == slug then
            if tostring(row.status or "") ~= "PUBLISHED" then
                error("Location Asset is not fully published: " .. slug)
            end
            return row
        end
    end
    error("Location Asset is missing from the registry: " .. slug)
end

local function placedModels(workspace: Workspace, slug: string): { Model }
    local result: { Model } = {}
    local authoring = workspace:FindFirstChild("Game1Authoring")
    local camera = workspace.CurrentCamera
    -- Older authored places keep decorations below Workspace.Places, while new
    -- placements live below Workspace.Game1DecoAssets. Identity attributes are
    -- the stable boundary; never move either layout merely to make Sync find it.
    for _, descendant in ipairs(workspace:GetDescendants()) do
        if descendant:IsA("Model")
            and descendant:GetAttribute(SLUG_ATTRIBUTE) == slug
            and tostring(descendant:GetAttribute("Game1DecoInstanceId") or "") ~= ""
            and (authoring == nil or not descendant:IsDescendantOf(authoring))
            and (camera == nil or not descendant:IsDescendantOf(camera)) then
            local ancestor = descendant.Parent
            local nested = false
            while ancestor ~= nil and ancestor ~= workspace do
                if ancestor:IsA("Model") and ancestor:GetAttribute(SLUG_ATTRIBUTE) ~= nil then
                    nested = true
                    break
                end
                ancestor = ancestor.Parent
            end
            if not nested then
                table.insert(result, descendant)
            end
        end
    end
    return result
end

-- Stamp publication identity only on a fresh, unparented placement clone. This
-- is deliberately separate from RefreshIds: ID Sync must never claim that an
-- existing placed model received newly published FBX geometry.
function DecoPlacedAssetSync.StampPublishedModel(model: Model, row: any)
    if not model:IsA("Model") or model.Parent ~= nil then
        error("published identity can only be stamped on a fresh placement clone")
    end
    local modelId = assetId(row.model_asset_id)
    local publishedSha = tostring(row.model_published_sha256 or "")
    if publishedSha == "" then
        error("published Location Asset model SHA is required")
    end
    model:SetAttribute("Game1DecoPublishedModelAssetId", modelId)
    model:SetAttribute("Game1DecoPublishedModelSha256", publishedSha)
    model:SetAttribute(REGISTRY_MODEL_ID_ATTRIBUTE, modelId)
end

local function priorHistory(model: Model, http: any): { any }
    local raw = model:GetAttribute(HISTORY_ATTRIBUTE)
    if raw == nil then
        return {}
    end
    if type(raw) ~= "string" then
        error("invalid Studio ID history attribute on " .. model:GetFullName())
    end
    local ok, decoded = pcall(http.JSONDecode, http, raw)
    if not ok or type(decoded) ~= "table" then
        error("corrupt Studio ID history on " .. model:GetFullName())
    end
    return decoded
end

local function idFromUri(uri: string): string
    return uri:match("(%d+)$") or ""
end

-- This intentionally DOES NOT apply the newly published FBX to old placements.
-- MeshPart.MeshId is not writable. ApplyMesh also replaces collision geometry,
-- so it cannot be used for the promised "replace IDs only" operation.
function DecoPlacedAssetSync.RefreshIds(
    workspace: Workspace, registry: any, targetSlug: string, http: any,
    expectedModelId: string, expectedAtlasId: string
): any
    if type(targetSlug) ~= "string" or targetSlug == "" then
        error("a target Location Asset slug is required; global sync is forbidden")
    end
    local row = findRow(registry, targetSlug)
    local modelId = assetId(row.model_asset_id)
    local atlasId = assetId(row.texture_asset_id)
    if modelId ~= expectedModelId or atlasId ~= expectedAtlasId then
        error("Location Asset publication changed during Studio Sync; retry")
    end
    local models = placedModels(workspace, targetSlug)
    local uri = "rbxassetid://" .. atlasId
    local pending = {}
    local uniqueChanges = {}
    for _, model in ipairs(models) do
        local currentReference = tostring(model:GetAttribute(REGISTRY_MODEL_ID_ATTRIBUTE)
            or model:GetAttribute("Game1DecoPublishedModelAssetId") or "")
        local modelChange = currentReference ~= modelId
        local meshChanges = {}
        for _, descendant in ipairs(model:GetDescendants()) do
            if descendant:IsA("MeshPart") then
                local surface = descendant:FindFirstChildOfClass("SurfaceAppearance")
                if descendant.TextureID ~= uri or (surface ~= nil and surface.ColorMap ~= uri) then
                    table.insert(meshChanges, { part = descendant, oldId = idFromUri(descendant.TextureID) })
                end
            end
        end
        if modelChange or #meshChanges > 0 then
            local history = priorHistory(model, http) -- validate before touching any instance
            table.insert(pending, { model = model, oldModelId = currentReference,
                modelChange = modelChange, meshes = meshChanges, history = history })
            if modelChange then
                uniqueChanges["model_reference:" .. currentReference .. ":" .. modelId] = true
            end
            for _, entry in ipairs(meshChanges) do
                uniqueChanges["atlas:" .. entry.oldId .. ":" .. atlasId] = true
            end
        end
    end
    local differentPairs = 0
    for _ in pairs(uniqueChanges) do
        differentPairs += 1
    end
    if differentPairs > 32 then
        error("too many different published IDs in one Sync; refused before changes")
    end

    local summary = {}
    local function record(kind: string, oldId: string, newId: string)
        local key = kind .. ":" .. oldId .. ":" .. newId
        if not summary[key] then
            summary[key] = { kind = kind, oldId = oldId, newId = newId, count = 0 }
        end
        summary[key].count += 1
    end
    -- Pre-serialize audit entries BEFORE changing any placed object. Store a
    -- compact per-instance summary, not one duplicate record per MeshPart.
    for _, item in ipairs(pending) do
        local group = {}
        local function include(kind: string, oldId: string, newId: string)
            local key = kind .. ":" .. oldId .. ":" .. newId
            if not group[key] then
                group[key] = { kind = kind, oldId = oldId, newId = newId, count = 0 }
            end
            group[key].count += 1
        end
        if item.modelChange then
            include("model_reference", item.oldModelId, modelId)
        end
        for _, entry in ipairs(item.meshes) do
            include("atlas", entry.oldId, atlasId)
        end
        local changes = {}
        for _, event in pairs(group) do
            table.insert(changes, event)
        end
        table.insert(item.history, { atUtc = os.time(), slug = targetSlug,
            instanceId = tostring(item.model:GetAttribute("Game1DecoInstanceId") or ""), changes = changes })
        while #item.history > 32 do
            table.remove(item.history, 1)
        end
        item.encodedHistory = http:JSONEncode(item.history)
        if #item.encodedHistory > 30000 then
            error("Location Asset Studio history too large; refused before changes")
        end
    end

    local modifiedModels, changedParts, modelReferences = 0, 0, 0
    local undo = {}
    local committed, commitError = pcall(function()
        for _, item in ipairs(pending) do
            local model: Model = item.model
            item.committedChanges = {}
            local function committedChange(kind: string, oldId: string, newId: string)
                local key = kind .. ":" .. oldId .. ":" .. newId
                if not item.committedChanges[key] then
                    item.committedChanges[key] = {
                        kind = kind, oldId = oldId, newId = newId, count = 0,
                    }
                end
                item.committedChanges[key].count += 1
            end
            -- Do not commit if the place has been edited while preflight ran.
            if model.Parent == nil or model:GetAttribute(SLUG_ATTRIBUTE) ~= targetSlug then
                error("placed Location Asset changed during Sync; aborting")
            end
            -- The model ID is only a registry REFERENCE. In particular leave
            -- Game1DecoPublishedModelSha256 unchanged: the FBX stays as placed.
            if item.modelChange then
                table.insert(undo, {kind = "model_reference", model = model,
                    previous = model:GetAttribute(REGISTRY_MODEL_ID_ATTRIBUTE)})
                model:SetAttribute(REGISTRY_MODEL_ID_ATTRIBUTE, modelId)
                modelReferences += 1
                record("model_reference", item.oldModelId, modelId)
                committedChange("model_reference", item.oldModelId, modelId)
            end
            for _, entry in ipairs(item.meshes) do
                local mesh: MeshPart = entry.part
                local surface = mesh:FindFirstChildOfClass("SurfaceAppearance")
                table.insert(undo, {kind = "atlas", mesh = mesh, surface = surface,
                    texture = mesh.TextureID, colorMap = if surface then surface.ColorMap else nil})
                -- Central texture adapter in STRICT ID-only mode. No AlphaMode,
                -- SurfaceAppearance creation, pivot, scale or collision changes.
                if StudioTextureAppearance.Apply(mesh, uri, nil, true) then
                    changedParts += 1
                    record("atlas", entry.oldId, atlasId)
                    committedChange("atlas", entry.oldId, atlasId)
                end
            end
            table.insert(undo, {kind = "history", model = model,
                previous = model:GetAttribute(HISTORY_ATTRIBUTE)})
            model:SetAttribute(HISTORY_ATTRIBUTE, item.encodedHistory)
            modifiedModels += 1
        end
    end)
    if not committed then
        -- Best-effort transaction rollback. Never Destroy / Clone a Model.
        for index = #undo, 1, -1 do
            local entry = undo[index]
            pcall(function()
                if entry.kind == "atlas" then
                    entry.mesh.TextureID = entry.texture
                    if entry.surface ~= nil and entry.colorMap ~= nil then
                        entry.surface.ColorMap = entry.colorMap
                    end
                elseif entry.kind == "model_reference" then
                    entry.model:SetAttribute(REGISTRY_MODEL_ID_ATTRIBUTE, entry.previous)
                elseif entry.kind == "history" then
                    entry.model:SetAttribute(HISTORY_ATTRIBUTE, entry.previous)
                end
            end)
        end
        error("scoped Location Asset ID sync failed; ID rollback attempted: " .. tostring(commitError), 2)
    end
    local changes = {}
    for _, event in pairs(summary) do
        table.insert(changes, event)
    end
    table.sort(changes, function(a, b)
        return a.kind .. a.oldId .. a.newId < b.kind .. b.oldId .. b.newId
    end)
    -- The central audit database needs the exact placed instance affected by
    -- each replacement. The bounded model attribute above remains only a
    -- convenient recent cache inside Studio; this response is the durable log.
    local instances = {}
    for _, item in ipairs(pending) do
        local instanceChanges = {}
        for _, event in pairs(item.committedChanges) do
            table.insert(instanceChanges, event)
        end
        table.sort(instanceChanges, function(a, b)
            return a.kind .. a.oldId .. a.newId < b.kind .. b.oldId .. b.newId
        end)
        if #instanceChanges > 0 then
            table.insert(instances, {
                instanceId = tostring(item.model:GetAttribute("Game1DecoInstanceId") or ""),
                studioPath = item.model:GetFullName(),
                changes = instanceChanges,
            })
        end
    end
    local pendingGeometry = 0
    for _, model in ipairs(models) do
        if tostring(model:GetAttribute("Game1DecoPublishedModelSha256") or "")
            ~= tostring(row.model_published_sha256 or "") then
            pendingGeometry += 1
        end
    end
    return { models = modifiedModels, parts = changedParts, matchedModels = #models,
        modelReferences = modelReferences, pendingGeometry = pendingGeometry,
        replacedModels = 0, changes = changes, instances = instances }
end

return DecoPlacedAssetSync
