-- Studio-only, explicit Location Asset whole-Model replacement.
-- No mesh-to-mesh migration: the target published model is a complete new tree.
-- Source Model/MeshPart transforms are only read. Nothing in the source is edited.
local History = require(script.Parent.StudioPublishedMeshHistory)
local MeshPhysics = require(script.Parent.StudioMeshPhysicsCore)
local Carrier = require(script.Parent.StudioLocationRigCarrier)
local Preparation = require(script.Parent.DecoAssetPreparation)
local Placed = require(script.Parent.DecoPlacedAssetSync)
local Collision = require(script.Parent.StudioLocationCollisionParts)

local GUID_PATTERN = "^[0-9a-fA-F]+%-[0-9a-fA-F]+%-[0-9a-fA-F]+%-[0-9a-fA-F]+%-[0-9a-fA-F]+$"
-- CFrame round-off from ScaleTo/PivotTo should not fail a valid replacement.
-- No intentionally different location or rotation is accepted.
local function sameFrame(a: CFrame, b: CFrame): boolean
    return (a.Position-b.Position).Magnitude <= 0.002
        and a.LookVector:Dot(b.LookVector) >= 0.999999
        and a.UpVector:Dot(b.UpVector) >= 0.999999
end
local function owned(model: Instance, slug: string): boolean
    return model:IsA("Model") and model:GetAttribute("Game1DecoAssetSlug") == slug
        and type(model:GetAttribute("Game1DecoInstanceId")) == "string"
        and #model:GetAttribute("Game1DecoInstanceId") == 36
        and model:GetAttribute("Game1DecoInstanceId"):match(GUID_PATTERN) ~= nil
end

local function visual(item: Instance): boolean
    return item:IsA("MeshPart") and not Carrier.IsCarrier(item)
        and not MeshPhysics.IsCollider(item.Name)
        and item:GetAttribute("Game1DecoPhysicsOnly") ~= true
end

-- The old placed MODEL pivot is the sole destination. Preview lists anchors
-- of the NEW published asset; a target MeshPart pivot can differ from the
-- target Model pivot (including its authored rotation).
local function describeMesh(root: Model, part: MeshPart): string
    local names = {}
    local node: Instance? = part
    while node and node ~= root do
        table.insert(names,1,node.Name)
        node = node.Parent
    end
    return table.concat(names," / ")
end

local function meshAnchors(root: Model): {any}
    local anchors = {}
    for _, part in ipairs(root:GetDescendants()) do
        if visual(part) then
            local meshId = History.Id(part.MeshId)
            if meshId == "" then error("Visual MeshPart is missing Mesh ID") end
            table.insert(anchors,{meshId=meshId,path=describeMesh(root,part),
                frame=part:GetPivot(),size=part.Size})
        end
    end
    if #anchors == 0 then error("Model has no visual MeshParts") end
    return anchors
end

local function anchorOptions(target: Model): ({any}, {[string]: any})
    local options = {{id="model", label="Pivot новой Model"}}
    local approved = {model={}}
    for index, part in ipairs(meshAnchors(target)) do
        local id = "mesh:"..tostring(index)
        table.insert(options,{id=id,label="Pivot нового MeshPart "..index.." · "..part.path,
            meshId=part.meshId})
        approved[id] = {meshId=part.meshId,path=part.path}
    end
    return options,approved
end

local function selectedTargetAnchor(target: Model, anchorId: string,
    approved: {[string]: any}): CFrame
    if anchorId == "model" and approved.model then return target:GetPivot() end
    local expected = approved[anchorId]
    local ordinal = tonumber(anchorId:match("^mesh:(%d+)$"))
    local part = if ordinal then meshAnchors(target)[ordinal] else nil
    if not expected or not part or part.meshId ~= expected.meshId
        or part.path ~= expected.path then
        error("Target MeshPart changed since Preview; preview again")
    end
    return part.frame
end

-- Pure rigid transform: align the selected NEW anchor with the OLD Model pivot.
-- No bounds/size heuristics and no edits to the authored pivots of either asset.
local function positionAtSource(target: Model, sourceFrame: CFrame,
    anchorId: string, approved: {[string]: any})
    local originalModelFrame = target:GetPivot()
    local originalAnchorFrame = selectedTargetAnchor(target,anchorId,approved)
    target:PivotTo(sourceFrame * originalAnchorFrame:Inverse() * originalModelFrame)
    if not sameFrame(selectedTargetAnchor(target,anchorId,approved),sourceFrame) then
        error("Selected target pivot did not align with the source Model pivot")
    end
end

local function versions(catalogRow: any, loader: any): {any}
    local result = {}
    for _, version in ipairs(catalogRow.models or {}) do
        local record = version
        local hasVisual = false
        for _, mesh in ipairs(record.meshes or {}) do
            if type(mesh.visualNames) == "table" and #mesh.visualNames > 0 then
                hasVisual = true
                break
            end
        end
        if not hasVisual then
            local source = loader:loadForMeshInventory(version.modelAssetId,catalogRow.slug)
            local ok, described = pcall(History.Describe,version.modelAssetId,source)
            source:Destroy()
            if not ok then error("Cannot inspect source historical Model: "..tostring(described)) end
            record = described
        end
        table.insert(result, record)
    end
    return result
end

local function meshCounts(model: Model): {[string]: number}
    local result = {}
    for _, child in ipairs(model:GetDescendants()) do
        if visual(child) then
            local meshId = History.Id(child.MeshId)
            if meshId == "" then error("Visual MeshPart has no published Mesh ID") end
            result[meshId] = (result[meshId] or 0) + 1
        end
    end
    return result
end

local function matchesVersion(counts: {[string]: number}, version: any): boolean
    local expected = {}
    for _, mesh in ipairs(version.meshes or {}) do
        if type(mesh.visualNames) == "table" and #mesh.visualNames > 0 then
            expected[mesh.meshId] = (expected[mesh.meshId] or 0) + mesh.count
        end
    end
    local total = 0
    for meshId, count in pairs(counts) do
        total += 1
        if expected[meshId] ~= count then return false end
    end
    if total == 0 then return false end
    local n = 0
    for _ in pairs(expected) do n += 1 end
    return n == total
end

local function proven(model: Model, source: any, sourceVersions: {any}, otherVersions: {any}): boolean
    if not owned(model,source.slug) then return false end
    local published = tostring(model:GetAttribute("Game1DecoPublishedModelAssetId") or "")
    local counts = meshCounts(model)
    local matches = false
    for _, version in ipairs(sourceVersions) do
        if version.modelAssetId == published and matchesVersion(counts,version) then
            matches = true
            break
        end
    end
    if not matches then return false end
    -- Ambiguous FULL visual inventory cannot be auto-replaced.
    for _, versionsForOther in ipairs(otherVersions) do
        for _, version in ipairs(versionsForOther) do
            if matchesVersion(counts,version) then return false end
        end
    end
    return true
end

local function allowedParent(root: Model, world: Workspace): boolean
    if not root:IsDescendantOf(world) then return false end
    if world.CurrentCamera and root:IsDescendantOf(world.CurrentCamera) then return false end
    local ancestor = root.Parent
    while ancestor and ancestor ~= world do
        if ancestor:GetAttribute("Game1RealEstateSlug") ~= nil or ancestor:GetAttribute("Game1PlotHousePreview") == true
            or ancestor:GetAttribute("Game1DecoAssetSlug") ~= nil then return false end
        ancestor = ancestor.Parent
    end
    return true
end

local function snapshot(root: Model): any
    return {root=root, parent=root.Parent, frame=root:GetPivot(), scale=root:GetScale(),
        name=root.Name, identity=root:GetAttribute("Game1DecoInstanceId"),
        publication=root:GetAttribute("Game1DecoPublishedModelAssetId"),
        visual=meshCounts(root), anchors=meshAnchors(root)}
end

local function unchanged(state: any): boolean
    local root = state.root
    if not root.Parent or root.Parent ~= state.parent or not sameFrame(root:GetPivot(), state.frame)
        or root:GetScale() ~= state.scale or root.Name ~= state.name
        or root:GetAttribute("Game1DecoInstanceId") ~= state.identity
        or root:GetAttribute("Game1DecoPublishedModelAssetId") ~= state.publication then return false end
    local current = meshCounts(root)
    for id, count in pairs(state.visual) do if current[id] ~= count then return false end end
    for id in pairs(current) do if state.visual[id] == nil then return false end end
    -- Changes to a manually adjusted MeshPart may not change Model:GetPivot().
    -- Detect them rather than silently using a stale Preview transform.
    local anchors = meshAnchors(root)
    if #anchors ~= #state.anchors then return false end
    for i, anchor in ipairs(anchors) do
        local previous = state.anchors[i]
        if anchor.meshId ~= previous.meshId or anchor.path ~= previous.path
            or not sameFrame(anchor.frame,previous.frame)
            or (anchor.size-previous.size).Magnitude > 0.002 then return false end
    end
    return true
end

local function sourceRoots(config: any, slug: string, scope: string): {Model}
    local results, seen = {}, {}
    local function add(root: Model)
        if not owned(root,slug) or seen[root] then return end
        if not allowedParent(root,config.Workspace) then error("Nested/foreign Location model cannot be replaced") end
        seen[root] = true
        table.insert(results,root)
    end
    if scope == "selected" then
        local selected = config.Selection:Get()
        if #selected == 0 then error("Select placed Location Model instances in Studio") end
        for _, item in ipairs(selected) do
            local cursor = item
            while cursor and cursor ~= config.Workspace do
                if owned(cursor,slug) then
                    add(cursor)
                    break
                end
                cursor = cursor.Parent
            end
            if not cursor or cursor == config.Workspace then
                error("Selection contains an object outside source Location Asset")
            end
        end
    else
        for _, item in ipairs(config.Workspace:GetDescendants()) do
            if owned(item,slug) then add(item) end
            if #results > 1000 then error("More than 1000 replacements; split the operation") end
        end
    end
    table.sort(results, function(a,b) return a:GetFullName()<b:GetFullName() end)
    if #results == 0 then error("No placed instances of source asset in the requested scope") end
    return results
end

local function getRow(catalog: any, slug: string): any
    for _, row in ipairs(catalog.items or {}) do if row.slug == slug then return row end end
    error("Asset is missing from published catalog: "..slug)
end

local function getLiveRow(loader: any, expected: any): any
    local registry = loader:fetchRegistry()
    for _, row in ipairs(registry.items) do
        if row.slug == expected.slug and row.status == "PUBLISHED"
            and tostring(row.model_asset_id or "") == expected.modelAssetId
            and tostring(row.model_published_sha256 or "") == expected.publishedSha
            and tostring(row.appearanceMode or "atlas") == expected.appearanceMode
            and tostring(row.visualMaterial or "SmoothPlastic") == expected.visualMaterial
            and tostring(row.visualColor or "#FFFFFF") == expected.visualColor
            and tonumber(row.collisionBlueprintRevision or 0) == expected.collisionBlueprintRevision
            and tostring(row.collisionBlueprintSha256 or "") == expected.collisionBlueprintSha256 then
            return row
        end
    end
    error("Target asset changed since registry snapshot; retry")
end

local function freshModel(template: Model, target: any, old: any,
    placementId: string, anchorId: string, approved: {[string]: any}): Model
    local clone = template:Clone()
    local ok, failure = pcall(function()
        -- Transfer the authored uniform Model scale, not bounds-derived guesses.
        -- This intentionally does not reinterpret manual child MeshPart Size edits.
        clone:ScaleTo(old.scale)
        positionAtSource(clone,old.frame,anchorId,approved)
        Preparation.PreparePlaced(clone,target.meshOptions,target.surfaceMaterial,
            target.materialDefinition and target.materialDefinition.robloxMaterial)
        Placed.StampPublishedModel(clone,target)
        clone.Name = target.slug.."__"..placementId:sub(1,8)
        clone:SetAttribute("Game1DecoAssetSlug",target.slug)
        clone:SetAttribute("Game1DecoInstanceId",placementId)
        if tonumber(target.collisionBlueprintRevision or 0) > 0 then
            local tx = Collision.Prepare(clone,target.collisionBlueprint,
                target.collisionBlueprintRevision,target.collisionBlueprintSha256)
            local applied, problem = pcall(Collision.Commit,tx)
            if not applied then Collision.Rollback(tx); error(problem) end
            Collision.Finalize(tx)
        end
        if not sameFrame(selectedTargetAnchor(clone,anchorId,approved),old.frame)
            or math.abs(clone:GetScale()-old.scale) > 0.00001 then
            error("Replacement transform or uniform Model scale changed during staging")
        end
    end)
    if not ok then clone:Destroy(); error(tostring(failure)) end
    return clone
end

local function placementIdCounts(world: Workspace): {[string]: number}
    local counts = {}
    for _, obj in ipairs(world:GetDescendants()) do
        if obj:IsA("Model") and allowedParent(obj,world) then
            local value = obj:GetAttribute("Game1DecoInstanceId")
            if type(value) == "string" and value ~= "" then
                counts[value] = (counts[value] or 0) + 1
            end
        end
    end
    return counts
end

-- Duplicated Placement IDs can occur on manually duplicated placed assets.
-- Place Registry Repair may refuse their noncanonical hierarchy. Preview never
-- edits them. Replacement rekeys only selected duplicates, atomically and Undoably.
local function assignPlacementIds(states: {any}, counts: {[string]: number}, http: any): number
    local reserved = {}
    local changed = 0
    for _, state in ipairs(states) do
        state.newIdentity = state.identity
        state.idCount = counts[state.identity] or 0
        if state.idCount ~= 1 then
            local fresh: string
            repeat
                fresh = http:GenerateGUID(false)
            until type(fresh) == "string" and #fresh == 36
                and fresh:match(GUID_PATTERN) ~= nil and not counts[fresh] and not reserved[fresh]
            reserved[fresh] = true
            state.newIdentity = fresh
            changed += 1
        end
    end
    return changed
end

return function(config: any)
    local session: any = nil
    local function execute(command: any): any
        if config.RunService:IsRunning() then error("Studio Edit mode required") end
        local source = getRow(command.catalog,command.sourceSlug)
        local target = getRow(command.catalog,command.targetSlug)
        if source.slug == target.slug or command.scope ~= "selected" and command.scope ~= "all" then
            error("Invalid asset replacement scope")
        end
        if command.phase == "preview" then
            local sourceVersions = versions(source,config.decoManager.loader)
            local otherVersions = {}
            -- Cross-asset ambiguity is checked against known publication inventories.
            -- Do not synchronously download every unrelated historical Model in Place.
            local ownedModelIds = {}
            for _, sourceVersion in ipairs(sourceVersions) do
                ownedModelIds[sourceVersion.modelAssetId] = true
            end
            for _, row in ipairs(command.catalog.items) do
                if row.slug ~= source.slug then
                    local known = {}
                    for _, version in ipairs(row.models or {}) do
                        if ownedModelIds[version.modelAssetId] then
                            error("Different assets share one published Model ID; replacement is ambiguous")
                        end
                        if type(version.meshes) == "table" and #version.meshes > 0 then
                            table.insert(known,version)
                        end
                    end
                    if #known > 0 then table.insert(otherVersions,known) end
                end
            end
            local roots = sourceRoots(config,source.slug,command.scope)
            local states = {}
            for _, root in ipairs(roots) do
                if not proven(root,source,sourceVersions,otherVersions) then
                    error("Unverified or ambiguous source Model: "..root:GetFullName())
                end
                table.insert(states,snapshot(root))
            end
            local counts = placementIdCounts(config.Workspace)
            local rekeyed = assignPlacementIds(states,counts,config.HttpService)
            local targetRow = getLiveRow(config.decoManager.loader,target)
            -- Inspect the NEW published target, not the old placed instances.
            local template = config.decoManager.loader:loadPublished(targetRow)
            local inspected, choices, approved = pcall(anchorOptions,template)
            template:Destroy()
            if not inspected then error("Cannot inspect target pivots: "..tostring(choices)) end
            local token = config.HttpService:GenerateGUID(false)
            session = {token=token,digest=command.catalog.digest,
                source=source.slug,target=target.slug,scope=command.scope,states=states,
                targetRevision=targetRow.revision,anchorOptions=choices,approved=approved,
                rekeyed=rekeyed}
            local placements = {}
            for _, state in ipairs(states) do
                table.insert(placements,{name=state.name,path=state.root:GetFullName(),
                    placementId=state.identity,newPlacementId=state.newIdentity})
            end
            return {count=#states,scanToken=token,placements=placements,
                anchorOptions=choices,reassignedIds=rekeyed}
        end
        if command.phase ~= "replace" then error("Unknown Instance Manager phase") end
        local current = session
        session = nil -- A Replace attempt always invalidates this Preview.
        if not current or command.scanToken ~= current.token
            or command.catalog.digest ~= current.digest
            or command.sourceSlug ~= current.source or command.targetSlug ~= current.target
            or command.scope ~= current.scope or not current.approved[command.anchorId] then
            error("Preview expired; run Preview again")
        end
        -- Selected scope must still contain exactly the same roots; All scope
        -- must still cover all instances, not a stale subset.
        local currentRoots = sourceRoots(config,source.slug,command.scope)
        if #currentRoots ~= #current.states then error("Selection/Place changed since Preview") end
        local expected = {}
        for _, state in ipairs(current.states) do expected[state.root] = true end
        for _, root in ipairs(currentRoots) do if not expected[root] then error("Selection changed since Preview") end end
        local liveCounts = placementIdCounts(config.Workspace)
        for _, state in ipairs(current.states) do
            if not unchanged(state) then error("Source placement changed since Preview: "..state.name) end
            if (liveCounts[state.identity] or 0) ~= state.idCount
                or (state.newIdentity ~= state.identity and liveCounts[state.newIdentity]) then
                error("Placement IDs changed since Preview; preview again")
            end
        end
        local targetRow = getLiveRow(config.decoManager.loader,target)
        if targetRow.revision ~= current.targetRevision then
            error("Target asset changed after Preview; preview again")
        end
        local template = config.decoManager.loader:loadPublished(targetRow)
        local stage = {}
        local staged, failure = pcall(function()
            for _, state in ipairs(current.states) do
                local candidate = freshModel(template,targetRow,state,state.newIdentity,command.anchorId,current.approved)
                table.insert(stage,{before=state,after=candidate})
            end
        end)
        template:Destroy()
        if not staged then
            for _, pair in ipairs(stage) do pair.after:Destroy() end
            error("Replacement staging failed, Place unchanged: "..tostring(failure))
        end
        for _, pair in ipairs(stage) do
            if not unchanged(pair.before) then
                for _, cleanup in ipairs(stage) do cleanup.after:Destroy() end
                error("Source moved during staging; Place unchanged")
            end
        end
        local recording = config.ChangeHistoryService:TryBeginRecording(
            "G1InstanceReplace:"..command.operationId,"Replace Location Asset instances")
        if not recording then
            for _, pair in ipairs(stage) do pair.after:Destroy() end
            error("Studio Undo unavailable; Place unchanged")
        end
        local committed, commitError = pcall(function()
            for _, pair in ipairs(stage) do
                pair.before.root.Parent = nil
                pair.after.Parent = pair.before.parent
                if not sameFrame(selectedTargetAnchor(pair.after,command.anchorId,current.approved),
                    pair.before.frame) or math.abs(pair.after:GetScale()-pair.before.scale) > 0.00001 then
                    error("Replacement target anchor/scale changed during commit")
                end
            end
        end)
        if not committed then
            for _, pair in ipairs(stage) do
                pair.after.Parent = nil
                pair.before.root.Parent = pair.before.parent
            end
            config.ChangeHistoryService:FinishRecording(recording,Enum.FinishRecordingOperation.Cancel)
            for _, pair in ipairs(stage) do pair.after:Destroy() end
            error("Replacement rolled back: "..tostring(commitError))
        end
        -- Do NOT Destroy the originals: ChangeHistoryService cannot undo Destroy().
        -- Their Parent=nil changes are recorded; Studio owns their Undo lifetime.
        local finished, finishError = pcall(config.ChangeHistoryService.FinishRecording,
            config.ChangeHistoryService,recording,Enum.FinishRecordingOperation.Commit)
        if not finished then
            for _, pair in ipairs(stage) do
                pair.after.Parent = nil
                pair.before.root.Parent = pair.before.parent
            end
            pcall(config.ChangeHistoryService.FinishRecording,config.ChangeHistoryService,
                recording,Enum.FinishRecordingOperation.Cancel)
            for _, pair in ipairs(stage) do pair.after:Destroy() end
            error("Undo recording failed; replacement rolled back: "..tostring(finishError))
        end
        local selected = {}
        for _, pair in ipairs(stage) do table.insert(selected,pair.after) end
        config.Selection:Set(selected)
        return {count=#stage,changed=#stage,reassignedIds=current.rekeyed,
            note="Selected NEW pivots aligned to old Model pivots. Ctrl+Z restores originals."}
    end

    return function(command: any)
        if command.project ~= "game1" or command.command ~= "location-instance-replace-v3"
            or command.schemaVersion ~= 3 or type(command.operationId) ~= "string"
            or type(command.catalog) ~= "table" or command.catalog.domain ~= "location_assets"
            or type(command.catalog.digest) ~= "string" then
            warn("[Game1] Invalid Instance Manager command")
            return
        end
        local ok, value = pcall(execute,command)
        local result = {project="game1",command="location-instance-replace-v3",
            schemaVersion=3,operationId=command.operationId,phase=command.phase,
            sourceSlug=command.sourceSlug,targetSlug=command.targetSlug,
            scope=command.scope,anchorId=command.anchorId,
            catalogDigest=command.catalog.digest}
        if ok then result.result=value else result.error=tostring(value):sub(1,950) end
        local sent, response = pcall(config.HttpService.RequestAsync,config.HttpService,{
            Url=config.bridgeUrl.."/location-instance-result",Method="POST",
            Headers={["X-Game1-Token"]=config.bridgeToken,["Content-Type"]="application/json"},
            Body=config.HttpService:JSONEncode(result),
        })
        if not sent or not response.Success then
            warn("[Game1] Instance Manager result failed: "..tostring(if sent then response.Body else response))
        end
    end
end
