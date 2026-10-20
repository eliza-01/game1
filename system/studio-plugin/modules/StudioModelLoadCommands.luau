-- Studio model-sync command: validates and imports Character, Monster/NPC and Weapon models.
-- Transport/AssetService dependencies are passed by the Game1Bridge composition root.
local CharacterTemplate = require(script.Parent.CharacterTemplate)
local StudioRealEstateModel = require(script.Parent.StudioRealEstateModel)
local StudioTextureAppearance = require(script.Parent.StudioTextureAppearance)

return function(services)
    local AssetService = services.AssetService
    local HttpService = services.HttpService
    local ServerStorage = services.ServerStorage
    local BRIDGE_URL = services.bridgeUrl
    local BRIDGE_TOKEN = services.bridgeToken

    local function validSegment(value: any): string
        local segment = tostring(value or "")
        if segment == "" or segment == "." or segment == ".." or segment:find("[/\\]") then
            error("invalid ServerStorage path segment")
        end
        return segment
    end

    local function modelLoadDestination(folders: { any }): Instance
        local node: Instance = ServerStorage
        for _, raw in ipairs(folders) do
            local name = validSegment(raw)
            local child = node:FindFirstChild(name)
            if child == nil then
                child = Instance.new("Folder")
                child.Name = name
                child.Parent = node
            elseif not child:IsA("Folder") then
                error("ServerStorage destination contains a non-Folder named " .. name)
            end
            node = child
        end
        return node
    end

    local function modelRigStats(root: Instance): any
        local stats = {
            baseParts = 0,
            bones = 0,
            boneNames = {},
            motor6Ds = 0,
            hasRootPart = false,
            rootPartClass = "",
        }
        local instances = { root }
        for _, descendant in root:GetDescendants() do
            table.insert(instances, descendant)
        end
        for _, instance in instances do
            if instance:IsA("BasePart") then
                stats.baseParts += 1
                if instance.Name == "RootPart" then
                    stats.hasRootPart = true
                    stats.rootPartClass = instance.ClassName
                end
            elseif instance:IsA("Bone") then
                stats.bones += 1
                table.insert(stats.boneNames, instance.Name)
            elseif instance:IsA("Motor6D") then
                stats.motor6Ds += 1
            end
        end
        table.sort(stats.boneNames)
        return stats
    end

    local function validateCharacterRig(root: Instance): any
        local stats = modelRigStats(root)
        if stats.baseParts <= 0 then
            error("character model contains no BasePart geometry")
        end
        if stats.bones + stats.motor6Ds <= 0 then
            error("character mode requires an articulated rig with Bone or Motor6D instances")
        end
        return stats
    end

    local function canonicalRigModel(imported: Instance): Model
        if imported:IsA("Model") then
            return imported
        end
        local model = Instance.new("Model")
        model.Name = "ImportedRig"
        imported.Parent = model
        return model
    end

    local function ensureCharacterHost(wrapper: Model, importedRig: Instance): Animator
        local host = wrapper:FindFirstChildOfClass("AnimationController")
        if host == nil then
            host = importedRig:FindFirstChildWhichIsA("AnimationController", true)
            if host ~= nil then
                host.Parent = wrapper
            else
                host = Instance.new("AnimationController")
                host.Name = "AnimationController"
                host.Parent = wrapper
            end
        end

        local duplicateHosts = {}
        for _, descendant in wrapper:GetDescendants() do
            if descendant:IsA("AnimationController") and descendant ~= host then
                table.insert(duplicateHosts, descendant)
            end
        end
        for _, duplicate in duplicateHosts do
            duplicate:Destroy()
        end

        local animator = host:FindFirstChildOfClass("Animator")
        if animator == nil then
            animator = Instance.new("Animator")
            animator.Name = "Animator"
            animator.Parent = host
        end
        local duplicateAnimators = {}
        for _, descendant in host:GetDescendants() do
            if descendant:IsA("Animator") and descendant ~= animator then
                table.insert(duplicateAnimators, descendant)
            end
        end
        for _, duplicate in duplicateAnimators do
            duplicate:Destroy()
        end
        return animator :: Animator
    end

    local function placeCharacterRig(importedRig: Model, destination: Instance, wrapperName: string, assetId: number): (Model, any, any)
        wrapperName = validSegment(wrapperName)
        local stats = validateCharacterRig(importedRig)
        local existing = destination:FindFirstChild(wrapperName)
        if existing ~= nil and not existing:IsA("Model") then
            error("character destination already contains a non-Model instance named " .. wrapperName)
        end
        if existing ~= nil and existing:GetAttribute("Game1CharacterRig") ~= true then
            error("refusing to replace an unmanaged Model named " .. wrapperName)
        end

        local wrapper = existing :: Model?
        if wrapper == nil then
            wrapper = Instance.new("Model")
            wrapper.Name = wrapperName
            wrapper.Parent = destination
        end

        local previousRig = wrapper:FindFirstChild("ImportedRig")
        if previousRig ~= nil then
            previousRig.Name = "ImportedRig_Previous"
        end
        importedRig.Name = "ImportedRig"
        importedRig.Parent = wrapper

        local hostOk, hostError = pcall(function()
            ensureCharacterHost(wrapper :: Model, importedRig)
        end)
        if not hostOk then
            importedRig:Destroy()
            if previousRig ~= nil then
                previousRig.Name = "ImportedRig"
            elseif existing == nil then
                wrapper:Destroy()
            end
            error(hostError)
        end
        if previousRig ~= nil then
            previousRig:Destroy()
        end

        local _, templateInfo = CharacterTemplate.EnsureCanonicalRoot(wrapper :: Model, importedRig)
        stats = modelRigStats(importedRig)

        wrapper:SetAttribute("Game1CharacterRig", true)
        wrapper:SetAttribute("Game1PlacementMode", "character-controller")
        wrapper:SetAttribute("Game1ModelAssetId", tostring(assetId))
        return wrapper :: Model, stats, templateInfo
    end

    local WEAPON_GRIP_NAME = "Game1WeaponGrip"

    local function weaponReferencePart(model: Model): BasePart?
        if model.PrimaryPart then
            return model.PrimaryPart
        end
        local parts = {}
        for _, descendant in model:GetDescendants() do
            if descendant:IsA("BasePart") then
                table.insert(parts, descendant)
            end
        end
        table.sort(parts, function(left, right)
            return left:GetFullName() < right:GetFullName()
        end)
        return parts[1]
    end

    local function ensureWeaponGrip(model: Model): Attachment
        local referencePart = weaponReferencePart(model)
        if not referencePart then
            error("weapon model contains no BasePart for grip reference")
        end

        for _, descendant in model:GetDescendants() do
            if descendant:IsA("Attachment") and descendant.Name == WEAPON_GRIP_NAME then
                descendant:Destroy()
            end
        end

        -- FBX/Model pivots are editor/runtime state and Model.WorldPivot is not
        -- replicated. Persist the actual grip point as an Attachment instead.
        -- Position comes from the imported model pivot; orientation is deliberately
        -- canonical world XYZ so two visually identical FBX weapons cannot equip
        -- differently only because their hidden Model pivot axes differ.
        local importedPivot = model:GetPivot()
        local canonicalGripWorld = CFrame.new(importedPivot.Position)
        local grip = Instance.new("Attachment")
        grip.Name = WEAPON_GRIP_NAME
        grip.CFrame = referencePart.CFrame:ToObjectSpace(canonicalGripWorld)
        grip:SetAttribute("Game1WeaponGrip", true)
        grip.Parent = referencePart
        model:SetAttribute("Game1WeaponGripMode", "attachment-v1")
        return grip
    end

    local function prepareWeaponModel(model: Model)
        for _, descendant in model:GetDescendants() do
            if descendant:IsA("Humanoid") or descendant:IsA("AnimationController") then
                descendant:Destroy()
            elseif descendant:IsA("BasePart") then
                descendant.Anchored = true
                descendant.CanCollide = false
                descendant.CanTouch = false
                descendant.CanQuery = false
                descendant.Massless = true
            end
        end
        ensureWeaponGrip(model)
    end

    local function applyWeaponTextures(model: Model, textures: { any }): any
        local meshParts = {}
        for _, descendant in model:GetDescendants() do
            if descendant:IsA("MeshPart") then
                table.insert(meshParts, descendant)
            end
        end
        table.sort(meshParts, function(left, right)
            return left:GetFullName() < right:GetFullName()
        end)

        local validTextures = {}
        for _, row in ipairs(textures or {}) do
            local assetId = tonumber(row.assetId)
            if assetId and assetId > 0 then
                table.insert(validTextures, {
                    slot = string.lower(tostring(row.slot or "")),
                    assetId = tostring(math.floor(assetId)),
                    usesAlpha = row.usesAlpha,
                })
            end
        end

        local applied = 0
        local unmatched = 0
        if #validTextures == 1 then
            local uri = "rbxassetid://" .. validTextures[1].assetId
            for _, mesh in ipairs(meshParts) do
                StudioTextureAppearance.Apply(mesh, uri, validTextures[1].usesAlpha)
                applied += 1
            end
        elseif #validTextures > 1 then
            for index, texture in ipairs(validTextures) do
                local matched = false
                for _, mesh in ipairs(meshParts) do
                    local meshName = string.lower(mesh.Name)
                    if texture.slot ~= "" and string.find(meshName, texture.slot, 1, true) then
                        StudioTextureAppearance.Apply(mesh, "rbxassetid://" .. texture.assetId, texture.usesAlpha)
                        matched = true
                        applied += 1
                    end
                end
                if not matched and #validTextures == #meshParts and meshParts[index] then
                    StudioTextureAppearance.Apply(meshParts[index], "rbxassetid://" .. texture.assetId, texture.usesAlpha)
                    matched = true
                    applied += 1
                end
                if not matched then
                    unmatched += 1
                end
            end
        end

        return {
            meshParts = #meshParts,
            textureAssets = #validTextures,
            applied = applied,
            unmatched = unmatched,
        }
    end

    -- Reject incomplete imported NPC skeletons before replacing a working Studio template.
    -- Registration owns the expected names; the plugin never encodes NPC-specific bones.
    local function assertExpectedBones(importedRig: Model, expected: any)
        if typeof(expected) ~= "table" or #expected == 0 then
            return
        end
        local present = {}
        for _, object in importedRig:GetDescendants() do
            if object:IsA("Bone") then
                present[object.Name] = true
            end
        end
        local missing = {}
        for _, name in expected do
            if typeof(name) == "string" and name ~= "" and not present[name] then
                table.insert(missing, name)
            end
        end
        if #missing > 0 then
            table.sort(missing)
            error(("Roblox imported an incomplete skeleton: %d of %d bones missing (%s). "
                .. "Republish the NPC model with the updated bone-survival pipeline and sync again.")
                :format(#missing, #expected, table.concat(missing, ", ", 1, math.min(12, #missing))))
        end
    end

    local function placeMonsterRig(importedRig: Model, destination: Instance, wrapperName: string, assetId: number, metadata: any): (Model, any, any, any)
        wrapperName = validSegment(wrapperName)
        local actorKind = if tostring(metadata.entityKind or "monster") == "npc" then "npc" else "monster"
        local managedAttribute = if actorKind == "npc" then "Game1NpcRig" else "Game1MonsterRig"
        local stats = validateCharacterRig(importedRig)
        assertExpectedBones(importedRig, metadata.expectedBones)
        local existing = destination:FindFirstChild(wrapperName)
        if existing ~= nil and not existing:IsA("Model") then
            error(actorKind .. " destination already contains a non-Model instance named " .. wrapperName)
        end
        if existing ~= nil and existing:GetAttribute(managedAttribute) ~= true then
            error("refusing to replace an unmanaged " .. actorKind .. " Model named " .. wrapperName)
        end

        local wrapper = existing :: Model?
        if wrapper == nil then
            wrapper = Instance.new("Model")
            wrapper.Name = wrapperName
            wrapper.Parent = destination
        end

        local previousRig = wrapper:FindFirstChild("ImportedRig")
        if previousRig ~= nil then
            previousRig.Name = "ImportedRig_Previous"
        end
        importedRig.Name = "ImportedRig"
        importedRig.Parent = wrapper

        local hostOk, hostError = pcall(function()
            ensureCharacterHost(wrapper :: Model, importedRig)
        end)
        if not hostOk then
            importedRig:Destroy()
            if previousRig ~= nil then
                previousRig.Name = "ImportedRig"
            elseif existing == nil then
                wrapper:Destroy()
            end
            error(hostError)
        end
        if previousRig ~= nil then
            previousRig:Destroy()
        end

        local _, templateInfo = CharacterTemplate.EnsureCanonicalRoot(wrapper :: Model, importedRig)
        stats = modelRigStats(importedRig)
        local textureStats = applyWeaponTextures(importedRig, metadata.textures or {})

        wrapper:SetAttribute(managedAttribute, true)
        wrapper:SetAttribute("Game1PlacementMode", "monster-rig")
        wrapper:SetAttribute("Game1ModelAssetId", tostring(assetId))
        wrapper:SetAttribute(if actorKind == "npc" then "NpcSlug" else "MonsterSlug", tostring(metadata.monsterSlug or wrapperName))
        return wrapper :: Model, stats, templateInfo, textureStats
    end

    local function placeWeaponModel(imported: Model, destination: Instance, wrapperName: string, assetId: number, metadata: any): (Model, any)
        wrapperName = validSegment(wrapperName)
        local existing = destination:FindFirstChild(wrapperName)
        if existing ~= nil and (not existing:IsA("Model") or existing:GetAttribute("Game1WeaponTemplate") ~= true) then
            error("refusing to replace unmanaged weapon instance named " .. wrapperName)
        end
        if existing then
            existing:Destroy()
        end

        imported.Name = wrapperName
        prepareWeaponModel(imported)
        imported:SetAttribute("Game1WeaponTemplate", true)
        imported:SetAttribute("Game1ModelAssetId", tostring(assetId))
        imported:SetAttribute("WeaponSlug", tostring(metadata.weaponSlug or wrapperName))
        imported:SetAttribute("WeaponType", tostring(metadata.weaponType or ""))
        imported:SetAttribute("WeaponRarity", tostring(metadata.rarity or ""))
        imported.Parent = destination

        local textureStats = applyWeaponTextures(imported, metadata.textures or {})
        return imported, textureStats
    end

    local function postModelLoadResult(payload: any)
        HttpService:RequestAsync({
            Url = BRIDGE_URL .. "/model-load-result",
            Method = "POST",
            Headers = {
                ["X-Game1-Token"] = BRIDGE_TOKEN,
                ["Content-Type"] = "application/json",
            },
            Body = HttpService:JSONEncode(payload),
        })
    end

    local function handleModelLoad(data: any)
        local result = {
            command = "model-load",
            project = "game1",
            schemaVersion = 1,
            assetId = tostring(data.assetId or ""),
        }
        local ok, operationError = xpcall(function()
            if tostring(data.project or "") ~= "game1" or tonumber(data.schemaVersion) ~= 1 then
                error("invalid game1 model load command")
            end
            local placementMode = tostring(data.placementMode or "")
            if placementMode ~= "character-controller" and placementMode ~= "weapon-pivot" and placementMode ~= "monster-rig" and placementMode ~= "real-estate-rig" then
                error("unsupported game1 model placement mode")
            end
            local assetId = tonumber(data.assetId)
            if assetId == nil or assetId <= 0 then
                error("model load requires a numeric Roblox Asset ID")
            end

            local loaded: Instance? = nil
            local lastError = ""
            for _ = 1, 8 do
                local loadedOk, value = pcall(function()
                    return AssetService:LoadAssetAsync(assetId)
                end)
                if loadedOk and value ~= nil then
                    loaded = value
                    break
                end
                lastError = tostring(value)
                task.wait(2)
            end
            if loaded == nil then
                error("Roblox Model Asset ID " .. tostring(assetId) .. " could not be loaded: " .. lastError)
            end

            -- Same rule as the reference project: strip only the single transport
            -- wrapper returned by AssetService and preserve the uploaded FBX tree.
            local importedRig: Instance = loaded
            local transportChildren = loaded:GetChildren()
            if loaded:IsA("Model") and #transportChildren == 1 then
                importedRig = transportChildren[1]
                importedRig.Parent = nil
                loaded:Destroy()
            end

            local destination = modelLoadDestination(data.destinationFolders or {})
            local normalizedModel = canonicalRigModel(importedRig)
            if placementMode == "real-estate-rig" then
                local wrapper, estateStats = StudioRealEstateModel.Place(
                    normalizedModel, destination, tostring(data.wrapperName or ""), assetId,
                    data.metadata or {}, AssetService
                )
                result.destination = wrapper:GetFullName()
                result.wrapperName = wrapper.Name
                result.realEstateStats = estateStats
                result.importedCount = #wrapper:GetDescendants()
            elseif placementMode == "weapon-pivot" then
                local wrapper, textureStats = placeWeaponModel(
                    normalizedModel,
                    destination,
                    tostring(data.wrapperName or ""),
                    assetId,
                    data.metadata or {}
                )
                result.destination = wrapper:GetFullName()
                result.wrapperName = wrapper.Name
                local grip = wrapper:FindFirstChild(WEAPON_GRIP_NAME, true)
                result.weaponStats = {
                    baseParts = modelRigStats(wrapper).baseParts,
                    textures = textureStats,
                    gripAttachment = grip ~= nil and grip:IsA("Attachment"),
                    gripMode = tostring(wrapper:GetAttribute("Game1WeaponGripMode") or ""),
                }
                result.importedCount = #wrapper:GetDescendants()
            elseif placementMode == "monster-rig" then
                local wrapper, stats, templateInfo, textureStats = placeMonsterRig(
                    normalizedModel,
                    destination,
                    tostring(data.wrapperName or ""),
                    assetId,
                    data.metadata or {}
                )
                result.destination = wrapper:GetFullName()
                result.wrapperName = wrapper.Name
                result.rigStats = stats
                result.template = templateInfo
                result.monsterStats = {
                    textures = textureStats,
                    monsterSlug = tostring(wrapper:GetAttribute("MonsterSlug") or wrapper:GetAttribute("NpcSlug") or ""),
                }
                result.importedCount = #wrapper:GetDescendants()
            else
                local wrapper, stats, templateInfo = placeCharacterRig(
                    normalizedModel,
                    destination,
                    tostring(data.wrapperName or ""),
                    assetId
                )
                result.destination = wrapper:GetFullName()
                result.wrapperName = wrapper.Name
                result.rigStats = stats
                result.template = templateInfo
                result.importedCount = #wrapper:GetDescendants()
            end
        end, debug.traceback)

        if not ok then
            result.error = tostring(operationError)
        end
        local postOk, postError = pcall(postModelLoadResult, result)
        if not postOk then
            warn("[game1 plugin] failed to report model load result: " .. tostring(postError))
        end
    end


    return handleModelLoad
end
