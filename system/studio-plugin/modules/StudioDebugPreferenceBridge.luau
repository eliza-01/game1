-- Studio-only persistence bridge for Test Loadout preferences.
-- Owns plugin settings, replicated attributes and their connections.
return function(services)
    local plugin = services.plugin
    local ReplicatedStorage = services.ReplicatedStorage
    local RunService = services.RunService

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


end
