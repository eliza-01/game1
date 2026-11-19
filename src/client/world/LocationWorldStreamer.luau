-- Client-only visual ownership. Server-owned placement roots/collision Parts are NEVER modified.
-- Uses immutable compiler snapshot positions; no per-placement server visual clones.
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local HttpService = game:GetService("HttpService")
local Workspace = game:GetService("Workspace")
local Players = game:GetService("Players")
local World = ReplicatedStorage:WaitForChild("Game1Shared"):WaitForChild("world")
local Registry = require(World:WaitForChild("LocationAssetRegistry"))
local Contract = require(World:WaitForChild("LocationRuntimeManifestContract"))
local Policy = require(World:WaitForChild("LocationLodDistancePolicy"))
local Streamer = {}
local started = false
local TICK = 0.25
local MAX_CHANGES_PER_TICK = 8 -- max clone/destroy actions per tick; per-client

local function transform(values)
    return CFrame.new(table.unpack(values))
end

local function paint(mesh, asset)
    -- FULL and LOD1 share one per-mesh authored visual contract.
    local override = if typeof(asset.meshOptions)=="table" then asset.meshOptions[mesh.Name] else nil
    local settings = if typeof(override)=="table" and override.appearanceMode then override else asset
    if settings.appearanceMode == "material" or settings.appearanceMode == "material_atlas" then
        local material = Enum.Material[tostring(settings.visualMaterial)]
        if material then mesh.Material = material end
        local hex = tostring(settings.visualColor or "")
        if hex:match("^#[%x][%x][%x][%x][%x][%x]$") then
            mesh.Color = Color3.fromRGB(tonumber(hex:sub(2, 3), 16),
                tonumber(hex:sub(4, 5), 16), tonumber(hex:sub(6, 7), 16))
        end
        if settings.appearanceMode=="material" then mesh.TextureID="" end
    end
    if settings.appearanceMode=="atlas" or settings.appearanceMode=="material_atlas" then
        if settings.appearanceMode=="atlas" then
            mesh.Material=Enum.Material.SmoothPlastic
            mesh.Color=Color3.new(1,1,1)
        end
        local atlas=tonumber(settings.texture_asset_id or asset.textureAssetId)
        if atlas and atlas>0 and not mesh:FindFirstChildOfClass("SurfaceAppearance") then
            local uri="rbxassetid://"..tostring(math.floor(atlas))
            if mesh.TextureID~=uri then mesh.TextureID=uri end
        end
    end
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
    local marker = ReplicatedStorage:FindFirstChild(Contract.MarkerName)
    if not marker then return end -- authoring play remains untouched
    if not marker:IsA("StringValue") then
        warn("[game1][LOD] bad runtime marker")
        return
    end
    local ok, manifest = pcall(HttpService.JSONDecode, HttpService, marker.Value)
    local valid, reason = false, "invalid JSON"
    if ok then valid, reason = Contract.Validate(manifest, Registry) end
    if not valid then
        warn("[game1][LOD] client refused manifest: " .. tostring(reason))
        return
    end

    local folder = Instance.new("Folder")
    folder.Name = Contract.VisualFolder
    folder.Parent = Workspace -- locally created; never server-owned
    local status = makeStatus()
    local records = {}
    for _, row in ipairs(manifest.placements) do
        table.insert(records, {
            id = row.id, slug = row.slug, pivot = Vector3.new(row.pivot[1], row.pivot[2], row.pivot[3]),
            cframe = transform(row.cframe), size = Vector3.new(table.unpack(row.size)),
            mode = manifest.modes[row.slug], desired = nil, actual = "UNLOADED", part = nil, distance = math.huge,
        })
    end
    local cache = ReplicatedStorage:WaitForChild(Contract.TemplateFolder, 30)
    if not cache then
        warn("[game1][LOD] server template cache missing; runtime visuals disabled")
        if status then status.Text = "Runtime LOD | no server templates" end
        return
    end
    local elapsed = 0
    local lastWarning = 0
    RunService.Heartbeat:Connect(function(dt)
        elapsed += dt
        if elapsed < TICK then return end
        elapsed = 0
        local camera = Workspace.CurrentCamera
        if not camera then return end
        local cameraPosition = camera.CFrame.Position
        local changes = 0
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
            if variant ~= "UNLOADED" and prototype and not prototype:IsA("MeshPart") then
                variant = "UNLOADED" -- invalid cache entry is never instantiated
            end
            if variant ~= record.actual and changes < MAX_CHANGES_PER_TICK then
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
                end
                if record.part then record.part:Destroy() end
                record.part = replacement
                record.actual = if replacement then variant else "UNLOADED"
                changes += 1
            end
        end
        if status then
            local counts = {FULL = 0, LOD1 = 0, LOD2 = 0, UNLOADED = 0}
            for _, record in ipairs(records) do counts[record.actual] += 1 end
            status.Text = ("Runtime LOD | FULL %d · LOD1 %d · LOD2 %d · UNLOADED %d\nTemplates %d/%d · operations/tick %d")
                :format(counts.FULL, counts.LOD1, counts.LOD2, counts.UNLOADED,
                    cache:GetAttribute("Loaded") or 0, cache:GetAttribute("Expected") or 0, changes)
        end
        if cache:GetAttribute("Ready") ~= true and os.clock() - lastWarning > 15 then
            lastWarning = os.clock()
            warn("[game1][LOD] template staging incomplete; never publish this build before visual validation")
        end
    end)
    print(("[game1][LOD] client visual streamer active | %d placements | snapshot %s")
        :format(#records, tostring(manifest.snapshotRevision)))
end

return table.freeze(Streamer)
