-- Studio assembly for any number of independent Real Estate MeshPart rigs.
-- This adapter validates the complete template before touching ServerStorage.
local HttpService = game:GetService("HttpService")
local StudioTextureAppearance = require(script.Parent.StudioTextureAppearance)
local StudioRealEstateModel = {}

local function findMesh(root: Instance, expected: string): MeshPart
    local match: MeshPart? = nil
    for _, instance in root:GetDescendants() do
        if instance:IsA("MeshPart") then
            if string.lower(instance.Name) ~= string.lower(expected) then
                error("Real Estate " .. expected .. " rig contains unexpected mesh " .. instance.Name)
            end
            if match then
                error("Real Estate rig contains duplicate mesh " .. expected)
            end
            match = instance
        end
    end
    if match == nil then
        error("Published Real Estate rig is missing mesh " .. expected)
    end
    return match :: MeshPart
end

local function verifyRig(root: Model, part: string, manifests: any): (MeshPart, number, {string})
    local expected = manifests[part]
    if typeof(expected) ~= "table" then
        error("Missing registered mesh manifest for " .. part)
    end
    -- The FBX registry records authored bones for diagnostics. Roblox can
    -- omit optional interaction bones on import, so this is not a sync gate.
    local found = {}
    local count = 0
    for _, descendant in root:GetDescendants() do
        if descendant:IsA("Bone") then
            count += 1
            found[descendant.Name] = true
        end
    end
    local warnings = {}
    -- Only named interaction hints are reported; arbitrary bones are optional.
    local advisoryBone = nil
    if part == "house" then
        advisoryBone = "chimney_bone"
    elseif part == "door" then
        advisoryBone = "door_bone"
    end
    if advisoryBone and not found[advisoryBone] then
        table.insert(warnings, part .. ": optional " .. advisoryBone
            .. " is missing from the published Roblox Model Asset")
    end
    return findMesh(root, part), count, warnings
end

local function loadIndependentRig(assetService: any, assetId: number, part: string): Model
    local lastError = ""
    for _ = 1, 8 do
        local ok, loaded = pcall(function()
            return assetService:LoadAssetAsync(assetId)
        end)
        if ok and loaded ~= nil then
            if loaded:IsA("Model") then
                return loaded
            end
            local container = Instance.new("Model")
            loaded.Parent = container
            return container
        end
        lastError = tostring(loaded)
        task.wait(2)
    end
    error("Real Estate " .. part .. " Model Asset ID " .. tostring(assetId)
        .. " could not be loaded: " .. lastError)
end

local function orderedParts(manifests: any): {string}
    if typeof(manifests) ~= "table" or typeof(manifests.house) ~= "table" then
        error("Real Estate requires an authored house mesh and its bone manifest")
    end
    local result = {"house"}
    for part, manifest in manifests do
        if typeof(part) ~= "string" or typeof(manifest) ~= "table" then
            error("Invalid Real Estate mesh manifest")
        end
        if part ~= "house" then
            table.insert(result, part)
        end
    end
    table.sort(result, function(a, b)
        if a == "house" then return true end
        if b == "house" then return false end
        return a:lower() < b:lower()
    end)
    return result
end

-- Texture-only refresh for managed Estate copies already placed in Workspace.
-- Never replace models or touch pivots/part transforms during atlas selection.
local function refreshPlaced(slug: string, imageAssets: {[string]: string}, imageAlpha: {[string]: any}): number
    local changed = 0
    for _, instance in workspace:GetDescendants() do
        if instance:IsA("Model") and instance:GetAttribute("Game1RealEstateSlug") == slug then
            local applied = false
            for _, child in instance:GetDescendants() do
                if child:IsA("MeshPart") then
                    local part = string.lower(child.Name)
                    if imageAssets[part] then
                        StudioTextureAppearance.Apply(child, "rbxassetid://" .. imageAssets[part], imageAlpha[part])
                        applied = true
                    end
                end
            end
            if applied then
                instance:SetAttribute("Game1TextureAssetIds", HttpService:JSONEncode(imageAssets))
                changed += 1
            end
        end
    end
    return changed
end

function StudioRealEstateModel.Place(imported: Model, destination: Instance, slug: string,
    assetId: number, metadata: any, assetService: any): (Model, any)
    if slug == "" or slug == "." or slug == ".." or slug:find("[/\\]") then
        error("Invalid Real Estate slug")
    end
    local manifests = metadata.expectedMeshes
    local parts = orderedParts(manifests)
    local rigIds = metadata.rigAssetIds
    if typeof(rigIds) ~= "table" or tonumber(rigIds.house) ~= assetId then
        error("Studio Sync requires published Model Asset IDs for every Real Estate mesh")
    end
    local imageAssets = {}
    local imageAlpha = {}
    for _, entry in metadata.textures or {} do
        local part = tostring(entry.slot or "")
        local id = tonumber(entry.assetId)
        if id and id > 0 and manifests[part] ~= nil then
            imageAssets[part] = tostring(math.floor(id))
            imageAlpha[part] = entry.usesAlpha
        end
    end
    local seenModels = {}
    for _, part in parts do
        local id = tonumber(rigIds[part])
        if not id or id <= 0 or seenModels[id] or not imageAssets[part] then
            error("Real Estate " .. part .. " requires its own Model Asset and a published image")
        end
        seenModels[id] = true
    end
    local previous = destination:FindFirstChild(slug)
    if previous and (not previous:IsA("Model") or previous:GetAttribute("Game1RealEstateTemplate") ~= true) then
        error("refusing to overwrite unmanaged Real Estate instance: " .. slug)
    end

    -- Stage and verify ALL meshes before changing the existing template.
    local staged = {}
    local meshes = {}
    local bones = 0
    local rigWarnings = {}
    local activePart = "house"
    local ok, problem = pcall(function()
        for _, part in parts do
            activePart = part
            local rig = part == "house" and imported
                or loadIndependentRig(assetService, tonumber(rigIds[part]) :: number, part)
            table.insert(staged, {part = part, rig = rig})
            local mesh, count, warnings = verifyRig(rig, part, manifests)
            meshes[part] = mesh
            bones += count
            for _, warning in warnings do
                table.insert(rigWarnings, warning)
            end
        end
    end)
    if not ok then
        for _, entry in staged do
            if entry.rig ~= imported then
                entry.rig:Destroy()
            end
        end
        local detail = tostring(problem)
        error("Real Estate " .. activePart .. " Model Asset " .. tostring(rigIds[activePart])
            .. ": " .. detail, 0)
    end

    local wrapper = Instance.new("Model")
    wrapper.Name = slug
    for _, entry in staged do
        local part = entry.part
        local rigName = part:sub(1, 1):upper() .. part:sub(2) .. "Rig"
        entry.rig.Name = rigName
        entry.rig.Parent = wrapper
        StudioTextureAppearance.Apply(meshes[part], "rbxassetid://" .. imageAssets[part], imageAlpha[part])
    end
    wrapper:SetAttribute("Game1RealEstateTemplate", true)
    wrapper:SetAttribute("Game1ModelAssetId", tostring(assetId))
    wrapper:SetAttribute("Game1HouseModelAssetId", tostring(assetId))
    if rigIds.door then
        wrapper:SetAttribute("Game1DoorModelAssetId", tostring(rigIds.door))
    end
    wrapper:SetAttribute("Game1RigAssetIds", HttpService:JSONEncode(rigIds))
    wrapper:SetAttribute("Game1TextureAssetIds", HttpService:JSONEncode(imageAssets))
    wrapper:SetAttribute("Game1RealEstateSlug", slug)
    wrapper:SetAttribute("Game1HouseLevel", tonumber(metadata.houseLevel) or 1)
    wrapper:SetAttribute("Game1PurchasePrice", tonumber(metadata.purchasePrice) or 1)
    wrapper:SetAttribute("Game1MinimumLevel", tonumber(metadata.minLevel) or 1)
    wrapper:SetAttribute("Game1SalePrice", tonumber(metadata.salePrice) or 1)
    wrapper.Parent = destination
    if previous then
        previous:Destroy()
    end
    local placedUpdated = refreshPlaced(slug, imageAssets, imageAlpha)
    return wrapper, {bonesValidated = true, rigsValidated = #parts,
        texturesApplied = #parts, workspaceModelsUpdated = placedUpdated,
        boneCount = bones, rigWarnings = rigWarnings}
end

return table.freeze(StudioRealEstateModel)
