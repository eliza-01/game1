local Carrier = require(script.Parent.StudioLocationRigCarrier)
-- Location Assets adapter for the same child-rig replacement transaction used
-- by Real Estate. Only this adapter knows the Location slug, publication and
-- audit attributes; the replacement mechanism has no domain-specific rules.
local StudioTextureAppearance = require(script.Parent.StudioTextureAppearance)
local Visual = require(script.Parent.StudioLocationVisualAppearance)
local RigSwap = require(script.Parent.StudioManagedRigSwap)
local History = require(script.Parent.StudioPublishedMeshHistory)
local BoneEffects = require(script.Parent.StudioPlacedRigBoneEffects)
local Placement = require(script.Parent.DecoAssetPreparation)
local Physics = require(script.Parent.StudioMeshPhysicsCore)
local RetiredCleanup = require(script.Parent.StudioRetiredColMeshCleanup)
local Ownership = require(script.Parent.StudioLocationPlacementOwner)
local Geometry = require(script.Parent.StudioLocationPlacedGeometry)
local collisionModuleOk, Collision = pcall(require, script.Parent.StudioLocationCollisionParts)
local DecoPlacedAssetSync = {}

local SLUG = "Game1DecoAssetSlug"
local INSTANCE = "Game1DecoInstanceId"
local HISTORY = "Game1DecoSyncHistory"
local REFERENCE = "Game1DecoRegistryModelAssetId"

local function belongsToSlug(value: any, slug: string, aliases: {string}?): boolean
    if value == slug then return true end
    for _, alias in ipairs(aliases or {}) do
        if value == alias then return true end
    end
    return false
end

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

local function targets(workspace: Workspace, slug: string, aliases: {string}?): {Model}
    local found = {}
    for _, descendant in ipairs(workspace:GetDescendants()) do
        if descendant:IsA("Model") and belongsToSlug(descendant:GetAttribute(SLUG), slug, aliases)
            and tostring(descendant:GetAttribute(INSTANCE) or "") ~= "" then
            -- Same ownership resolver as Find. A nested, individually stamped
            -- asset is valid; its parent grouping Model must not shadow it.
            for _, part in ipairs(descendant:GetDescendants()) do
                if part:IsA("MeshPart") and Ownership.ForPart(workspace, part, slug, aliases) == descendant then
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
    if not collisionModuleOk then error("Collision generator unavailable; rig Sync blocked") end
    local result = {}
    for _, child in ipairs(model:GetChildren()) do
        if Collision.IsOwned(child) then continue end
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

-- A placed rig can already be the CURRENT immutable publication while its
-- legacy Model ID / SHA attributes are stale. Verify the entire managed rig,
-- not one visual MeshId or an untrusted attribute, before reconciling metadata.
-- Alignment is tested only on detached clones: no placed geometry is touched.
local function matchesCurrentPublishedRig(model: Model, published: Model, row: any): boolean
    if Carrier.Diagnose(model, row.rigManifest, row.legacyStaticPublication) ~= "current" then
        return false
    end
    if not History.MatchesInventory(model, History.Describe(tostring(row.model_asset_id), published)) then
        return false
    end
    local good = pcall(History.VerifyChildren, published, rigChildren(model))
    if not good then return false end
    local probe = published:Clone()
    local reference = published:Clone()
    local aligned = pcall(Geometry.Align, probe, reference, model)
    reference:Destroy()
    if not aligned then probe:Destroy(); return false end

    -- The same Mesh IDs can be republished with changed local part or Bone
    -- transforms. Only reconcile metadata when the actual authored geometry
    -- agrees too. Duplicated Mesh IDs cannot establish a unique correspondence.
    local sources, actuals = {}, {}
    for _, pair in ipairs({{probe, sources}, {model, actuals}}) do
        for _, part in ipairs(meshParts(pair[1])) do
            local meshId = History.Id(part.MeshId)
            if meshId == "" or pair[2][meshId] then
                probe:Destroy()
                return false
            end
            pair[2][meshId] = part
        end
    end
    for meshId, source in pairs(sources) do
        local target = actuals[meshId]
        if not target or (source.Size - target.Size).Magnitude > 0.025
            or (source.CFrame.Position - target.CFrame.Position).Magnitude > 0.04
            or source.CFrame.LookVector:Dot(target.CFrame.LookVector) < 0.9995
            or source.CFrame.UpVector:Dot(target.CFrame.UpVector) < 0.9995 then
            probe:Destroy()
            return false
        end
    end
    local authoredBones = {}
    for _, item in ipairs(probe:GetDescendants()) do
        if item:IsA("Bone") then authoredBones[item.Name] = item.CFrame end
    end
    local boneCount = 0
    for _, item in ipairs(model:GetDescendants()) do
        if item:IsA("Bone") then
            local authored = authoredBones[item.Name]
            if not authored or (authored.Position - item.CFrame.Position).Magnitude > 0.025
                or authored.LookVector:Dot(item.CFrame.LookVector) < 0.9995
                or authored.UpVector:Dot(item.CFrame.UpVector) < 0.9995 then
                probe:Destroy()
                return false
            end
            boneCount += 1
        end
    end
    local expectedBoneCount = 0
    for _ in pairs(authoredBones) do expectedBoneCount += 1 end
    probe:Destroy()
    return boneCount == expectedBoneCount
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
    expectedModelId: string, expectedAtlasId: string, loader: any, preview: any,
    selectedKeys: {string}, rigChoices: {[string]: string}?): any
    if type(slug) ~= "string" or slug == "" then
        error("one explicitly selected Location Asset slug is required")
    end
    local row = rowFor(registry, slug)
    local modelId = id(row.model_asset_id)
    local atlasId = if row.appearanceMode=="material" then "" else id(row.texture_asset_id)
    if modelId ~= expectedModelId or atlasId ~= expectedAtlasId then
        error("Location Asset publication changed during Studio Sync; retry")
    end
    local publishedSha = tostring(row.model_published_sha256 or "")
    if publishedSha == "" then error("missing published FBX SHA") end
    if not preview or type(preview.roots)~="table" or type(preview.geometryRoots)~="table" then
        error("Find Mesh IDs in Studio before replacing; no Place geometry modified")
    end
    local chosenParts, chosenRoots, chosenGeometry,chosenPhysics={},{},{},{}
    local historicalRigChoices={}
    for _, key in ipairs(selectedKeys) do
        local entry=preview.partByKey[key]
        if not entry or not entry.root then error("invalid selected managed MeshPart") end
        chosenParts[entry.part]=true
        chosenRoots[entry.root]=true
        if entry.row.needsMesh then
            chosenGeometry[entry.root]=true
            local choice=if rigChoices then rigChoices[key] else nil
            if choice~=nil and choice~="rig" and choice~="static" then
                error("invalid historical rig choice; no Place geometry modified")
            end
            local previous=historicalRigChoices[entry.root]
            if previous and choice and previous~=choice then
                error("contradictory rig answers for one placed Model; no Place geometry modified")
            end
            historicalRigChoices[entry.root]=choice or previous or "rig"
        end
        if entry.row.needsPhysics then chosenPhysics[entry.part]=true end
    end
    local live={}
    for _, root in ipairs(targets(workspace,slug,row.aliases)) do live[root]=true end
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
        local selectedOwner = Ownership.ForPart(workspace, part, slug, row.aliases)
        if not selectedOwner or not chosenRoots[selectedOwner] then
            error("scanned MeshPart ownership changed; Find again before Sync")
        end
    end
    if #placed<1 then error("no selected managed Location instance; no Place geometry modified") end
    -- The INCOMING publication must be canonical. The outgoing placement may
    -- legitimately be an older immutable topology (including a two-part rig
    -- without carrier). Its complete historical Model inventory is verified
    -- below before StudioManagedRigSwap replaces the managed child rig.
    if row.needsFbxInspection==true then
        error("analyze the saved FBX before migrating placed rigs; Place unchanged")
    end
    if not Carrier.IsCanonicalPublication(row.rigManifest,row.legacyStaticPublication) then
        error("current Model publication is not canonical; republish before Studio migration")
    end
    for part, snap in pairs(preview.partStates or {}) do
        if part.Parent~=snap.parent or part:GetPivot()~=snap.frame or part.Size~=snap.size
            or History.Id(part.MeshId)~=snap.meshId or part.TextureID~=snap.texture or part.Material~=snap.material
            or part.Color~=snap.color or part:GetAttribute("Game1DecoAppearanceMode")~=snap.appearanceMode
            or part.CanCollide~=snap.canCollide or part.CanQuery~=snap.canQuery
            or part.CanTouch~=snap.canTouch or part.DoubleSided~=snap.doubleSided
            or part.CollisionFidelity~=snap.collisionFidelity then
            error("Mesh identity, transform or texture changed since Find; rescan")
        end
        local surface=part:FindFirstChildOfClass("SurfaceAppearance")
        if (if surface then surface.ColorMap else nil)~=snap.colorMap
            or surface~=snap.surface or (if surface then surface.AlphaMode else nil)~=snap.alphaMode then
            error("ColorMap or AlphaMode changed since Find; rescan")
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
    for part in pairs(chosenPhysics) do
        if not allowedNames or allowedNames[part.Name] ~= true then
            error("selected MeshPart is outside the SHA-bound physics report; no Place geometry modified")
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
            local changeRef = false
            local metadataCurrent = false
            local stage, transaction = nil, nil
            local oldParts = meshParts(model)
            if geometry then
                if Ownership.HasNestedPlacements(model) then
                    error("nested Location placements must be synced separately; no Place geometry modified")
                end
                -- If Studio already contains the exact current rig, a swap
                -- would destroy and recreate unchanged geometry. Reconcile
                -- publication metadata only after whole-rig and transform
                -- verification against the LOADED current Model.
                metadataCurrent = matchesCurrentPublishedRig(model, published :: Model, row)
                if metadataCurrent then
                    geometry = false
                else
                    stage = (published :: Model):Clone()
                    table.insert(staging, stage)
                    -- A genuinely old rig still requires an immutable prior
                    -- publication. Never guess from one shared Mesh ID.
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
                    if previousId=="" then
                        local ids = {}
                        for _, part in ipairs(oldParts) do
                            table.insert(ids, part.Name .. "=" .. History.Id(part.MeshId))
                        end
                        table.sort(ids)
                        error("published Model source unverified for " .. model:GetFullName()
                            .. "; stamped Model ID=" .. oldId .. "; placed Mesh IDs="
                            .. table.concat(ids, ", "):sub(1, 450)
                            .. "; neither current rig nor unique historical publication matches; "
                            .. "no Place geometry modified")
                    end
                    previousModelId=previousId
                    local previousVersion=nil
                    for _, version in ipairs(preview.inventory or {}) do
                        if version.modelAssetId==previousId then previousVersion=version break end
                    end
                    if not previousVersion then
                        error("historical Model evidence missing for "..previousId
                            .."; no Place geometry modified")
                    end
                    if historicalRigChoices[model]=="static" then
                        for _, item in ipairs(model:GetDescendants()) do
                            if item:IsA("Bone") or item.Name=="rig_carrier"
                                or item:IsA("WrapLayer") or item:IsA("WrapTarget")
                                or item:IsA("Motor6D") then
                                error("placed Model contains a rig; choose Yes before Sync; no Place geometry modified")
                            end
                        end
                    end
                    local previousPublished=loader:loadHistoricalRigForComparison(
                        previousId,slug,previousVersion.rigManifest,
                        historicalRigChoices[model])
                    local good,problem=pcall(function()
                        local previousChildren=rigChildren(model)
                        History.VerifyChildren(previousPublished,previousChildren)
                        local anchor=Geometry.Align(stage,previousPublished,model)
                        Placement.PrepareSynced(stage,row.meshOptions,row.surfaceMaterial,nil)
                        BoneEffects.CopyToIncoming(previousChildren, rigChildren(stage))
                        transaction = RigSwap.Prepare(model, previousChildren, rigChildren(stage),
                            {preferredPrimary=anchor})
                    end)
                    previousPublished:Destroy()
                    if not good then error(tostring(problem)) end
                    totalMeshes += #meshParts(stage)
                    if totalMeshes > 4096 then error("more than 4096 MeshParts in scoped Sync") end
                end
            end
            changeRef = (geometry or metadataCurrent) and oldRef ~= modelId
            local atlasChanges = {}
            local uri = "rbxassetid://" .. atlasId
            for _, part in ipairs(oldParts) do
                if Carrier.IsCarrier(part) or Physics.IsCollider(part.Name)
                    or part:GetAttribute("Game1DecoPhysicsOnly") == true then continue end
                if not geometry and not chosenParts[part] then continue end
                if not Visual.IsCurrent(part,row) then
                    table.insert(atlasChanges, {part=part,oldId=textureId(part.TextureID),
                        before=Visual.Capture(part)})
                end
            end
            local alphaChanges={}
            -- Keep the historical Alpha audit while applying each MeshPart's
            -- effective settings. Visual.Apply owns the actual transition.
            if not geometry then
                for _, part in ipairs(oldParts) do
                    local settings=Visual.Settings(part,row)
                    if chosenParts[part] and not Carrier.IsCarrier(part) and not Physics.IsCollider(part.Name)
                        and part:GetAttribute("Game1DecoPhysicsOnly")~=true
                        and settings.appearanceMode~="material"
                        and not StudioTextureAppearance.AlphaCurrent(part,settings.alphaEnabled==true) then
                        table.insert(alphaChanges,StudioTextureAppearance.Capture(part))
                    end
                end
            end
            local physicsNames=nil
            if not geometry and allowedNames then
                for _, part in ipairs(oldParts) do
                    if chosenPhysics[part] and allowedNames[part.Name] == true then
                        physicsNames=physicsNames or {}
                        physicsNames[part.Name]=true
                    end
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
            if changeRef then add("model_reference", oldRef, modelId, 1)
            elseif metadataCurrent and oldId ~= modelId then
                -- Changed publication stamp, NOT changed geometry.
                add("model_reference", oldId, modelId, 1)
            end
            for _, change in ipairs(atlasChanges) do
                local settings=Visual.Settings(change.part,row)
                if settings.appearanceMode=="material" then
                    local oldAppearance=change.oldId
                    if change.before.mode=="material" then
                        oldAppearance=tostring(change.before.visualMaterial or "")
                            ..tostring(change.before.visualColor or "")
                    end
                    add("appearance",oldAppearance,tostring(settings.visualMaterial)..tostring(settings.visualColor),1)
                else
                    add("atlas",change.oldId,tostring(settings.texture_asset_id or ""),1)
                end
            end
            for _, change in ipairs(alphaChanges) do
                -- Persist the stable enum name. tostring(EnumItem) includes the
                -- "Enum.AlphaMode." prefix and does not fit the audit value
                -- contract used after Studio has already committed the edit.
                add("alpha",if change.mode then change.mode.Name else "missing",
                    if row.alphaEnabled==true then "Transparency" else "Opaque",1)
            end
            if physicsNames then
                local count=0
                for _ in pairs(physicsNames) do count+=1 end
                add("physics","previous","registered",count)
            end
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
                geometry = geometry, metadataCurrent = metadataCurrent,
                oldId = oldId, oldRef = oldRef,
                changeRef = changeRef, atlasChanges = atlasChanges,alphaChanges=alphaChanges,
                historyJson = historyJson, oldHistory = model:GetAttribute(HISTORY),
                oldSha = model:GetAttribute("Game1DecoPublishedModelSha256"),
                oldPublishedId = model:GetAttribute("Game1DecoPublishedModelAssetId"),
                oldReference = model:GetAttribute(REFERENCE),
                oldSlug = model:GetAttribute(SLUG), oldName = model.Name,
                oldAnchorPath = model:GetAttribute("Game1DecoAuthoringAnchorPath"),
                events = events, meshIdsBefore=beforeMeshes,meshIdsAfter=afterMeshes,
                physicsNames=physicsNames,
                physicsBefore = if physicsNames then
                    Physics.CaptureLocationModel(model, physicsNames) else nil})
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
            if model.Parent == nil or not belongsToSlug(model:GetAttribute(SLUG),slug,row.aliases) then
                error("placed Location Asset changed during sync")
            end
            if item.swap then
                RigSwap.Commit(item.swap)
                geometryUpdated += 1
            end
            if item.swap or item.metadataCurrent then
                -- Rename only the retained root identity. Its parent, scale and
                -- geometry stay put; pivot metadata follows the aligned publication.
                model:SetAttribute(SLUG,slug)
                local instanceId=tostring(model:GetAttribute(INSTANCE) or "")
                if instanceId~="" then model.Name=slug.."__"..instanceId:sub(1,8) end
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
                elseif Visual.Apply(change.part,row) then
                    changedParts += 1
                end
            end
            for _, change in ipairs(item.alphaChanges) do
                local settings=Visual.Settings(change.mesh,row)
                if StudioTextureAppearance.ApplyAlpha(change.mesh,settings.alphaEnabled==true,
                    "rbxassetid://"..tostring(settings.texture_asset_id or "")) then
                    changedParts+=1
                end
            end
            if not item.geometry then
                for _, change in ipairs(item.atlasChanges) do
                    Visual.AssertCurrent(change.part, row)
                end
                for _, change in ipairs(item.alphaChanges) do
                    Visual.AssertCurrent(change.mesh, row)
                end
            end
            if item.physicsBefore and item.physicsNames then
                physicsChecked += Physics.ApplyLocationModel(model, item.physicsNames, row.meshOptions)
                for _, part in ipairs(meshParts(model)) do
                    if item.physicsNames[part.Name] and Physics.LocationNeedsPhysics(part,row.meshOptions) then
                        error("Location physics Sync failed: "..part.Name)
                    end
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
                model:SetAttribute(SLUG,item.oldSlug)
                model.Name=item.oldName
                model:SetAttribute("Game1DecoAuthoringAnchorPath", item.oldAnchorPath)
                model:SetAttribute(HISTORY, item.oldHistory)
                if item.physicsBefore then Physics.RestoreLocationModel(item.physicsBefore) end
                for _, change in ipairs(item.alphaChanges) do
                    StudioTextureAppearance.Restore(change)
                end
                for _, change in ipairs(item.atlasChanges) do
                    if not item.geometry then
                        Visual.Restore(change.before)
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
        RetiredCleanup.CleanLocation(item.model)
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
        meshPartsUpdated = totalMeshes, physicsUpdated = physicsChecked,
        pendingGeometry = pending, replacedModels = 0,
        changes = summary, instances = instances}
end

return DecoPlacedAssetSync
