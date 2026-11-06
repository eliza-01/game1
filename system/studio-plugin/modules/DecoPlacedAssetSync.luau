-- Location Assets adapter for the same child-rig replacement transaction used
-- by Real Estate. Only this adapter knows the Location slug, publication and
-- audit attributes; the replacement mechanism has no domain-specific rules.
local StudioTextureAppearance = require(script.Parent.StudioTextureAppearance)
local RigSwap = require(script.Parent.StudioManagedRigSwap)
local History = require(script.Parent.StudioPublishedMeshHistory)
local Placement = require(script.Parent.DecoAssetPreparation)
local Physics = require(script.Parent.StudioMeshPhysicsCore)
local Ownership = require(script.Parent.StudioLocationPlacementOwner)
local Geometry = require(script.Parent.StudioLocationPlacedGeometry)
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
    for _, descendant in ipairs(workspace:GetDescendants()) do
        if descendant:IsA("Model") and descendant:GetAttribute(SLUG) == slug
            and tostring(descendant:GetAttribute(INSTANCE) or "") ~= "" then
            -- Same ownership resolver as Find. A nested, individually stamped
            -- asset is valid; its parent grouping Model must not shadow it.
            for _, part in ipairs(descendant:GetDescendants()) do
                if part:IsA("MeshPart") and Ownership.ForPart(workspace, part, slug) == descendant then
                    table.insert(found, descendant)
                    break
                end
            end
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

-- Read-only eligibility check for explicitly linking an old, manually placed
-- publication. Do not grant ownership if its hierarchy was edited by hand.
function DecoPlacedAssetSync.VerifyLegacyModel(model: Model, oldPublished: Model)
    History.VerifyChildren(oldPublished, rigChildren(model))
    oldPublished:ScaleTo(model:GetScale())
    History.Provenance(model, oldPublished)
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
    expectedModelId: string, expectedAtlasId: string, loader: any, preview: any, selectedKeys: {string}): any
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
    if not preview or type(preview.roots)~="table" or type(preview.geometryRoots)~="table" then
        error("Find Mesh IDs in Studio before replacing; no Place geometry modified")
    end
    local chosenParts, chosenRoots, chosenGeometry={},{},{}
    for _, key in ipairs(selectedKeys) do
        local entry=preview.partByKey[key]
        if not entry or not entry.root then error("invalid selected managed MeshPart") end
        chosenParts[entry.part]=true
        chosenRoots[entry.root]=true
        if entry.row.needsMesh then chosenGeometry[entry.root]=true end
    end
    local live={}
    for _, root in ipairs(targets(workspace,slug)) do live[root]=true end
    local placed={}
    for _, root in ipairs(preview.roots) do
        if not live[root] then
            error("scanned Location placement ownership changed; Find again before Sync")
        end
        if chosenRoots[root] then table.insert(placed,root) end
    end
    -- Ensure that every selected part still resolves to the exact scanned
    -- owner. A grouping Model, a copied Instance ID, or a moved nested rig
    -- must never redirect the Sync into an adjacent/parent asset.
    for part in pairs(chosenParts) do
        local selectedOwner = Ownership.ForPart(workspace, part, slug)
        if not selectedOwner or not chosenRoots[selectedOwner] then
            error("scanned MeshPart ownership changed; Find again before Sync")
        end
    end
    if #placed<1 then error("no selected managed Location instance; no Place geometry modified") end
    for part, snap in pairs(preview.partStates or {}) do
        if part.Parent~=snap.parent or part:GetPivot()~=snap.frame or part.Size~=snap.size
            or History.Id(part.MeshId)~=snap.meshId or part.TextureID~=snap.texture then
            error("Mesh identity, transform or texture changed since Find; rescan")
        end
        local surface=part:FindFirstChildOfClass("SurfaceAppearance")
        if (if surface then surface.ColorMap else nil)~=snap.colorMap then
            error("ColorMap changed since Find; rescan")
        end
    end
    if #placed > 1000 then error("more than 1000 placed instances of one slug") end
    -- Only the meshes actually described by the SHA-bound FBX report are
    -- eligible for policy refresh. Never touch manually added MeshParts.
    local inspected = typeof(row.fbxAnalysis) == "table" and row.fbxAnalysis or nil
    local allowedNames = nil
    if inspected and typeof(inspected.meshes) == "table" then
        allowedNames = {}
        for _, entry in ipairs(inspected.meshes) do
            if typeof(entry.name) == "string" then allowedNames[entry.name] = true end
        end
    end
    local needsGeometry = false
    for _, model in ipairs(placed) do
        if chosenGeometry[model] then
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
            local geometry = chosenGeometry[model] == true
            local oldId = tostring(model:GetAttribute("Game1DecoPublishedModelAssetId") or "")
            local previousModelId=oldId
            local oldRef = tostring(model:GetAttribute(REFERENCE) or oldId)
            local changeRef = geometry and oldRef ~= modelId
            local stage, transaction = nil, nil
            local oldParts = meshParts(model)
            if geometry then
                if Ownership.HasNestedPlacements(model) then
                    error("nested Location placements must be synced separately; no Place geometry modified")
                end
                stage = (published :: Model):Clone()
                table.insert(staging, stage)
                -- Same shared managed-rig transaction as Real Estate.
                -- The previous immutable published Model is the authoring
                -- reference. We identify it by MeshPart.MeshId history,
                -- never by old/new names, hierarchy or importer order.
                local previousId=oldId
                if previousId=="" or previousId==modelId then
                    local matchId=nil
                    for _, entry in ipairs(preview.inventory or {}) do
                        if entry.modelAssetId~=modelId and History.MatchesInventory(model,entry) then
                            if matchId then error("ambiguous historical Model version; no Place geometry modified") end
                            matchId=entry.modelAssetId
                        end
                    end
                    previousId=matchId or ""
                end
                if previousId=="" then error("old published Model ID unknown; no Place geometry modified") end
                previousModelId=previousId
                local previousPublished=loader:loadForMeshInventory(previousId,slug)
                local good,problem=pcall(function()
                    local previousChildren=rigChildren(model)
                    History.VerifyChildren(previousPublished,previousChildren)
                    local anchor=Geometry.Align(stage,previousPublished,model)
                    Placement.PreparePlaced(stage,row.meshOptions)
                    transaction = RigSwap.Prepare(model, previousChildren, rigChildren(stage),
                        {preferredPrimary=anchor})
                end)
                previousPublished:Destroy()
                if not good then error(tostring(problem)) end
                totalMeshes += #meshParts(stage)
                if totalMeshes > 4096 then error("more than 4096 MeshParts in scoped Sync") end
            end
            local atlasChanges = {}
            local uri = "rbxassetid://" .. atlasId
            for _, part in ipairs(oldParts) do
                if Physics.IsCollider(part.Name) or part:GetAttribute("Game1DecoPhysicsOnly") == true then continue end
                if not geometry and not chosenParts[part] then continue end
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
            if geometry then add("model", previousModelId, modelId, 1) end
            if changeRef then add("model_reference", oldRef, modelId, 1) end
            for _, change in ipairs(atlasChanges) do add("atlas", change.oldId, atlasId, 1) end
            local beforeMeshes=if geometry then History.Describe(previousModelId,model).meshes else {}
            local afterMeshes=if geometry then History.Describe(modelId,stage).meshes else {}
            local history = oldHistory(model, http)
            local historyJson = nil
            if #events > 0 then
                table.insert(history, {atUtc = os.time(), slug = slug,
                    instanceId = tostring(model:GetAttribute(INSTANCE) or ""), changes = events,
                    meshIdsBefore=beforeMeshes,meshIdsAfter=afterMeshes})
                while #history > 32 do table.remove(history, 1) end
                historyJson = http:JSONEncode(history)
                while #historyJson > 30000 and #history > 1 do
                    table.remove(history, 1)
                    historyJson = http:JSONEncode(history)
                end
                if #historyJson > 30000 then
                    -- The global JSONL/MySQL audit stores the COMPLETE Mesh ID
                    -- sets. Never block Place on a huge Roblox attribute.
                    history[#history].meshIdsBefore = nil
                    history[#history].meshIdsAfter = nil
                    history[#history].meshHistoryInDatabase = true
                    historyJson = http:JSONEncode(history)
                end
                if #historyJson > 30000 then error("Studio history exceeded safe attribute limit") end
            end
            table.insert(plans, {model = model, stage = stage, swap = transaction,
                geometry = geometry, oldId = oldId, oldRef = oldRef,
                changeRef = changeRef, atlasChanges = atlasChanges,
                historyJson = historyJson, oldHistory = model:GetAttribute(HISTORY),
                oldSha = model:GetAttribute("Game1DecoPublishedModelSha256"),
                oldPublishedId = model:GetAttribute("Game1DecoPublishedModelAssetId"),
                oldReference = model:GetAttribute(REFERENCE),
                oldAnchorPath = model:GetAttribute("Game1DecoAuthoringAnchorPath"),
                events = events, meshIdsBefore=beforeMeshes,meshIdsAfter=afterMeshes,
                physicsBefore = if not geometry and allowedNames then
                    Physics.CaptureLocationModel(model, allowedNames) else nil})
        end
    end)
    if not prepared then
        disposeStages()
        error("no Place geometry modified; " .. tostring(issue))
    end
    local changedParts, geometryUpdated, changedReferences, changedModels = 0, 0, 0, 0
    local physicsChecked = 0
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
            if item.physicsBefore and allowedNames then
                physicsChecked += Physics.ApplyLocationModel(model, allowedNames, row.meshOptions)
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
                model:SetAttribute("Game1DecoAuthoringAnchorPath", item.oldAnchorPath)
                model:SetAttribute(HISTORY, item.oldHistory)
                if item.physicsBefore then Physics.RestoreLocationModel(item.physicsBefore) end
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
                studioPath = item.model:GetFullName(), changes = item.events,
                meshIdsBefore=item.meshIdsBefore,meshIdsAfter=item.meshIdsAfter})
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
        meshPartsUpdated = totalMeshes, physicsChecked = physicsChecked,
        pendingGeometry = pending, replacedModels = 0,
        changes = summary, instances = instances}
end

return DecoPlacedAssetSync
