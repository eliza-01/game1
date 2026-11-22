-- Client-only visual ownership. Server-owned placement roots/collision Parts are NEVER modified.
-- Uses immutable compiler snapshot positions; no per-placement server visual clones.
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
local Players = game:GetService("Players")
local CollectionService = game:GetService("CollectionService")
local World = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("world")
local Registry = require(World:WaitForChild("LocationAssetRegistry"))
local Contract = require(World:WaitForChild("LocationRuntimeManifestContract"))
local Policy = require(World:WaitForChild("LocationLodDistancePolicy"))
local HouseVisualAdapter = require(script.Parent:WaitForChild("HouseVisualAdapter"))
local LocationCompositeVisual = require(script.Parent:WaitForChild("LocationCompositeVisual"))
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

local function paint(mesh, asset)
    -- The per-mesh selection is shared with registered Location Assets.
    local override = if typeof(asset.meshOptions) == "table" then asset.meshOptions[mesh.Name] else nil
    local settings = if typeof(override) == "table" and override.appearanceMode then override else asset
    local ok = Appearance.Apply(mesh, {
        mode = settings.appearanceMode, -- includes material_atlas
        material = settings.visualMaterial,
        color = settings.visualColor,
        textureId = settings.texture_asset_id or asset.textureAssetId,
        alpha = settings.alphaEnabled == true,
    })
    if not ok then warn("[game1][LOD] invalid runtime visual appearance: " .. mesh.Name) end
end

local function makeStatus()
    if not RunService:IsStudio() then return nil end
    local player = Players.LocalPlayer
    if not player then return nil end
    local screen = Instance.new("ScreenGui")
    screen.Name = "Game1RuntimeLodStatus"
    screen.ResetOnSpawn = false
    screen.DisplayOrder = 110
    local label = Instance.new("TextLabel")
    label.Name = "Status"
    label.Position = UDim2.fromOffset(12, 138)
    label.Size = UDim2.fromOffset(430, 49)
    label.BackgroundTransparency = 0.2
    label.BackgroundColor3 = Color3.fromRGB(17, 23, 31)
    label.TextColor3 = Color3.fromRGB(230, 243, 255)
    label.TextSize = 14
    label.TextWrapped = true
    label.TextXAlignment = Enum.TextXAlignment.Left
    label.Text = "Runtime LOD | awaiting templates..."
    label.Parent = screen
    screen.Parent = player:WaitForChild("PlayerGui")
    return label
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
    local status = nil
    local records = {}
    local cache = nil
    if manifest then
        folder = Instance.new("Folder")
        folder.Name = Contract.VisualFolder
        folder.Parent = Workspace -- locally created; never server-owned
        status = makeStatus()
        for _, row in ipairs(manifest.placements) do
            table.insert(records, {
                id = row.id, slug = row.slug, pivot = Vector3.new(row.pivot[1], row.pivot[2], row.pivot[3]),
                cframe = transform(row.cframe), size = Vector3.new(table.unpack(row.size)),
                mode = manifest.modes[row.slug], desired = nil, actual = "UNLOADED", part = nil, distance = math.huge,
                modelPath = row.modelPath, components = row.components,
            })
        end
        cache = ReplicatedStorage:WaitForChild(Contract.TemplateFolder, 30)
        if not cache then
            warn("[game1][LOD] server template cache missing; runtime visuals disabled")
            if status then status.Text = "Runtime LOD | no server templates" end
            manifest = nil
        end
    end
    local houseAdapter = nil
    if manifest and manifest.houses then
        houseAdapter = HouseVisualAdapter.new(manifest.houses, cache)
    end
    local preview = nil
    if not marker and RunService:IsStudio() then
        preview = require(script.Parent:WaitForChild("StudioLodPreviewAdapter")).new(function(part)
            local record = visuals[part]
            return if record then record.original else part.LocalTransparencyModifier
        end)
        status = makeStatus()
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
            if status then
                local counts = preview:Stats()
                status.Text = if preview.digest then
                    ("Studio LOD preview | FULL %d · LOD1 %d · LOD2 %d · UNLOADED %d\nVisual only · profile %s")
                        :format(counts.FULL, counts.LOD1, counts.LOD2, counts.UNLOADED, preview.digest:sub(1,12))
                    else "Studio LOD preview | waiting for local Bridge / Control Center"
            end
        end
        if not manifest then return end
        -- Reserve half the existing shared budget for houses so dense Location
        -- placement fields cannot starve the house adapter indefinitely.
        local changes = if houseAdapter then houseAdapter:Step(MAX_CHANGES_PER_TICK // 2) else 0
        for _, record in ipairs(records) do
            local distance = (cameraPosition - record.pivot).Magnitude
            record.distance = distance
            record.desired = Policy.Resolve(distance, record.desired, manifest.distances, record.mode)
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
            -- During partial template loading we never create a bad fallback geometry.
            if variant ~= "UNLOADED" and not prototype then
                -- During partial staging prefer a lower-detail available template,
                -- never invent a Mesh ID or modify desired distance state.
                for _, fallback in ipairs({"LOD1", "FULL"}) do
                    prototype = cache:FindFirstChild(record.slug .. "__" .. fallback)
                    if prototype then variant = fallback break end
                end
                if not prototype then variant = "UNLOADED" end
            end
            if variant ~= "UNLOADED" and prototype and not prototype:IsA("MeshPart")
                and not (variant == "FULL" and record.components and prototype:IsA("Model")) then
                variant = "UNLOADED" -- invalid cache entry is never instantiated
            end
            -- Composite clones represent multiple real MeshPart operations;
            -- charge them against the existing shared per-tick budget.
            local cost = if record.components then math.min(MAX_CHANGES_PER_TICK,
                math.max(1,#record.components)) else 1
            if variant ~= record.actual and changes + cost <= MAX_CHANGES_PER_TICK then
                local replacement = nil
                if prototype and prototype:IsA("MeshPart") then
                    replacement = prototype:Clone()
                    replacement.Name = record.slug .. "__" .. record.id
                    replacement.Anchored = true
                    replacement.CanCollide = false
                    replacement.CanTouch = false
                    replacement.CanQuery = false
                    replacement.Size = record.size
                    replacement.CFrame = record.cframe
                    paint(replacement, Registry.assets[record.slug])
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
        if status then
            local counts = {FULL = 0, LOD1 = 0, LOD2 = 0, UNLOADED = 0}
            for _, record in ipairs(records) do counts[record.actual] += 1 end
            local houseText = ""
            if houseAdapter then
                local full, lod, unloaded = houseAdapter:Stats()
                houseText = (" | Houses %d / %d / %d"):format(full, lod, unloaded)
            end
            status.Text = ("Runtime LOD | FULL %d · LOD1 %d · LOD2 %d · UNLOADED %d%s\nTemplates %d/%d · operations/tick %d")
                :format(counts.FULL, counts.LOD1, counts.LOD2, counts.UNLOADED, houseText,
                    cache:GetAttribute("Loaded") or 0, cache:GetAttribute("Expected") or 0, changes)
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
