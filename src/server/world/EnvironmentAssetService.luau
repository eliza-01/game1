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
local rootConnections: { RBXScriptConnection } = {}

local function clearConnections()
    for _, connection in ipairs(rootConnections) do
        connection:Disconnect()
    end
    table.clear(rootConnections)
end

local function rebuildRegisteredModels()
    local nextModels = {}
    for model in pairs(definitionsByModel) do
        if model.Parent ~= nil then
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
    if deferRebuild ~= true then
        rebuildRegisteredModels()
    end
end

local function registerModel(model: Model, deferRebuild: boolean?)
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

    definitionsByModel[model] = definition
    EnvironmentAssetVisuals.ApplyModel(model, definition)
    applyStaticRuntimePhysics(model)
    if deferRebuild ~= true then
        rebuildRegisteredModels()
    end
end

local function scanRoot(root: Instance)
    table.clear(definitionsByModel)
    for _, descendant in ipairs(root:GetDescendants()) do
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

    scanRoot(root)
    table.insert(rootConnections, root.DescendantAdded:Connect(function(descendant)
        if descendant:IsA("Model") and tostring(descendant:GetAttribute(LOCATION_ASSET_ID_ATTRIBUTE) or "") ~= "" then
            registerModel(descendant)
        elseif descendant:IsA("BasePart") then
            local model = descendant:FindFirstAncestorOfClass("Model")
            if model and definitionsByModel[model] then
                EnvironmentAssetVisuals.ApplyPart(descendant, definitionsByModel[model])
                descendant.Anchored = true
                descendant.CanQuery = true
            end
        end
    end))
    table.insert(rootConnections, root.DescendantRemoving:Connect(function(descendant)
        if descendant:IsA("Model") and definitionsByModel[descendant] then
            unregisterModel(descendant)
        end
    end))

    print(("[game1][environment] registered %d placed location asset(s)"):format(#registeredModels))
end

return table.freeze(EnvironmentAssetService)
