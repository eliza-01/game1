-- Location Assets adapter for the same child-rig replacement transaction used
-- by Real Estate. Only this adapter knows the Location slug, publication and
-- audit attributes; the replacement mechanism has no domain-specific rules.
local StudioTextureAppearance = require(script.Parent.StudioTextureAppearance)
local RigSwap = require(script.Parent.StudioManagedRigSwap)
local Placement = require(script.Parent.DecoAssetPreparation)
local DecoPlacedAssetSync = {}

local SLUG = "Game1DecoAssetSlug"
local INSTANCE = "Game1DecoInstanceId"
local HISTORY = "Game1DecoSyncHistory"
local REFERENCE = "Game1DecoRegistryModelAssetId"

local function id(value: any): string
    local n = tonumber(value)
    if not n or n <= 0 or n ~= math.floor(n) then error("invalid published asset ID") end
    return tostring(math.floor(n))
end

local function rowFor(registry: any, slug: string): any
    if type(registry) ~= "table" or type(registry.items) ~= "table" then
        error("invalid Location Assets registry")
    end
    for _, row in ipairs(registry.items) do
        if tostring(row.slug or "") == slug then
            if row.status ~= "PUBLISHED" then error("Location Asset is not published: " .. slug) end
            return row
        end
    end
    error("Location Asset not registered: " .. slug)
end

local function targets(workspace: Workspace, slug: string): {Model}
    local found = {}
    local authoring = workspace:FindFirstChild("Game1Authoring")
    local camera = workspace.CurrentCamera
    for _, descendant in ipairs(workspace:GetDescendants()) do
        if descendant:IsA("Model") and descendant:GetAttribute(SLUG) == slug
            and tostring(descendant:GetAttribute(INSTANCE) or "") ~= ""
            and (not authoring or not descendant:IsDescendantOf(authoring))
            and (not camera or not descendant:IsDescendantOf(camera)) then
            local ancestor: Instance? = descendant.Parent
            local nested = false
            while ancestor and ancestor ~= workspace do
                if ancestor:IsA("Model") and ancestor:GetAttribute(SLUG) ~= nil then
                    nested = true
                    break
                end
                ancestor = ancestor.Parent
            end
            if not nested then table.insert(found, descendant) end
        end
    end
    return found
end

local function meshParts(model: Model): {MeshPart}
    local parts = {}
    for _, obj in ipairs(model:GetDescendants()) do
        if obj:IsA("MeshPart") then table.insert(parts, obj) end
    end
    return parts
end

-- A stable published MeshPart pivot, rather than the import-dependent Model
-- bounding-box pivot, is used exactly like Real Estate's authored house anchor.
-- Accept a unique mesh, or one uniquely matching Name across the revisions.
local function anchors(old: Model, candidate: Model): (MeshPart, MeshPart)
    local before, after = meshParts(old), meshParts(candidate)
    if #before == 1 and #after == 1 then return before[1], after[1] end
    local byName = {}
    for _, part in ipairs(after) do
        if byName[part.Name] then byName[part.Name] = false
        else byName[part.Name] = part end
    end
    local pairsFound = {}
    for _, part in ipairs(before) do
        if byName[part.Name] then
            table.insert(pairsFound, {old = part, new = byName[part.Name]})
        end
    end
    if #pairsFound ~= 1 then
        error("ambiguous Location Asset authoring anchor: unique MeshPart name required")
    end
    return pairsFound[1].old, pairsFound[1].new
end

local function rigChildren(model: Model): {Instance}
    local result = {}
    for _, child in ipairs(model:GetChildren()) do
        if child:IsA("BasePart") then
            table.insert(result, child)
        elseif child:IsA("Model") or child:IsA("Folder") then
            if child:FindFirstChildWhichIsA("BasePart", true) then
                table.insert(result, child)
            end
        end
    end
    if #result == 0 then error("Location Asset contains no managed geometry children") end
    return result
end

function DecoPlacedAssetSync.StampPublishedModel(model: Model, row: any)
    if not model:IsA("Model") or model.Parent ~= nil then
        error("published identity may only be stamped on a fresh placement clone")
    end
    local modelId = id(row.model_asset_id)
    local sha = tostring(row.model_published_sha256 or "")
    if sha == "" then error("Location Asset published SHA is required") end
    model:SetAttribute("Game1DecoPublishedModelAssetId", modelId)
    model:SetAttribute("Game1DecoPublishedModelSha256", sha)
    model:SetAttribute(REFERENCE, modelId)
end

local function oldHistory(model: Model, http: any): {any}
    local encoded = model:GetAttribute(HISTORY)
    if encoded == nil then return {} end
    if type(encoded) ~= "string" then error("invalid Studio asset history") end
    local ok, decoded = pcall(http.JSONDecode, http, encoded)
    if not ok or type(decoded) ~= "table" then error("corrupt Studio asset history") end
    return decoded
end

local function textureId(uri: string): string
    return uri:match("(%d+)$") or ""
end

function DecoPlacedAssetSync.RefreshIds(workspace: Workspace, registry: any, slug: string, http: any,
    expectedModelId: string, expectedAtlasId: string, loader: any): any
    if type(slug) ~= "string" or slug == "" then
        error("one explicitly selected Location Asset slug is required")
    end
    local row = rowFor(registry, slug)
    local modelId, atlasId = id(row.model_asset_id), id(row.texture_asset_id)
    if modelId ~= expectedModelId or atlasId ~= expectedAtlasId then
        error("Location Asset publication changed during Studio Sync; retry")
    end
    local publishedSha = tostring(row.model_published_sha256 or "")
    if publishedSha == "" then error("missing published FBX SHA") end
    local placed = targets(workspace, slug)
    if #placed > 1000 then error("more than 1000 placed instances of one slug") end
    local needsGeometry = false
    for _, model in ipairs(placed) do
        if tostring(model:GetAttribute("Game1DecoPublishedModelSha256") or "") ~= publishedSha then
            needsGeometry = true
            break
        end
    end
    local published: Model? = nil
    if needsGeometry then published = loader:loadPublished(row) end
    local plans = {}
    local staging = {}
    local totalMeshes = 0
    local function disposeStages()
        for _, stage in ipairs(staging) do stage:Destroy() end
        if published then published:Destroy() end
    end
    -- PREPARE EVERY INSTANCE FIRST. A bad skinned rig, anchor, or model layout
    -- must fail before any placed root or texture is modified.
    local prepared, issue = pcall(function()
        for _, model in ipairs(placed) do
            local geometry = tostring(model:GetAttribute("Game1DecoPublishedModelSha256") or "") ~= publishedSha
            local oldId = tostring(model:GetAttribute("Game1DecoPublishedModelAssetId") or "")
            local oldRef = tostring(model:GetAttribute(REFERENCE) or oldId)
            local changeRef = oldRef ~= modelId
            local stage, transaction = nil, nil
            local oldParts = meshParts(model)
            if geometry then
                stage = (published :: Model):Clone()
                table.insert(staging, stage)
                -- Mirror DecoPlacement's authored scale, then align via the
                -- MeshPart's stable Blender-authored pivot (Real Estate method).
                stage:ScaleTo(model:GetScale())
                local existingAnchor, freshAnchor = anchors(model, stage)
                RigSwap.AlignToAnchor(stage, freshAnchor, existingAnchor:GetPivot(), "Location Asset " .. slug)
                Placement.PreparePlaced(stage)
                -- Unowned geometry added directly to a placed root must not be
                -- silently classified as an FBX rig and deleted. Published
                -- direct-child names/classes must match the legacy instance.
                local previousChildren, nextChildren = rigChildren(model), rigChildren(stage)
                if #previousChildren ~= #nextChildren then
                    error("placed/published rig count differs; refusing to remove unknown geometry")
                end
                local nextByName = {}
                for _, child in ipairs(nextChildren) do
                    if nextByName[child.Name] then error("duplicate published rig child " .. child.Name) end
                    nextByName[child.Name] = child
                end
                for _, child in ipairs(previousChildren) do
                    local nextChild = nextByName[child.Name]
                    if not nextChild or child.ClassName ~= nextChild.ClassName then
                        error("unmatched placed rig child " .. child.Name .. "; no Place changed")
                    end
                end
                transaction = RigSwap.Prepare(model, previousChildren, nextChildren)
                totalMeshes += #meshParts(stage)
                if totalMeshes > 4096 then error("more than 4096 MeshParts in scoped Sync") end
            end
            local atlasChanges = {}
            local uri = "rbxassetid://" .. atlasId
            for _, part in ipairs(oldParts) do
                local surface = part:FindFirstChildOfClass("SurfaceAppearance")
                if part.TextureID ~= uri or (surface and surface.ColorMap ~= uri) then
                    local previousUri = if part.TextureID == uri and surface then surface.ColorMap else part.TextureID
                    table.insert(atlasChanges, {part = part, oldId = textureId(previousUri),
                        texture = part.TextureID, surface = surface,
                        colorMap = if surface then surface.ColorMap else nil})
                end
            end
            local events, eventIndex = {}, {}
            local function add(kind: string, oldValue: string, newValue: string, count: number)
                local key = kind .. ":" .. oldValue .. ":" .. newValue
                if not eventIndex[key] then
                    eventIndex[key] = {kind = kind, oldId = oldValue, newId = newValue, count = 0}
                    table.insert(events, eventIndex[key])
                end
                eventIndex[key].count += count
            end
            if geometry then add("model", oldId, modelId, 1) end
            if changeRef then add("model_reference", oldRef, modelId, 1) end
            for _, change in ipairs(atlasChanges) do add("atlas", change.oldId, atlasId, 1) end
            local history = oldHistory(model, http)
            local historyJson = nil
            if #events > 0 then
                table.insert(history, {atUtc = os.time(), slug = slug,
                    instanceId = tostring(model:GetAttribute(INSTANCE) or ""), changes = events})
                while #history > 32 do table.remove(history, 1) end
                historyJson = http:JSONEncode(history)
                if #historyJson > 30000 then error("Studio history exceeded attribute limit") end
            end
            table.insert(plans, {model = model, stage = stage, swap = transaction,
                geometry = geometry, oldId = oldId, oldRef = oldRef,
                changeRef = changeRef, atlasChanges = atlasChanges,
                historyJson = historyJson, oldHistory = model:GetAttribute(HISTORY),
                oldSha = model:GetAttribute("Game1DecoPublishedModelSha256"),
                oldPublishedId = model:GetAttribute("Game1DecoPublishedModelAssetId"),
                oldReference = model:GetAttribute(REFERENCE), events = events})
        end
    end)
    if not prepared then
        disposeStages()
        error("no Place geometry modified; " .. tostring(issue))
    end
    local changedParts, geometryUpdated, changedReferences, changedModels = 0, 0, 0, 0
    local ok, problem = pcall(function()
        for _, item in ipairs(plans) do
            local model = item.model
            if model.Parent == nil or model:GetAttribute(SLUG) ~= slug then
                error("placed Location Asset changed during sync")
            end
            if item.swap then
                RigSwap.Commit(item.swap)
                geometryUpdated += 1
                model:SetAttribute("Game1DecoPublishedModelAssetId", modelId)
                model:SetAttribute("Game1DecoPublishedModelSha256", publishedSha)
            end
            if item.changeRef then
                model:SetAttribute(REFERENCE, modelId)
                changedReferences += 1
            end
            local uri = "rbxassetid://" .. atlasId
            for _, change in ipairs(item.atlasChanges) do
                if item.geometry then
                    -- Source rig is already textured by the central DecoAssetLoader.
                    changedParts += 1
                elseif StudioTextureAppearance.Apply(change.part, uri, nil, true) then
                    changedParts += 1
                end
            end
            if item.historyJson then model:SetAttribute(HISTORY, item.historyJson) end
            if #item.events > 0 then changedModels += 1 end
        end
    end)
    if not ok then
        for index = #plans, 1, -1 do
            local item = plans[index]
            local model = item.model
            pcall(function()
                model:SetAttribute("Game1DecoPublishedModelAssetId", item.oldPublishedId)
                model:SetAttribute("Game1DecoPublishedModelSha256", item.oldSha)
                model:SetAttribute(REFERENCE, item.oldReference)
                model:SetAttribute(HISTORY, item.oldHistory)
                for _, change in ipairs(item.atlasChanges) do
                    if not item.geometry then
                        change.part.TextureID = change.texture
                        if change.surface then change.surface.ColorMap = change.colorMap end
                    end
                end
            end)
            if item.swap then RigSwap.Rollback(item.swap) end
        end
        disposeStages()
        error("Location Asset rig sync failed; all managed child swaps rolled back: " .. tostring(problem))
    end
    for _, item in ipairs(plans) do
        if item.swap then RigSwap.Finalize(item.swap) end
    end
    disposeStages()
    local summary, grouped = {}, {}
    local instances = {}
    for _, item in ipairs(plans) do
        if #item.events > 0 then
            table.insert(instances, {instanceId = tostring(item.model:GetAttribute(INSTANCE) or ""),
                studioPath = item.model:GetFullName(), changes = item.events})
            for _, event in ipairs(item.events) do
                local key = event.kind .. ":" .. event.oldId .. ":" .. event.newId
                if not grouped[key] then
                    grouped[key] = {kind = event.kind, oldId = event.oldId,
                        newId = event.newId, count = 0}
                    table.insert(summary, grouped[key])
                end
                grouped[key].count += event.count
            end
        end
    end
    table.sort(summary, function(a,b) return a.kind .. a.oldId .. a.newId < b.kind .. b.oldId .. b.newId end)
    local pending = 0
    for _, model in ipairs(placed) do
        if tostring(model:GetAttribute("Game1DecoPublishedModelSha256") or "") ~= publishedSha then
            pending += 1
        end
    end
    return {models = changedModels, parts = changedParts, matchedModels = #placed,
        modelReferences = changedReferences, geometryUpdated = geometryUpdated,
        meshPartsUpdated = totalMeshes, pendingGeometry = pending, replacedModels = 0,
        changes = summary, instances = instances}
end

return DecoPlacedAssetSync
