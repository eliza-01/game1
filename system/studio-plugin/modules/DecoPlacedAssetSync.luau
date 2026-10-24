local StudioTextureAppearance = require(script.Parent.StudioTextureAppearance)
local DecoPlacedAssetSync = {}

local ROOT_NAME = "Game1DecoAssets"
local ASSET_SLUG_ATTRIBUTE = "Game1DecoAssetSlug"

local function rowsBySlug(registry: any): { [string]: any }
    local result = {}
    if type(registry) ~= "table" or type(registry.items) ~= "table" then
        return result
    end
    for _, row in ipairs(registry.items) do
        local slug = tostring(row.slug or "")
        if slug ~= "" then
            result[slug] = row
        end
    end
    return result
end

-- Only game1-owned instances are eligible. Scope is by immutable asset slug,
-- never by proximity, name or model shape. Does not load/place/clone anything.
function DecoPlacedAssetSync.RefreshTextures(workspace: Workspace, registry: any, targetSlug: string?, serverStorage: Instance?): any
    local registryRows = rowsBySlug(registry)
    local changedModels, changedParts, matchedModels = 0, 0, 0
    local function updateTree(root: Instance)
        for _, descendant in ipairs(root:GetDescendants()) do
            if descendant:IsA("Model") then
                local slug = tostring(descendant:GetAttribute(ASSET_SLUG_ATTRIBUTE) or "")
                if slug ~= "" and (targetSlug == nil or targetSlug == "" or slug == targetSlug) then
                    local row = registryRows[slug]
                    local numericId = row and tonumber(row.texture_asset_id) or nil
                    if row and tostring(row.status or "") == "PUBLISHED" and numericId and numericId > 0 then
                        matchedModels += 1
                        local uri = "rbxassetid://" .. tostring(math.floor(numericId))
                        local modelChanged = false
                        for _, part in ipairs(descendant:GetDescendants()) do
                            if part:IsA("MeshPart") and StudioTextureAppearance.Apply(part, uri, row.textureUsesAlpha) then
                                changedParts += 1
                                modelChanged = true
                            end
                        end
                        if modelChanged then
                            changedModels += 1
                        end
                    end
                end
            end
        end
    end
    updateTree(workspace)
    if serverStorage ~= nil then
        updateTree(serverStorage)
    end
    return { models = changedModels, parts = changedParts, matchedModels = matchedModels }
end

return DecoPlacedAssetSync
