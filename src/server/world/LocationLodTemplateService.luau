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
local Service = {}
local started = false

local function loadPrototype(assetId, name, expectedParts)

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
    local numberVisuals = 0
    for _, part in ipairs(wrapper:GetDescendants()) do
        -- Historical published Model Assets may still contain the retired
        -- col_mesh. M342 removed it from authoring/Studio, not from immutable
        -- Roblox publications. Never include it in a client visual template.
        if part:IsA("MeshPart") and not MeshPhysics.IsLocationCarrier(part)
            and not MeshPhysics.IsCollider(part.Name) then
            numberVisuals += 1
            visual = part
        end
    end
    if expectedParts then
        local found = {}
        for _, candidate in ipairs(wrapper:GetDescendants()) do
            if candidate:IsA("MeshPart") and not MeshPhysics.IsLocationCarrier(candidate)
                and not MeshPhysics.IsCollider(candidate.Name) then
                if found[candidate.Name] then
                    warn("[game1][LOD] duplicate composite part: " .. candidate.Name)
                    wrapper:Destroy()
                    return nil
                end
                found[candidate.Name] = candidate
            end
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
    local marker = ReplicatedStorage:FindFirstChild(Contract.MarkerName)
    if not marker then return end -- never run on editable authoring Place
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
    cache:SetAttribute("Loaded", 0)
    cache.Parent = ReplicatedStorage
    task.spawn(function()
        local count, expected = 0, 0
        for _, slug in ipairs(manifest.targets) do
            local asset = Registry.assets[slug]
            for _, variant in ipairs(Contract.Variants(manifest.modes[slug])) do
                expected += 1
                local id = tonumber(if variant == "FULL" then asset.modelAssetId
                    elseif variant == "LOD1" then asset.lod1ModelAssetId else asset.lod2ModelAssetId)
                local name = slug .. "__" .. variant
                local expectedParts = nil
                if variant == "FULL" then
                    for _, row in ipairs(manifest.placements) do
                        if row.slug == slug and row.components then
                            expectedParts = row.components
                            break
                        end
                    end
                end
                local prototype = loadPrototype(id, name, expectedParts)
                if prototype then
                    prototype.Parent = cache
                    count += 1
                    cache:SetAttribute("Loaded", count)
                end
            end
        end
        if manifest.houses then
            -- Only one compact LOD1 template per house TYPE is replicated.
            -- FULL house geometry is never staged in ReplicatedStorage.
            for slug, profile in manifest.houses.types do
                if profile.mode == "lod1" then
                    expected += 1
                    local name = slug .. "__HOUSE_LOD1"
                    local template = loadPrototype(tonumber(profile.lod1ModelAssetId), name)
                    if template then
                        template.Parent = cache
                        count += 1
                        cache:SetAttribute("Loaded", count)
                    end
                end
            end
        end
        cache:SetAttribute("Expected", expected)
        local ready = count == expected
        cache:SetAttribute("Ready", ready)
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
