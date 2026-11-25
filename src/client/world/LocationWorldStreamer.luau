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
local Appearance = require(World:WaitForChild("RuntimeVisualAppearance"))
local Streamer = {}
local started = false
local TICK = 0.25
local MAX_CHANGES_PER_TICK = 8 -- max clone/destroy actions per tick; per-client
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

local function available(record, candidate, level)
    if not candidate or (record.failedAssemblies and record.failedAssemblies[level] == candidate) then return false end
    if level == "FULL" then
        if record.components then
            if not candidate:IsA("Model") then return false end
            for _, component in ipairs(record.components) do
                local mesh = candidate:FindFirstChild(component.name)
                if not mesh or not mesh:IsA("MeshPart") then return false end
            end
            return true
        end
        return candidate:IsA("MeshPart")
    end
    return LodAssembly.Count(candidate) > 0
end

function Streamer.Start()
    if started then return end
    started = true
    -- Shared visual distance owner: CollectionService supplies exact MeshParts,
    -- while Location LOD continues to use its existing manifest snapshot.
    CollectionService:GetInstanceAddedSignal(VISUAL_TAG):Connect(addVisual)
    CollectionService:GetInstanceRemovedSignal(VISUAL_TAG):Connect(removeVisual)
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
    local cache = nil
    if manifest then
        folder = Instance.new("Folder")
        folder.Name = Contract.VisualFolder
        folder.Parent = Workspace -- locally created; never server-owned
        for _, row in ipairs(manifest.placements) do
            table.insert(records, {
                id = row.id, slug = row.slug, pivot = Vector3.new(row.pivot[1], row.pivot[2], row.pivot[3]),
                cframe = transform(row.cframe), size = Vector3.new(table.unpack(row.size)),
                pivotFrame = transform(row.pivot),
                mode = manifest.modes[row.slug], distances = Policy.WithHysteresis(manifest.assetDistances[row.slug], manifest.hysteresis), desired = nil, actual = "UNLOADED", part = nil, distance = math.huge,
                modelPath = row.modelPath, components = row.components,
            })
            local record = records[#records]
            record.fullBounds = {{CFrame=record.cframe, Size=record.size}}
            if row.components then
                record.fullBounds = {}
                for _, component in ipairs(row.components) do
                    table.insert(record.fullBounds, {CFrame=transform(component.cframe), Size=Vector3.new(table.unpack(component.size))})
                end
            end
        end
        cache = ReplicatedStorage:WaitForChild(Contract.TemplateFolder, 30)
        if not cache then
            warn("[game1][LOD] server template cache missing; runtime visuals disabled")
            manifest = nil
        end
    end
    local houseAdapter = nil
    if manifest and manifest.houses then
        houseAdapter = HouseVisualAdapter.new(manifest.houses, cache, manifest.hysteresis)
    end
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
    RunService.Heartbeat:Connect(function(dt)
        if houseAdapter then houseAdapter:FollowMoving() end
        elapsed += dt
        visualElapsed += dt
        if elapsed < TICK and visualElapsed < VISUAL_INTERVAL then return end
        local camera = Workspace.CurrentCamera
        if not camera then return end
        local cameraPosition = camera.CFrame.Position
        if visualElapsed >= VISUAL_INTERVAL then
            visualElapsed = 0
            if preview then preview:Resolve(cameraPosition) end
            sampleVisuals(cameraPosition, preview)
            if houseAdapter then houseAdapter:Resolve(cameraPosition) end
        end
        if elapsed < TICK then return end
        elapsed = 0
        if preview then
            preview:FollowMoving()
            preview:Step(MAX_CHANGES_PER_TICK)
        end
        if not manifest then return end
        -- Reserve half the existing shared budget for houses so dense Location
        -- placement fields cannot starve the house adapter indefinitely.
        local changes = if houseAdapter then houseAdapter:Step(MAX_CHANGES_PER_TICK // 2) else 0
        for _, record in ipairs(records) do
            local distance = (cameraPosition - record.pivot).Magnitude
            record.distance = distance
            record.desired = Policy.Resolve(distance, record.desired, record.distances, record.mode)
        end
        -- Release stale distant visuals first, then prioritize nearest loads.
        -- Both phases share the same MAX_CHANGES_PER_TICK budget.
        table.sort(records, function(a, b)
            local aUnload = a.desired == "UNLOADED" and a.actual ~= "UNLOADED"
            local bUnload = b.desired == "UNLOADED" and b.actual ~= "UNLOADED"
            if aUnload ~= bUnload then return aUnload end
            return a.distance < b.distance
        end)
        for _, record in ipairs(records) do
            -- Roblox native streaming can independently remove the parent
            -- technical Model. Recover when that root later streams back in.
            if record.part and not record.part:IsDescendantOf(Workspace) then
                record.part = nil
                record.actual = "UNLOADED"
            end
            local variant = record.desired
            local prototype = if variant ~= "UNLOADED"
                then cache:FindFirstChild(record.slug .. "__" .. variant) else nil
            if variant ~= "UNLOADED" and not available(record, prototype, variant) then
                prototype = nil
                -- Never instantiate a partially replicated assembly. Preserve
                -- a valid available detail level while the desired one loads.
                for _, fallback in ipairs({"LOD1", "FULL"}) do
                    local candidate = cache:FindFirstChild(record.slug .. "__" .. fallback)
                    if available(record, candidate, fallback) then prototype = candidate; variant = fallback; break end
                end
                if not prototype then
                    if record.part then continue end
                    variant = "UNLOADED"
                end
            end
            local useAssembly = prototype and variant ~= "FULL"
                and (record.components ~= nil or prototype:IsA("Model"))
            local targetCost = if useAssembly then LodAssembly.Count(prototype)
                elseif variant == "FULL" and record.components then #record.components else 1
            local cost = math.min(MAX_CHANGES_PER_TICK, math.max(1, targetCost, record.visualCost or 1))
            if variant ~= record.actual and changes + cost <= MAX_CHANGES_PER_TICK then
                local replacement = nil
                if useAssembly then
                    local assemblyError
                    replacement, assemblyError = LodAssembly.Create(prototype, record.pivotFrame, record.fullBounds, function(mesh)
                        paint(mesh, Registry.assets[record.slug], true)
                    end)
                    if assemblyError then
                        record.failedAssemblies = record.failedAssemblies or {}
                        record.failedAssemblies[variant] = prototype
                        warn("[game1][LOD] assembly placement failed: " .. record.slug .. " " .. tostring(assemblyError))
                    end
                    if replacement then
                        replacement.Name = record.slug .. "__" .. record.id
                        replacement.Parent = folder
                    end
                elseif prototype and prototype:IsA("MeshPart") then
                    replacement = prototype:Clone()
                    replacement.Name = LodAssembly.SourceName(prototype)
                    replacement.Anchored = true
                    replacement.CanCollide = false
                    replacement.CanTouch = false
                    replacement.CanQuery = false
                    replacement.Size = record.size
                    replacement.CFrame = record.cframe
                    paint(replacement, Registry.assets[record.slug], variant ~= "FULL")
                    replacement.Name = record.slug .. "__" .. record.id
                    replacement.Parent = folder
                elseif variant == "FULL" and record.components and prototype and prototype:IsA("Model") then
                    replacement = LocationCompositeVisual.Create(prototype, record, paint,
                        Registry.assets[record.slug])
                end
                -- If the technical root has not streamed in yet, defer the
                -- swap. Never drop a visible LOD to an empty clone.
                if replacement or variant == "UNLOADED" then
                    if record.part then record.part:Destroy() end
                    record.part = replacement
                    record.visualCost = if replacement then targetCost else nil
                    record.actual = if replacement then variant else "UNLOADED"
                    changes += cost
                end
            end
            -- Effect visibility follows the committed visual state, not a
            -- guessed range or an unavailable published template.
            if record.components then
                LocationCompositeVisual.SetEffects(record, record.actual ~= "UNLOADED")
            end
        end
        if houseAdapter and changes < MAX_CHANGES_PER_TICK then
            changes += houseAdapter:Step(MAX_CHANGES_PER_TICK - changes)
        end
        if cache:GetAttribute("Ready") ~= true and os.clock() - lastWarning > 15 then
            lastWarning = os.clock()
            warn("[game1][LOD] template staging incomplete; never publish this build before visual validation")
        end
    end)
    if manifest then
        print(("[game1][LOD] client visual streamer active | %d placements | snapshot %s")
            :format(#records, tostring(manifest.snapshotRevision)))
    end
end

return table.freeze(Streamer)
