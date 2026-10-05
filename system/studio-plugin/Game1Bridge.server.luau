local AssetService = game:GetService("AssetService")
local HttpService = game:GetService("HttpService")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")

local CharacterTemplate = require(script.Parent.modules.CharacterTemplate)

local toolbar = plugin:CreateToolbar("game1")
local button = toolbar:CreateButton("Control Center", "Check the game1 local Control Center host agent", "")
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
        elseif instance:IsA("Motor6D") then
            stats.motor6Ds += 1
        end
    end
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
        if placementMode ~= "character-controller" and placementMode ~= "weapon-pivot" then
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
            result.weaponStats = {
                baseParts = modelRigStats(wrapper).baseParts,
                textures = textureStats,
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
    end
end

task.spawn(function()
    while true do
        pollBridge()
        task.wait(1)
    end
end)

print("[game1 plugin] loaded · model bridge v5 · templates + Studio test loadout preferences")
