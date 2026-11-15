-- Server-owned bounded prototype cache. Never creates world visuals on the server.
-- Only active when a Runtime Place contains the compiler-owned manifest marker.
-- Four MeshParts maximum in ReplicatedStorage for the initial two-asset pilot.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local InsertService = game:GetService("InsertService")
local AssetService = game:GetService("AssetService")
local HttpService = game:GetService("HttpService")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local World = Shared:WaitForChild("world")
local Registry = require(World:WaitForChild("LocationAssetRegistry"))
local Contract = require(World:WaitForChild("LocationRuntimeManifestContract"))
local MeshPhysics = require(World:WaitForChild("MeshPhysicsCore"))
local Service = {}
local started = false

local function loadPrototype(assetId, name)
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
        if part:IsA("MeshPart") and not MeshPhysics.IsLocationCarrier(part) then
            numberVisuals += 1
            visual = part
        end
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
    local success, manifest = pcall(HttpService.JSONDecode, HttpService, marker.Value)
    local valid, reason = false, "manifest JSON invalid"
    if success then valid, reason = Contract.Validate(manifest, Registry) end
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
        local count = 0
        for _, slug in ipairs(manifest.targets) do
            local asset = Registry.assets[slug]
            for _, variant in ipairs({"FULL", "LOD1"}) do
                local id = tonumber(variant == "FULL" and asset.modelAssetId or asset.lod1ModelAssetId)
                local name = slug .. "__" .. variant
                local prototype = loadPrototype(id, name)
                if prototype then
                    prototype.Parent = cache
                    count += 1
                    cache:SetAttribute("Loaded", count)
                end
            end
        end
        local ready = count == #manifest.targets * 2
        cache:SetAttribute("Ready", ready)
        if ready then
            print(("[game1][LOD] %d shared templates ready; %d runtime placements")
                :format(count, #manifest.placements))
        else
            warn(("[game1][LOD] only %d/%d templates loaded; Runtime Place is NOT publish-ready")
                :format(count, #manifest.targets * 2))
        end
    end)
end

return table.freeze(Service)
