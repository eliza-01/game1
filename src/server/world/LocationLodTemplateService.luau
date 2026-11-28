-- Server-owned published prototype cache; client owns all world visuals.
-- Only active in compiled Runtime Places. Bounded by Contract.MaxTargets.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local InsertService = game:GetService("InsertService")
local AssetService = game:GetService("AssetService")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local World = Shared:WaitForChild("world")
local Registry = require(World:WaitForChild("LocationAssetRegistry"))
local Contract = require(World:WaitForChild("LocationRuntimeManifestContract"))
local MeshPhysics = require(World:WaitForChild("MeshPhysicsCore"))
local Workspace = game:GetService("Workspace")
local Policy = require(World:WaitForChild("LocationLodDistancePolicy"))
local CharacterConfig = require(Shared:WaitForChild("character"):WaitForChild("CharacterConfig"))
local StagePlan = require(script.Parent:WaitForChild("LocationTemplateStagePlan"))
local Service = {}
local started = false

local function loadPrototype(assetId, name, expectedParts, allowAssembly)

    -- Prefer owned/shared model assets; fall back to the current API for a
    -- properly permitted third-party asset. No client can submit asset IDs.
    local ok, wrapper = pcall(InsertService.LoadAsset, InsertService, assetId)
    if not ok or not wrapper then
        ok, wrapper = pcall(AssetService.LoadAssetAsync, AssetService, assetId)
    end
    if not ok or not wrapper or not wrapper:IsA("Model") then
        warn("[game1][LOD] model load failed " .. name .. " (" .. tostring(assetId) .. "): " .. tostring(wrapper))
        return nil
    end
    local visual = nil
    local visuals = {}
    local publishedPivot = wrapper:GetPivot()
    local numberVisuals = 0
    for _, part in ipairs(wrapper:GetDescendants()) do
        -- Historical published Model Assets may still contain the retired
        -- col_mesh. M342 removed it from authoring/Studio, not from immutable
        -- Roblox publications. Never include it in a client visual template.
        if part:IsA("MeshPart") and not MeshPhysics.IsLocationCarrier(part)
            and not MeshPhysics.IsCollider(part.Name)
            and part:GetAttribute("Game1DecoPhysicsOnly") ~= true then
            numberVisuals += 1
            visual = part
            table.insert(visuals, part)
        end
    end
    if expectedParts then
        local found = {}
        for _, candidate in ipairs(visuals) do
            if found[candidate.Name] then
                warn("[game1][LOD] duplicate composite part: " .. candidate.Name)
                wrapper:Destroy()
                return nil
            end
            found[candidate.Name] = candidate
        end
        if numberVisuals ~= #expectedParts then
            warn("[game1][LOD] composite model count mismatched: " .. name)
            wrapper:Destroy()
            return nil
        end
        -- Stage only the actual published visual MeshParts. The live
        -- Workspace keeps the authored carrier/bones/lights/fire/sockets;
        -- never stage or execute arbitrary scripts or duplicate emitters.
        local template = Instance.new("Model")
        template.Name = name
        for _, spec in ipairs(expectedParts) do
            local candidate = found[spec.name]
            if not candidate then
                template:Destroy()
                wrapper:Destroy()
                return nil
            end
            -- Do not trust a stale published model with changed Mesh IDs.
            local numeric = tostring(candidate.MeshId):match("(%d+)$")
            if numeric ~= spec.meshId then
                warn("[game1][LOD] published composite Mesh ID mismatch: " .. spec.name)
                template:Destroy()
                wrapper:Destroy()
                return nil
            end
            local copy = candidate:Clone()
            for _, descendant in ipairs(copy:GetDescendants()) do
                if not descendant:IsA("SurfaceAppearance") then
                    descendant:Destroy()
                end
            end
            copy.Name = spec.name
            copy.Anchored = true
            copy.CanCollide = false
            copy.CanTouch = false
            copy.CanQuery = false
            copy.Parent = template
        end
        wrapper:Destroy()
        return template
    end
    -- Location LODs can be authored as several material/geometry meshes.
    -- Keep their original relative transforms and names, never include a rig,
    -- collision mesh, script or effect. Houses/resident effects still use one.
    if allowAssembly and numberVisuals > 1 and numberVisuals <= 64 then
        local assembly = Instance.new("Model")
        assembly.Name = name
        for _, source in ipairs(visuals) do
            local copy = source:Clone()
            for _, descendant in ipairs(copy:GetDescendants()) do
                if not descendant:IsA("SurfaceAppearance") then descendant:Destroy() end
            end
            copy.Anchored = true
            copy.CanCollide = false
            copy.CanTouch = false
            copy.CanQuery = false
            copy.Parent = assembly
        end
        assembly.WorldPivot = publishedPivot
        -- WorldPivot itself is not replicated; carry the authored frame explicitly.
        assembly:SetAttribute("Game1LodPublishedPivot", publishedPivot)
        assembly:SetAttribute("Game1LodVisualCount", numberVisuals)
        wrapper:Destroy()
        print(("[game1][LOD] assembly ready %s (%s) · %d visual MeshParts"):format(name, tostring(assetId), numberVisuals))
        return assembly
    end
    if numberVisuals ~= 1 then
        warn("[game1][LOD] " .. name .. " has " .. numberVisuals .. " visual MeshParts; expected one")
        wrapper:Destroy()
        return nil
    end
    local template = visual:Clone()
    -- Never replicate a loaded model's arbitrary descendants/scripts.
    for _, instance in ipairs(template:GetDescendants()) do
        if not instance:IsA("SurfaceAppearance") then
            instance:Destroy()
        end
    end
    template:SetAttribute("Game1LodSourceName", visual.Name)
    template:SetAttribute("Game1LodPublishedPivot", publishedPivot)
    template.Name = name
    template.Anchored = true
    template.CanCollide = false
    template.CanTouch = false
    template.CanQuery = false
    wrapper:Destroy()
    return template
end

function Service.Start()
    if started then return end
    started = true
    -- Resident cosmetic templates are independent of Place LOD placements.
    -- Stage in both Studio and compiled Runtime using the SAME verified loader.
    require(script.Parent:WaitForChild("LocationResidentTemplateService")).Start(loadPrototype)
    local marker = ReplicatedStorage:FindFirstChild(Contract.MarkerName)
    if not marker then
        require(script.Parent:WaitForChild("StudioLodPreviewTemplates")).Start(loadPrototype)
        return
    end -- compiled Runtime uses only its pinned manifest
    if not marker:IsA("StringValue") then
        warn("[game1][LOD] invalid runtime manifest marker class")
        return
    end
    local manifest, decodeError = Contract.ReadManifest(marker)
    local valid, reason = false, decodeError or "manifest JSON invalid"
    if manifest then valid, reason = Contract.Validate(manifest, Registry) end
    if not valid then
        warn("[game1][LOD] refusing to stage templates: " .. tostring(reason))
        return
    end
    local cache = Instance.new("Folder")
    cache.Name = Contract.TemplateFolder
    cache:SetAttribute("Ready", false)
    cache:SetAttribute("StagingComplete", false)
    cache:SetAttribute("Loaded", 0)
    cache.Parent = ReplicatedStorage
    task.spawn(function()
        -- Spawn locations are a server-side startup hint, not an individual
        -- player's actual camera/root. The client independently reprioritizes.
        local anchors = {}
        for _, object in ipairs(Workspace:GetDescendants()) do
            if object:IsA("SpawnLocation") and object.Enabled then
                anchors[#anchors+1] = object.Position + Vector3.new(0,
                    object.Size.Y * 0.5 + CharacterConfig.RootAnchorOffset + CharacterConfig.SpawnClearance, 0)
            end
        end
        if #anchors == 0 then anchors[1] = Vector3.new(0, CharacterConfig.RootAnchorOffset + 8, 0) end
        local plan = StagePlan.Build(manifest, Registry, Contract.Variants, anchors, Policy.SurfaceDistance)
        local count, expected = 0, #plan
        for _, entry in ipairs(plan) do
            local prototype = loadPrototype(entry.id, entry.name, entry.parts, entry.assembly)
            if prototype then
                prototype.Parent = cache
                count += 1
                cache:SetAttribute("Loaded", count)
            end
        end
        cache:SetAttribute("Expected", expected)
        local ready = count == expected
        cache:SetAttribute("Ready", ready)
        cache:SetAttribute("StagingComplete", true)
        if ready then
            print(("[game1][LOD] %d shared templates ready; %d runtime placements")
                :format(count, #manifest.placements))
        else
            warn(("[game1][LOD] only %d/%d templates loaded; Runtime Place is NOT publish-ready")
                :format(count, expected))
        end
    end)
end

return table.freeze(Service)
