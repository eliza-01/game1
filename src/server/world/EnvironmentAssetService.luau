local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local WorldShared = Shared:WaitForChild("world")
local LocationAssetRegistry = require(WorldShared:WaitForChild("LocationAssetRegistry"))
local EnvironmentAssetVisuals = require(script.Parent:WaitForChild("EnvironmentAssetVisuals"))

local EnvironmentAssetService = {}

local ROOT_NAME = "Game1DecoAssets"
local LOCATION_ASSET_ID_ATTRIBUTE = "Game1DecoAssetSlug"

local started = false
local definitionsByModel: { [Model]: any } = {}
local registeredModels: { Model } = {}
local registryRevision = 0
local workspaceConnections: { RBXScriptConnection } = {}
local registeredAttributeConnections: { [Model]: RBXScriptConnection } = {}

local function clearConnections()
    for _, connection in ipairs(workspaceConnections) do
        connection:Disconnect()
    end
    table.clear(workspaceConnections)
    for model, connection in pairs(registeredAttributeConnections) do
        connection:Disconnect()
        registeredAttributeConnections[model] = nil
    end
end

local function rebuildRegisteredModels()
    local nextModels = {}
    for model in pairs(definitionsByModel) do
        if model:IsDescendantOf(Workspace) then
            table.insert(nextModels, model)
        end
    end
    table.sort(nextModels, function(left, right)
        return left:GetFullName() < right:GetFullName()
    end)
    registeredModels = nextModels
    registryRevision += 1
end

local function applyStaticRuntimePhysics(model: Model)
    -- Authoring stays editable: DecoManager saves unanchored instances in Studio.
    -- Runtime owns world physics and turns registered location assets into stable
    -- scenery without copying gameplay policy into Instance attributes.
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("BasePart") then
            descendant.Anchored = true
            descendant.CanQuery = true
        end
    end
end

local function unregisterModel(model: Model, deferRebuild: boolean?)
    if definitionsByModel[model] == nil then
        return
    end
    definitionsByModel[model] = nil
    local connection = registeredAttributeConnections[model]
    if connection then
        connection:Disconnect()
        registeredAttributeConnections[model] = nil
    end
    if deferRebuild ~= true then
        rebuildRegisteredModels()
    end
end

local function registerModel(model: Model, deferRebuild: boolean?)
    if not model:IsDescendantOf(Workspace) then
        unregisterModel(model, deferRebuild)
        return
    end
    local locationAssetId = tostring(model:GetAttribute(LOCATION_ASSET_ID_ATTRIBUTE) or "")
    if locationAssetId == "" then
        unregisterModel(model, deferRebuild)
        return
    end

    local definition = LocationAssetRegistry.assets[locationAssetId]
    if type(definition) ~= "table" or tostring(definition.status or "") ~= "PUBLISHED" then
        warn(("[game1][environment] placed asset %s references unknown/unpublished location asset %s")
            :format(model:GetFullName(), locationAssetId))
        unregisterModel(model, deferRebuild)
        return
    end

    local previousDefinition = definitionsByModel[model]
    if previousDefinition == definition then
        return
    end
    definitionsByModel[model] = definition
    -- Only published location assets own a listener. This avoids per-NPC/model
    -- connections across Workspace while supporting changes to registered slugs.
    if registeredAttributeConnections[model] == nil then
        registeredAttributeConnections[model] = model:GetAttributeChangedSignal(LOCATION_ASSET_ID_ATTRIBUTE):Connect(function()
            registerModel(model)
        end)
    end
    EnvironmentAssetVisuals.ApplyModel(model, definition)
    applyStaticRuntimePhysics(model)
    if deferRebuild ~= true then
        rebuildRegisteredModels()
    end
end

local function scanWorkspace()
    table.clear(definitionsByModel)
    for _, descendant in ipairs(Workspace:GetDescendants()) do
        if descendant:IsA("Model") and tostring(descendant:GetAttribute(LOCATION_ASSET_ID_ATTRIBUTE) or "") ~= "" then
            registerModel(descendant, true)
        end
    end
    rebuildRegisteredModels()
end

function EnvironmentAssetService.GetDefinition(model: Model): any?
    return definitionsByModel[model]
end

function EnvironmentAssetService.ResolvePart(part: BasePart): (Model?, any?)
    local cursor: Instance? = part
    while cursor and cursor ~= Workspace do
        if cursor:IsA("Model") then
            local definition = definitionsByModel[cursor]
            if definition ~= nil then
                return cursor, definition
            end
        end
        cursor = cursor.Parent
    end
    return nil, nil
end

-- Consumers receive the service-owned array plus a revision number and must treat
-- the array as read-only. Domain-specific systems (combat, harvesting, etc.) can
-- derive their own filtered indexes without EnvironmentAssetService owning those
-- gameplay rules.
function EnvironmentAssetService.GetRegisteredSnapshot(): ({ Model }, number)
    return registeredModels, registryRevision
end

function EnvironmentAssetService.Start()
    if started then
        return
    end
    started = true

    clearConnections()
    local root = Workspace:FindFirstChild(ROOT_NAME)
    if root == nil then
        root = Instance.new("Folder")
        root.Name = ROOT_NAME
        root.Parent = Workspace
    end

    -- Game1DecoAssets remains the authoring default, not a gameplay boundary.
    -- Published location identity is the Game1DecoAssetSlug attribute anywhere
    -- under Workspace, including arbitrarily nested folders.
    scanWorkspace()
    table.insert(workspaceConnections, Workspace.DescendantAdded:Connect(function(descendant)
        if descendant:IsA("Model") and tostring(descendant:GetAttribute(LOCATION_ASSET_ID_ATTRIBUTE) or "") ~= "" then
            registerModel(descendant)
        elseif descendant:IsA("BasePart") then
            local cursor: Instance? = descendant.Parent
            while cursor and cursor ~= Workspace do
                if cursor:IsA("Model") and definitionsByModel[cursor] then
                    EnvironmentAssetVisuals.ApplyPart(descendant, definitionsByModel[cursor])
                    descendant.Anchored = true
                    descendant.CanQuery = true
                    break
                end
                cursor = cursor.Parent
            end
        end
    end))
    table.insert(workspaceConnections, Workspace.DescendantRemoving:Connect(function(descendant)
        if descendant:IsA("Model") and definitionsByModel[descendant] then
            unregisterModel(descendant)
        end
        -- Removing a containing folder may move a whole authored subtree out
        -- of Workspace. Expire its entries without rescanning all Workspace.
        if descendant:IsA("Folder") then
            local changed = false
            for model in pairs(definitionsByModel) do
                if model:IsDescendantOf(descendant) then
                    unregisterModel(model, true)
                    changed = true
                end
            end
            if changed then
                rebuildRegisteredModels()
            end
        end
    end))

    print(("[game1][environment] registered %d placed location asset(s)"):format(#registeredModels))
end

return table.freeze(EnvironmentAssetService)
