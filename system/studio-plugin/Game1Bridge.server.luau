local AssetService = game:GetService("AssetService")
local HttpService = game:GetService("HttpService")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")
local Selection = game:GetService("Selection")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local CharacterTemplate = require(script.Parent.modules.CharacterTemplate)

local toolbar = plugin:CreateToolbar("game1")
local button = toolbar:CreateButton(
    "Game1ControlCenter",
    "Check the game1 local Control Center host agent",
    "",
    "Control Center"
)
button.ClickableWhenViewportHidden = true
local AGENT_URL = "http://127.0.0.1:43821/api/agent/info"
local AGENT_TOKEN = "Game1LocalControlV1"
local BRIDGE_URL = "http://127.0.0.1:43137"
local BRIDGE_TOKEN = "Game1StudioBridgeV1"

local STUDIO_DEBUG_PREFERENCES_SETTING = "Game1StudioDebugPreferences_v1"
local STUDIO_DEBUG_PREFERENCES_FOLDER = "Game1StudioPreferences"
local STUDIO_DEBUG_PREFERENCE_FIELDS = {
    LastLoadoutArchetype = { key = "lastLoadoutArchetype", valueType = "string" },
    LastLoadoutWeaponSlug = { key = "lastLoadoutWeaponSlug", valueType = "string" },
}

local studioPreferenceFolder: Folder? = nil
local studioPreferenceConnections: { RBXScriptConnection } = {}
local applyingStudioPreferences = false

local function readStudioDebugPreferences(): any
    local ok, value = pcall(function()
        return plugin:GetSetting(STUDIO_DEBUG_PREFERENCES_SETTING)
    end)
    if ok and type(value) == "table" then
        return value
    end
    if not ok then
        warn("[game1 plugin] could not read Studio debug preferences: " .. tostring(value))
    end
    return {}
end

local function writeStudioDebugPreference(key: string, value: any)
    local preferences = readStudioDebugPreferences()
    preferences[key] = value
    local ok, err = pcall(function()
        plugin:SetSetting(STUDIO_DEBUG_PREFERENCES_SETTING, preferences)
    end)
    if not ok then
        warn("[game1 plugin] could not save Studio debug preference: " .. tostring(err))
    end
end

local function disconnectStudioPreferenceBridge()
    for _, connection in ipairs(studioPreferenceConnections) do
        connection:Disconnect()
    end
    table.clear(studioPreferenceConnections)
    studioPreferenceFolder = nil
end

local function attachStudioPreferenceBridge(folder: Folder)
    if studioPreferenceFolder == folder then
        return
    end
    disconnectStudioPreferenceBridge()
    studioPreferenceFolder = folder

    local preferences = readStudioDebugPreferences()
    applyingStudioPreferences = true
    for attributeName, field in pairs(STUDIO_DEBUG_PREFERENCE_FIELDS) do
        local value = preferences[field.key]
        if type(value) ~= field.valueType then
            value = ""
        end
        folder:SetAttribute(attributeName, value)
    end
    applyingStudioPreferences = false

    for attributeName, field in pairs(STUDIO_DEBUG_PREFERENCE_FIELDS) do
        table.insert(studioPreferenceConnections, folder:GetAttributeChangedSignal(attributeName):Connect(function()
            if applyingStudioPreferences then
                return
            end
            local value = folder:GetAttribute(attributeName)
            if type(value) == field.valueType then
                writeStudioDebugPreference(field.key, value)
            end
        end))
    end

    if RunService:IsClient() then
        folder:SetAttribute("ClientPreferencesReady", true)
    end
end

local function syncStudioPreferenceBridge()
    if not RunService:IsRunning() then
        disconnectStudioPreferenceBridge()
        return
    end

    local folder = ReplicatedStorage:FindFirstChild(STUDIO_DEBUG_PREFERENCES_FOLDER)
    if not folder and RunService:IsServer() then
        folder = Instance.new("Folder")
        folder.Name = STUDIO_DEBUG_PREFERENCES_FOLDER
        folder.Parent = ReplicatedStorage
    end
    if folder and folder:IsA("Folder") then
        attachStudioPreferenceBridge(folder)
    end
end

ReplicatedStorage.ChildAdded:Connect(function(child)
    if RunService:IsRunning() and child.Name == STUDIO_DEBUG_PREFERENCES_FOLDER and child:IsA("Folder") then
        attachStudioPreferenceBridge(child)
    end
end)
RunService:GetPropertyChangedSignal("RunState"):Connect(function()
    task.defer(syncStudioPreferenceBridge)
end)
task.defer(syncStudioPreferenceBridge)

local function checkAgent()
    local ok, response = pcall(HttpService.RequestAsync, HttpService, {
        Url = AGENT_URL,
        Method = "GET",
        Headers = { ["X-Control-Token"] = AGENT_TOKEN },
    })
    if not ok then
        warn("[game1 plugin] control center agent is unavailable: " .. tostring(response))
        return
    end
    if not response.Success then
        warn(("[game1 plugin] agent http %d: %s"):format(response.StatusCode, response.Body))
        return
    end
    local decodedOk, data = pcall(HttpService.JSONDecode, HttpService, response.Body)
    if decodedOk then
        print(("[game1 plugin] connected · %s · %s"):format(tostring(data.project), tostring(data.build)))
    else
        print("[game1 plugin] connected")
    end
end
button.Click:Connect(checkAgent)


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
            })
        end
    end

    local applied = 0
    local unmatched = 0
    if #validTextures == 1 then
        local uri = "rbxassetid://" .. validTextures[1].assetId
        for _, mesh in ipairs(meshParts) do
            mesh.TextureID = uri
            applied += 1
        end
    elseif #validTextures > 1 then
        for index, texture in ipairs(validTextures) do
            local matched = false
            for _, mesh in ipairs(meshParts) do
                local meshName = string.lower(mesh.Name)
                if texture.slot ~= "" and string.find(meshName, texture.slot, 1, true) then
                    mesh.TextureID = "rbxassetid://" .. texture.assetId
                    matched = true
                    applied += 1
                end
            end
            if not matched and #validTextures == #meshParts and meshParts[index] then
                meshParts[index].TextureID = "rbxassetid://" .. texture.assetId
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

local function placeMonsterRig(importedRig: Model, destination: Instance, wrapperName: string, assetId: number, metadata: any): (Model, any, any, any)
    wrapperName = validSegment(wrapperName)
    local stats = validateCharacterRig(importedRig)
    local existing = destination:FindFirstChild(wrapperName)
    if existing ~= nil and not existing:IsA("Model") then
        error("monster destination already contains a non-Model instance named " .. wrapperName)
    end
    if existing ~= nil and existing:GetAttribute("Game1MonsterRig") ~= true then
        error("refusing to replace an unmanaged monster Model named " .. wrapperName)
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

    wrapper:SetAttribute("Game1MonsterRig", true)
    wrapper:SetAttribute("Game1PlacementMode", "monster-rig")
    wrapper:SetAttribute("Game1ModelAssetId", tostring(assetId))
    wrapper:SetAttribute("MonsterSlug", tostring(metadata.monsterSlug or wrapperName))
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
        if placementMode ~= "character-controller" and placementMode ~= "weapon-pivot" and placementMode ~= "monster-rig" then
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
        if placementMode == "weapon-pivot" then
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
                monsterSlug = tostring(wrapper:GetAttribute("MonsterSlug") or ""),
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

local MONSTER_SPAWN_AUTHORING_ROOT = "Game1Authoring"
local MONSTER_SPAWN_MARKER_FOLDER = "MonsterSpawns"

local function postMonsterSpawnResult(payload: any)
    local response = HttpService:RequestAsync({
        Url = BRIDGE_URL .. "/monster-spawn-result",
        Method = "POST",
        Headers = {
            ["X-Game1-Token"] = BRIDGE_TOKEN,
            ["Content-Type"] = "application/json",
        },
        Body = HttpService:JSONEncode(payload),
    })
    if not response.Success then
        error("game1 Monster Spawn result bridge rejected response: " .. tostring(response.StatusCode))
    end
end

local function monsterSpawnMarkerFolder(): Folder
    local root = Workspace:FindFirstChild(MONSTER_SPAWN_AUTHORING_ROOT)
    if root and not root:IsA("Folder") then
        error("Workspace." .. MONSTER_SPAWN_AUTHORING_ROOT .. " exists but is not a Folder")
    end
    if not root then
        root = Instance.new("Folder")
        root.Name = MONSTER_SPAWN_AUTHORING_ROOT
        root:SetAttribute("Game1Authoring", true)
        root.Parent = Workspace
    end
    local folder = root:FindFirstChild(MONSTER_SPAWN_MARKER_FOLDER)
    if folder and not folder:IsA("Folder") then
        error(root:GetFullName() .. "." .. MONSTER_SPAWN_MARKER_FOLDER .. " exists but is not a Folder")
    end
    if not folder then
        folder = Instance.new("Folder")
        folder.Name = MONSTER_SPAWN_MARKER_FOLDER
        folder.Parent = root
    end
    return folder :: Folder
end

local function findMonsterSpawnMarker(spawnId: string): Model?
    local root = Workspace:FindFirstChild(MONSTER_SPAWN_AUTHORING_ROOT)
    local folder = root and root:FindFirstChild(MONSTER_SPAWN_MARKER_FOLDER)
    if not folder then
        return nil
    end
    for _, child in ipairs(folder:GetChildren()) do
        if child:IsA("Model") and tostring(child:GetAttribute("SpawnId") or "") == spawnId then
            return child
        end
    end
    return nil
end

local function safeMonsterSpawnMarkerPart(parent: Instance, name: string, size: Vector3, cframe: CFrame, color: Color3, transparency: number): Part
    local part = Instance.new("Part")
    part.Name = name
    part.Anchored = true
    part.CanCollide = false
    part.CanQuery = false
    part.CanTouch = false
    part.CastShadow = false
    part.Material = Enum.Material.Neon
    part.Color = color
    part.Size = size
    part.CFrame = cframe
    part.Transparency = transparency
    part.Parent = parent
    return part
end

local function monsterSpawnMarkerCFrame(position: any, yawDegrees: any): CFrame
    if typeof(position) ~= "table" then
        error("Monster Spawn position is missing")
    end
    local x = tonumber(position.x)
    local y = tonumber(position.y)
    local z = tonumber(position.z)
    if x == nil or y == nil or z == nil then
        error("Monster Spawn position is invalid")
    end
    return CFrame.new(x, y, z) * CFrame.Angles(0, math.rad(tonumber(yawDegrees) or 0), 0)
end

local function monsterSpawnMarkerName(data: any): string
    local name = tostring(data.monsterName or data.monsterSlug or "Monster")
        :gsub("[^%w]+", "_"):gsub("^_+", ""):gsub("_+$", "")
    if name == "" then
        name = "Monster"
    end
    local shortId = tostring(data.spawnId or "spawn"):gsub("^spawn%-", ""):sub(1, 8)
    return string.format("%s_%s", name, shortId)
end

local function createMonsterSpawnMarker(data: any, markerState: string): Model
    local spawnId = tostring(data.spawnId or "")
    if not spawnId:match("^spawn%-%w[%w%-]+$") then
        error("Monster Spawn command has invalid spawnId")
    end
    local preview = markerState == "preview"
    local folder = monsterSpawnMarkerFolder()
    for _, child in ipairs(folder:GetChildren()) do
        if child:IsA("Model") then
            local registeredCopy = not preview and tostring(child:GetAttribute("SpawnId") or "") == spawnId
            local previewCopy = tostring(child:GetAttribute("PreviewForSpawnId") or "") == spawnId
            if registeredCopy or previewCopy then
                child:Destroy()
            end
        end
    end

    local world = monsterSpawnMarkerCFrame(data.position, data.yawDegrees)
    local color = preview and Color3.fromRGB(255, 111, 97) or Color3.fromRGB(66, 214, 177)
    local marker = Instance.new("Model")
    marker.Name = monsterSpawnMarkerName(data)
    marker:SetAttribute("Game1MonsterSpawnMarker", true)
    marker:SetAttribute("SpawnState", markerState)
    marker:SetAttribute("SpawnId", preview and "" or spawnId)
    if preview then
        marker:SetAttribute("PreviewForSpawnId", spawnId)
    end
    marker:SetAttribute("MonsterSlug", tostring(data.monsterSlug or ""))
    marker:SetAttribute("MonsterName", tostring(data.monsterName or ""))
    marker:SetAttribute("MapKey", tostring(data.mapKey or "main"))
    marker:SetAttribute("PlaceId", tonumber(data.placeId) or game.PlaceId)
    marker:SetAttribute("YawDegrees", tonumber(data.yawDegrees) or 0)
    marker:SetAttribute("SpawnRadius", tonumber(data.spawnRadius) or 0)
    marker:SetAttribute("MaxAlive", tonumber(data.maxAlive) or 1)
    marker:SetAttribute("Enabled", data.enabled ~= false)
    marker.Parent = folder

    local point = safeMonsterSpawnMarkerPart(marker, "Point", Vector3.new(0.12, 2.2, 2.2), world * CFrame.Angles(0, 0, math.rad(90)), color, 0.18)
    point.Shape = Enum.PartType.Cylinder
    safeMonsterSpawnMarkerPart(marker, "Direction", Vector3.new(0.22, 0.12, 3.2), world * CFrame.new(0, 0.18, -1.6), color, 0.12)
    local radius = math.max(0, tonumber(data.spawnRadius) or 0)
    if radius > 0.01 then
        local area = safeMonsterSpawnMarkerPart(marker, "Radius", Vector3.new(0.06, radius * 2, radius * 2), world * CFrame.Angles(0, 0, math.rad(90)), color, 0.84)
        area.Shape = Enum.PartType.Cylinder
    end

    local billboard = Instance.new("BillboardGui")
    billboard.Name = "Label"
    billboard.Adornee = point
    billboard.AlwaysOnTop = true
    billboard.LightInfluence = 0
    billboard.Size = UDim2.fromOffset(250, 52)
    billboard.StudsOffsetWorldSpace = Vector3.new(0, 3.2, 0)
    billboard.Parent = marker
    local text = Instance.new("TextLabel")
    text.BackgroundColor3 = Color3.fromRGB(17, 24, 33)
    text.BackgroundTransparency = 0.08
    text.BorderSizePixel = 0
    text.Size = UDim2.fromScale(1, 1)
    text.Font = Enum.Font.GothamSemibold
    text.TextColor3 = Color3.fromRGB(246, 248, 251)
    text.TextSize = 14
    text.TextWrapped = true
    text.Text = string.format("%s\n%s · max %d%s", tostring(data.monsterName or data.monsterSlug or "Monster"), tostring(data.spawnId or ""), tonumber(data.maxAlive) or 1, preview and " · PREVIEW" or "")
    text.Parent = billboard
    local corner = Instance.new("UICorner")
    corner.CornerRadius = UDim.new(0, 7)
    corner.Parent = text

    marker.PrimaryPart = point
    Selection:Set({ marker })
    return marker
end

local function moveMonsterSpawnMarker(marker: Model, position: Vector3, yawDegrees: number)
    local world = monsterSpawnMarkerCFrame({ x = position.X, y = position.Y, z = position.Z }, yawDegrees)
    marker:SetAttribute("YawDegrees", yawDegrees)
    local point = marker:FindFirstChild("Point")
    if point and point:IsA("BasePart") then
        point.CFrame = world * CFrame.Angles(0, 0, math.rad(90))
    end
    local direction = marker:FindFirstChild("Direction")
    if direction and direction:IsA("BasePart") then
        direction.CFrame = world * CFrame.new(0, 0.18, -1.6)
    end
    local radius = marker:FindFirstChild("Radius")
    if radius and radius:IsA("BasePart") then
        radius.CFrame = world * CFrame.Angles(0, 0, math.rad(90))
    end
end

local function monsterSpawnCameraYaw(): number
    local camera = Workspace.CurrentCamera
    local look = camera and camera.CFrame.LookVector or Vector3.new(0, 0, -1)
    return math.deg(math.atan2(-look.X, -look.Z)) % 360
end

local function monsterSpawnPlacementResult(data: any): any
    local expectedPlaceId = tonumber(data.placeId) or 0
    if expectedPlaceId > 0 and game.PlaceId > 0 and expectedPlaceId ~= game.PlaceId then
        error(string.format("Open PlaceId %d does not match Spawn PlaceId %d", game.PlaceId, expectedPlaceId))
    end

    local mouse = plugin:GetMouse()
    local initial = data.position
    local startPosition = Vector3.new(0, 0, 0)
    if typeof(initial) == "table" and tonumber(initial.x) and tonumber(initial.y) and tonumber(initial.z) then
        startPosition = Vector3.new(tonumber(initial.x), tonumber(initial.y), tonumber(initial.z))
    elseif mouse.Target then
        startPosition = mouse.Hit.Position
    end
    local yaw = monsterSpawnCameraYaw()
    data.position = { x = startPosition.X, y = startPosition.Y, z = startPosition.Z }
    data.yawDegrees = yaw
    data.placeId = game.PlaceId
    local preview = createMonsterSpawnMarker(data, "preview")
    local finished = false
    local cancelled = false
    local chosenPosition = startPosition
    local targetName = ""

    plugin:Activate(true)
    local moveConnection = mouse.Move:Connect(function()
        if mouse.Target then
            chosenPosition = mouse.Hit.Position
            yaw = monsterSpawnCameraYaw()
            moveMonsterSpawnMarker(preview, chosenPosition, yaw)
        end
    end)
    local clickConnection = mouse.Button1Down:Connect(function()
        if mouse.Target then
            chosenPosition = mouse.Hit.Position
            targetName = mouse.Target:GetFullName()
            moveMonsterSpawnMarker(preview, chosenPosition, yaw)
            finished = true
        end
    end)
    local inputConnection = UserInputService.InputBegan:Connect(function(input, processed)
        if not processed and input.KeyCode == Enum.KeyCode.Escape then
            cancelled = true
        end
    end)
    local deadline = os.clock() + 295
    repeat
        task.wait(0.05)
    until finished or cancelled or os.clock() >= deadline
    moveConnection:Disconnect()
    clickConnection:Disconnect()
    inputConnection:Disconnect()
    plugin:Deactivate()
    if not finished then
        preview:Destroy()
        error(cancelled and "Monster Spawn placement was cancelled" or "Monster Spawn placement timed out")
    end
    return {
        position = { x = chosenPosition.X, y = chosenPosition.Y, z = chosenPosition.Z },
        yawDegrees = yaw,
        target = targetName,
        markerPath = preview:GetFullName(),
    }
end

local function handleMonsterSpawn(data: any)
    local result = {
        command = "monster-spawn",
        project = "game1",
        schemaVersion = 1,
        action = tostring(data.action or ""),
        operationId = tostring(data.operationId or ""),
        spawnId = tostring(data.spawnId or ""),
        placeId = game.PlaceId,
        universeId = game.GameId,
        placeName = game.Name,
        mapKey = tostring(data.mapKey or "main"),
    }
    local ok, operationError = xpcall(function()
        if tostring(data.project or "") ~= "game1" or tonumber(data.schemaVersion) ~= 1 then
            error("invalid game1 Monster Spawn command")
        end
        local action = tostring(data.action or "")
        if action == "place" then
            local placed = monsterSpawnPlacementResult(data)
            for key, value in pairs(placed) do
                result[key] = value
            end
        elseif action == "upsert" then
            local expectedPlaceId = tonumber(data.placeId) or 0
            if expectedPlaceId > 0 and game.PlaceId > 0 and expectedPlaceId ~= game.PlaceId then
                error(string.format("Open PlaceId %d does not match Spawn PlaceId %d", game.PlaceId, expectedPlaceId))
            end
            local marker = createMonsterSpawnMarker(data, "registered")
            result.markerPath = marker:GetFullName()
            result.synchronized = true
        elseif action == "select" then
            local marker = findMonsterSpawnMarker(tostring(data.spawnId or ""))
            if not marker then
                error("registered Monster Spawn marker was not found in Studio")
            end
            Selection:Set({ marker })
            local root = marker.PrimaryPart
            local camera = Workspace.CurrentCamera
            if root and camera then
                camera.CFrame = CFrame.lookAt(root.Position + Vector3.new(9, 7, 9), root.Position)
            end
            result.markerPath = marker:GetFullName()
            result.synchronized = true
        elseif action == "delete" then
            local spawnId = tostring(data.spawnId or "")
            local marker = findMonsterSpawnMarker(spawnId)
            if marker then
                marker:Destroy()
            end
            for _, child in ipairs(monsterSpawnMarkerFolder():GetChildren()) do
                if child:IsA("Model") and tostring(child:GetAttribute("PreviewForSpawnId") or "") == spawnId then
                    child:Destroy()
                end
            end
            result.deleted = marker ~= nil
            result.synchronized = true
        elseif action == "sync" then
            local folder = monsterSpawnMarkerFolder()
            for _, child in ipairs(folder:GetChildren()) do
                if child:IsA("Model") and child:GetAttribute("Game1MonsterSpawnMarker") == true then
                    child:Destroy()
                end
            end
            local created = 0
            local skipped = 0
            local syncedSpawnIds = {}
            for _, record in ipairs(typeof(data.records) == "table" and data.records or {}) do
                local recordPlaceId = tonumber(record.placeId) or 0
                if recordPlaceId == 0 or game.PlaceId == 0 or recordPlaceId == game.PlaceId then
                    createMonsterSpawnMarker(record, "registered")
                    created += 1
                    table.insert(syncedSpawnIds, tostring(record.spawnId or ""))
                else
                    skipped += 1
                end
            end
            result.synchronized = true
            result.created = created
            result.skipped = skipped
            result.syncedSpawnIds = syncedSpawnIds
        else
            error("unsupported Monster Spawn action: " .. action)
        end
    end, debug.traceback)

    if not ok then
        result.error = tostring(operationError)
        warn("[game1 plugin] Monster Spawn command failed: " .. tostring(operationError))
    end
    local postOk, postError = pcall(postMonsterSpawnResult, result)
    if not postOk then
        warn("[game1 plugin] failed to report Monster Spawn result: " .. tostring(postError))
    end
end

local function pollBridge()
    if RunService:IsRunning() then
        return
    end
    local ok, response = pcall(HttpService.RequestAsync, HttpService, {
        Url = BRIDGE_URL .. "/command",
        Method = "GET",
        Headers = { ["X-Game1-Token"] = BRIDGE_TOKEN },
    })
    if not ok or not response.Success then
        return
    end
    local decodeOk, data = pcall(HttpService.JSONDecode, HttpService, response.Body)
    if not decodeOk or type(data) ~= "table" then
        return
    end
    if data.command == "model-load" then
        handleModelLoad(data)
    elseif data.command == "monster-spawn" then
        handleMonsterSpawn(data)
    end
end

task.spawn(function()
    while true do
        pollBridge()
        task.wait(1)
    end
end)

print("[game1 plugin] loaded · model bridge v10 · animation reimport verification moved to Control Center UI")
