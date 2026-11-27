-- Client-only visual ownership. Server-owned placement roots/collision Parts are NEVER modified.
-- Uses immutable compiler snapshot positions; no per-placement server visual clones.
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
local CollectionService = game:GetService("CollectionService")
local World = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("world")
local Registry = require(World:WaitForChild("LocationAssetRegistry"))
local Contract = require(World:WaitForChild("LocationRuntimeManifestContract"))
local Policy = require(World:WaitForChild("LocationLodDistancePolicy"))
local HouseVisualAdapter = require(script.Parent:WaitForChild("HouseVisualAdapter"))
local LocationCompositeVisual = require(script.Parent:WaitForChild("LocationCompositeVisual"))
local LodAssembly = require(script.Parent:WaitForChild("LocationLodAssembly"))
local StaticPlacementIndex = require(script.Parent:WaitForChild("StaticPlacementIndex"))
local LocationLodCandidates = require(script.Parent:WaitForChild("LocationLodCandidates"))
local LodThresholdCache = require(script.Parent:WaitForChild("LodThresholdCache"))
local LodTransitionQueue = require(script.Parent:WaitForChild("LodTransitionQueue"))
local LodPrototypeCache = require(script.Parent:WaitForChild("LodPrototypeCache"))
local LodRuntimeWork = require(script.Parent:WaitForChild("LodRuntimeWork"))
local Appearance = require(World:WaitForChild("RuntimeVisualAppearance"))
local Streamer = {}
local started = false
local active = nil
local TICK = 0.25
local MAX_CHANGES_PER_TICK = 8 -- legacy House/Studio preview budget; Location uses per-frame work units
local VISUAL_TAG = "Game1DistanceVisual"
local VISUAL_INTERVAL = 1 -- one update/second; piggybacks on the existing LOD Heartbeat

local visuals = {} -- CollectionService-maintained, never rescanned in Heartbeat
local function addVisual(part)
    if not part:IsA("MeshPart") or not part:IsDescendantOf(Workspace) then return end
    if visuals[part] ~= nil then return end
    visuals[part] = {visible = nil, original = part.LocalTransparencyModifier}
end
local function removeVisual(part)
    local record = visuals[part]
    if not record then return end
    visuals[part] = nil
    -- Restore if a streamed part moves outside Workspace but later returns.
    if part.Parent then
        part.LocalTransparencyModifier = record.original
    end
end
local function sampleVisuals(cameraPosition, preview)
    for part, record in visuals do
        if not part:IsDescendantOf(Workspace) then
            removeVisual(part)
            continue
        end
        if preview and preview:Owns(part) then record.visible = nil; continue end
        local distanceLimit = part:GetAttribute("Game1VisualDistanceStuds")
        if typeof(distanceLimit) ~= "number" or distanceLimit < 20 or distanceLimit > 1000 then
            -- StreamingEnabled may replicate the tag before its attributes.
            -- Keep the subscription alive until the authoritative range arrives.
            if record.visible == false then
                part.LocalTransparencyModifier = record.original
                record.visible = nil
            end
            continue
        end
        -- Distance to the actual rotated mesh bounding box, not its far-away pivot.
        local localPosition = part.CFrame:PointToObjectSpace(cameraPosition)
        local half = part.Size * 0.5
        local delta = Vector3.new(math.max(math.abs(localPosition.X) - half.X, 0),
            math.max(math.abs(localPosition.Y) - half.Y, 0),
            math.max(math.abs(localPosition.Z) - half.Z, 0))
        local visible = Policy.VisualWithin(delta.Magnitude, record.visible, distanceLimit)
        if record.visible ~= visible then
            part.LocalTransparencyModifier = if visible then record.original else 1
            record.visible = visible
        end
    end
end

local function transform(values)
    return CFrame.new(table.unpack(values))
end

local function componentsSignature(components)
    if not components then return nil end
    local names = {}
    for _, component in ipairs(components) do table.insert(names, component.name) end
    return table.concat(names, "\30")
end

local missingAppearance = {}
local function paint(mesh, asset, reduced)
    -- The per-mesh selection is shared with registered Location Assets.
    local override = if typeof(asset.meshOptions) == "table" then asset.meshOptions[mesh.Name] else nil
    if reduced and not override and typeof(asset.meshOptions) == "table" then
        local name = LodAssembly.AppearanceName(mesh, asset.meshOptions)
        override = name and asset.meshOptions[name]
        if not override then
            local only, count = nil, 0
            for _, options in pairs(asset.meshOptions) do only = options; count += 1 end
            if count == 1 then override = only
            elseif count > 1 then
                -- No arbitrary first material on a multi-material LOD. Keep
                -- the publication appearance and diagnose an unmapped name.
                local key = asset.slug .. "/" .. mesh.Name
                if not missingAppearance[key] then
                    missingAppearance[key] = true
                    warn("[game1][LOD] no FULL appearance match: " .. key)
                end
                return
            end
        end
    end
    local settings = if typeof(override) == "table" and override.appearanceMode then override else asset
    local ok = Appearance.Apply(mesh, {
        mode = settings.appearanceMode, -- includes material_atlas
        material = settings.visualMaterial,
        color = settings.visualColor,
        textureId = settings.texture_asset_id or asset.textureAssetId,
        alpha = settings.alphaEnabled == true,
    })
    if typeof(settings.doubleSided) == "boolean" then mesh.DoubleSided = settings.doubleSided end
    if not ok then warn("[game1][LOD] invalid runtime visual appearance: " .. mesh.Name) end
end

local function available(record, status, candidate, metadata, level)
    if status ~= "ready" or not candidate or not metadata then return false end
    local failed = record.failedAssemblies and record.failedAssemblies[level]
    local failedGeneration = record.failedAssemblyGenerations and record.failedAssemblyGenerations[level]
    if failed == candidate and failedGeneration == metadata.generation then return false end
    if level == "FULL" then
        if record.components then
            return candidate:IsA("Model") and metadata.kind == "composite"
        end
        return candidate:IsA("MeshPart") and metadata.kind == "meshpart"
    end
    return metadata.count > 0 and (candidate:IsA("MeshPart") or candidate:IsA("Model"))
end


function Streamer.Start()
    if started then return end
    started = true
    -- Shared visual distance owner: CollectionService supplies exact MeshParts,
    -- while Location LOD continues to use its existing manifest snapshot.
    local visualAddedConnection = CollectionService:GetInstanceAddedSignal(VISUAL_TAG):Connect(addVisual)
    local visualRemovedConnection = CollectionService:GetInstanceRemovedSignal(VISUAL_TAG):Connect(removeVisual)
    for _, part in ipairs(CollectionService:GetTagged(VISUAL_TAG)) do addVisual(part) end

    local manifest = nil
    local marker = ReplicatedStorage:FindFirstChild(Contract.MarkerName)
    if marker and marker:IsA("StringValue") then
        local candidate, decodeError = Contract.ReadManifest(marker)
        local valid, reason = false, decodeError or "invalid JSON"
        if candidate then valid, reason = Contract.Validate(candidate, Registry) end
        if valid then
            manifest = candidate
        else
            warn("[game1][LOD] client refused manifest: " .. tostring(reason))
        end
    elseif marker then
        warn("[game1][LOD] bad runtime marker")
    end

    local folder = nil
    local records = {}
    local composites = {}
    local candidates = nil
    local queue = nil
    local prototypeCache = nil
    local prototypeChangedConnection = nil
    local runtimeWork = LodRuntimeWork.new()
    if manifest then
        folder = Instance.new("Folder")
        folder.Name = Contract.VisualFolder
        folder.Parent = Workspace -- locally created; never server-owned
        for _, row in ipairs(manifest.placements) do
            table.insert(records, {
                order = #records + 1, id = row.id, slug = row.slug, pivot = Vector3.new(row.pivot[1], row.pivot[2], row.pivot[3]),
                cframe = transform(row.cframe), size = Vector3.new(table.unpack(row.size)),
                pivotFrame = transform(row.pivot),
                mode = manifest.modes[row.slug], distances = Policy.WithHysteresis(manifest.assetDistances[row.slug], manifest.hysteresis), desired = nil, actual = "UNLOADED", part = nil, distance = math.huge,
                modelPath = row.modelPath, components = row.components,
                componentContract = componentsSignature(row.components),
                prototypeDirty = true, prototypeDesired = nil, prototypeActual = nil,
                actualPrototype = nil, actualPrototypeGeneration = nil,
            })
            local record = records[#records]
            record.fullBounds = {{CFrame=record.cframe, Size=record.size}}
            if row.components then
                table.insert(composites, record)
                record.fullBounds = {}
                for _, component in ipairs(row.components) do
                    table.insert(record.fullBounds, {CFrame=transform(component.cframe), Size=Vector3.new(table.unpack(component.size))})
                end
            end
        end
        queue = LodTransitionQueue.new(LocationLodCandidates.SortTransitions)
        prototypeCache = LodPrototypeCache.new(ReplicatedStorage, Contract.TemplateFolder, LodAssembly)
        local dependentsByName = {}
        for _, record in ipairs(records) do
            for _, variantName in ipairs({"FULL", "LOD1", "LOD2"}) do
                local name = record.slug .. "__" .. variantName
                local dependents = dependentsByName[name]
                if not dependents then
                    dependents = {}
                    dependentsByName[name] = dependents
                end
                dependents[record] = true
            end
        end
        prototypeChangedConnection = prototypeCache:ConnectChanged(function(name)
            for record in pairs(dependentsByName[name] or {}) do
                record.prototypeDirty = true
                record.prototypeEpoch = (record.prototypeEpoch or 0) + 1
            end
        end)
    end
    local houseAdapter = nil
    if manifest and manifest.houses then
        houseAdapter = HouseVisualAdapter.new(manifest.houses, prototypeCache, manifest.hysteresis, records)
    end
    if manifest then candidates = LocationLodCandidates.new(StaticPlacementIndex.new(records)) end
    local preview = nil
    if not marker and RunService:IsStudio() then
        preview = require(script.Parent:WaitForChild("StudioLodPreviewAdapter")).new(function(part)
            local record = visuals[part]
            return if record then record.original else part.LocalTransparencyModifier
        end, paint)
    end
    local elapsed = 0
    local visualElapsed = VISUAL_INTERVAL -- first distance test immediately
    local lastWarning = 0
    local lastCamera = nil
    local cameraPosition = nil
    local callbacks = {}
    function callbacks.valid(transition, job)
        local record = transition.record
        if queue.entries[record] ~= transition or transition.desired ~= record.desired
            or transition.actual ~= record.actual or (transition.attemptTick == queue.tick and not job) then return false end
        -- Recheck active work against the current camera, even between observations.
        if LodThresholdCache.ResolveAt(record, LodThresholdCache.Measure(record, cameraPosition, Policy),
            Policy, record.desired) ~= transition.desired then return false end
        if transition.prototype then
            local cacheFolder = prototypeCache:Folder()
            if not cacheFolder or transition.prototype.Parent ~= cacheFolder then return false end
        end
        if record.house then return houseAdapter:Valid(transition, job) end
        if transition.epoch ~= (record.prototypeEpoch or 0) then return false end
        if job and job.root and not LocationCompositeVisual.RootAlive(job, record) then return false end
        return true
    end
    function callbacks.prepare(transition)
        queue:Attempted(transition)
        transition.attemptTick = queue.tick
        local record, variant, prototype = transition.record, transition.variant, transition.prototype
        if record.house then return houseAdapter:Prepare(transition) end
        local asset = Registry.assets[record.slug]
        local job, reason
        if variant ~= "FULL" and (record.components or prototype:IsA("Model")) then
            job, reason = LodAssembly.Prepare(prototype, record.pivotFrame, record.fullBounds, function(mesh)
                paint(mesh, asset, true)
            end, transition.metadata)
        elseif prototype:IsA("MeshPart") then
            job = LodAssembly.PrepareSingle(prototype, record, function(mesh)
                paint(mesh, asset, variant ~= "FULL")
            end)
        elseif variant == "FULL" and record.components then
            job, reason = LocationCompositeVisual.Prepare(prototype, record, paint, asset, transition.metadata)
        end
        return job, reason, reason == "root unavailable" or reason == "component unavailable"
    end
    function callbacks.failed(transition, reason, retryable)
        local record, variant, prototype = transition.record, transition.variant, transition.prototype
        transition.attemptTick = queue.tick
        if record.house then houseAdapter:Failed(transition, reason, retryable); return end
        if retryable then return end
        record.failedAssemblies = record.failedAssemblies or {}
        record.failedAssemblies[variant] = prototype
        record.failedAssemblyGenerations = record.failedAssemblyGenerations or {}
        record.failedAssemblyGenerations[variant] = transition.metadata and transition.metadata.generation
        record.prototypeDirty = true
        queue:Remove(record)
        warn("[game1][LOD] assembly placement failed: " .. record.slug .. " " .. tostring(reason))
    end
    function callbacks.commit(transition, job, work)
        local record, variant, prototype = transition.record, transition.variant, transition.prototype
        if record.house then
            local ok, reason, retryable = houseAdapter:Commit(transition, job, work)
            if ok then queue:Remove(record) end
            return ok, reason, retryable
        end
        local replacement = job and job.bundle
        if replacement then
            local ok, bound = pcall(function()
                if job.root and not LocationCompositeVisual.BindForCommit(job, record) then return false end
                if not job.root then replacement.Name = record.slug .. "__" .. record.id end
                replacement.Parent = job.root or folder
                return true
            end)
            if not ok then return false, bound, false end
            if not bound then return false, "component unavailable at commit", true end
            job:Release()
        end
        -- No yield between publishing the new bundle and detaching the old one.
        -- Only local visual bundles enter retirement, never the technical root.
        if record.part then work:Retire(record.part) end
        record.part = replacement
        record.detached = nil
        record.actual = if replacement then variant else "UNLOADED"
        record.actualPrototype = if replacement then prototype else nil
        record.actualPrototypeGeneration = if replacement then transition.metadata.generation else nil
        if replacement and record.failedAssemblies then
            record.failedAssemblies[variant] = nil
            if record.failedAssemblyGenerations then record.failedAssemblyGenerations[variant] = nil end
        end
        record.prototypeResolvedActual = record.actual
        record.prototypeActual = record.actual
        queue:Remove(record)
        if record.components then LocationCompositeVisual.SetEffects(record, record.actual ~= "UNLOADED") end
        return true
    end
    local heartbeatConnection = RunService.Heartbeat:Connect(function(dt)
        if houseAdapter then houseAdapter:FollowMoving() end
        elapsed += dt
        visualElapsed += dt
        local camera = Workspace.CurrentCamera
        if not camera then runtimeWork:Cancel(); runtimeWork:Cleanup(runtimeWork.CleanupBudget); return end
        cameraPosition = camera.CFrame.Position
        if visualElapsed >= VISUAL_INTERVAL then
            visualElapsed = 0
            if preview then preview:Resolve(cameraPosition) end
            sampleVisuals(cameraPosition, preview)
        end
        if elapsed < TICK then
            if manifest then runtimeWork:Step(callbacks) end
            return
        end
        elapsed = 0
        if preview then
            preview:FollowMoving()
            preview:Step(MAX_CHANGES_PER_TICK)
        end
        if not manifest then return end
        local cameraChanged = lastCamera ~= camera
        lastCamera = camera
        queue:Begin(cameraPosition, cameraChanged)
        local localRecords = candidates:Collect(cameraPosition, cameraChanged)
        local deferredEffects = {}
        for _, record in ipairs(localRecords) do
            local previousDesired = record.desired
            LodThresholdCache.Resolve(record, cameraPosition, Policy, cameraChanged)
            if record.house then
                houseAdapter:Observe(record, previousDesired, queue)
                continue
            end
            if record.desired ~= previousDesired then record.prototypeDirty = true end
            -- Roblox native streaming can independently remove the parent
            -- technical Model. Recover when that root later streams back in.
            if record.part and not record.detached and not record.part:IsDescendantOf(Workspace) then
                -- Retain ownership until the bounded retirement path disposes it.
                if record.part.Parent then record.part.Parent = nil end
                record.detached = true
                record.actual = "UNLOADED"
                record.actualPrototype = nil
                record.actualPrototypeGeneration = nil
                record.prototypeDirty = true
            end
            if record.prototypeDirty or record.prototypeDesired ~= record.desired
                or record.prototypeActual ~= record.actual then
                record.prototypeDirty = false
                record.prototypeDesired = record.desired
                record.prototypeActual = record.actual
                local variant = record.desired
                local prototype, metadata = nil, nil
                local retryPrototypes = false
                local status = "missing"
                if variant ~= "UNLOADED" then
                    status, prototype, metadata = prototypeCache:Resolve(
                        record.slug .. "__" .. variant, variant, record.components, record.componentContract)
                    retryPrototypes = status == "incomplete"
                        or (status == "missing" and prototypeCache:FolderReady() == false)
                end
                if variant ~= "UNLOADED" and not available(record, status, prototype, metadata, variant) then
                    prototype, metadata = nil, nil
                    -- Preserve the existing fallback order. Cache readiness is
                    -- structural and shared; the placement contract stays local.
                    for _, fallback in ipairs({"LOD1", "FULL"}) do
                        local fallbackComponents = if fallback == "FULL" then record.components else nil
                        local fallbackContract = if fallback == "FULL" then record.componentContract else nil
                        local fallbackStatus, candidate, candidateMetadata = prototypeCache:Resolve(
                            record.slug .. "__" .. fallback, fallback, fallbackComponents, fallbackContract)
                        if fallbackStatus == "incomplete"
                            or (fallbackStatus == "missing" and prototypeCache:FolderReady() == false) then
                            retryPrototypes = true
                        end
                        if available(record, fallbackStatus, candidate, candidateMetadata, fallback) then
                            prototype, metadata, variant = candidate, candidateMetadata, fallback
                            break
                        end
                    end
                    if not prototype then
                        if record.part and not record.detached and record.components then deferredEffects[record] = true end
                        if record.part and not record.detached then
                            record.prototypeDirty = retryPrototypes
                            queue:Remove(record)
                            continue
                        end
                        variant = "UNLOADED"
                    end
                end
                local force = (variant == "UNLOADED" and record.detached == true)
                    or (variant == record.actual and record.part ~= nil and prototype ~= nil
                    and (record.actualPrototype ~= prototype
                        or record.actualPrototypeGeneration ~= metadata.generation))
                record.prototypeDirty = retryPrototypes
                queue:Set(record, variant, prototype, metadata, force)
                if queue.entries[record] then queue.entries[record].epoch = record.prototypeEpoch or 0 end
            end
        end
        runtimeWork:Begin(queue:Ordered(function(record, position)
            return LodThresholdCache.Distance(record, position, Policy)
        end))
        runtimeWork:Step(callbacks)
        candidates:Retain(localRecords)
        -- Keep the existing effect lifecycle for every composite, including
        -- distant roots that may stream in late. Do not tie effect visibility
        -- to candidate membership. Event-driven invalidation is a later phase.
        for _, record in ipairs(composites) do
            if not deferredEffects[record] then
                LocationCompositeVisual.SetEffects(record, record.actual ~= "UNLOADED")
            end
        end
        if prototypeCache:FolderReady() ~= true and os.clock() - lastWarning > 15 then
            lastWarning = os.clock()
            warn("[game1][LOD] template staging incomplete; never publish this build before visual validation")
        end
    end)
    active = {heartbeatConnection = heartbeatConnection, visualAddedConnection = visualAddedConnection,
        visualRemovedConnection = visualRemovedConnection, prototypeCache = prototypeCache,
        prototypeChangedConnection = prototypeChangedConnection, houseAdapter = houseAdapter,
        folder = folder, records = records, composites = composites, preview = preview, runtimeWork = runtimeWork}
    if manifest then
        print(("[game1][LOD] client visual streamer active | %d placements | snapshot %s")
            :format(#records, tostring(manifest.snapshotRevision)))
    end
end


function Streamer.Stop()
    if not started then return end
    started = false
    local state = active
    active = nil
    if not state then return end
    for _, connection in ipairs({state.heartbeatConnection, state.visualAddedConnection, state.visualRemovedConnection,
        state.prototypeChangedConnection}) do
        if connection then pcall(function() connection:Disconnect() end) end
    end
    if state.runtimeWork then state.runtimeWork:Destroy() end
    if state.houseAdapter then state.houseAdapter:Destroy() end
    if state.prototypeCache then state.prototypeCache:Destroy() end
    if state.preview and state.preview.Destroy then state.preview:Destroy() end
    for _, record in ipairs(state.records or {}) do
        if record.part then record.part:Destroy(); record.part = nil end
        record.actual = "UNLOADED"
        record.actualPrototype = nil
        record.actualPrototypeGeneration = nil
    end
    for _, record in ipairs(state.composites or {}) do
        LocationCompositeVisual.SetEffects(record, true)
    end
    for part in pairs(visuals) do removeVisual(part) end
    if state.folder then state.folder:Destroy() end
end

return table.freeze(Streamer)
