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

function DecoPlacedAssetSync.RefreshTextures(workspace: Workspace, registry: any): any
    local root = workspace:FindFirstChild(ROOT_NAME)
    if root == nil then
        return { models = 0, parts = 0 }
    end

    local registryRows = rowsBySlug(registry)
    local changedModels = 0
    local changedParts = 0
    for _, descendant in ipairs(root:GetDescendants()) do
        if descendant:IsA("Model") then
            local slug = tostring(descendant:GetAttribute(ASSET_SLUG_ATTRIBUTE) or "")
            local row = registryRows[slug]
            local numericId = row and tonumber(row.texture_asset_id) or nil
            if row and tostring(row.status or "") == "PUBLISHED" and numericId and numericId > 0 then
                local uri = "rbxassetid://" .. tostring(math.floor(numericId))
                local modelChanged = false
                for _, part in ipairs(descendant:GetDescendants()) do
                    if part:IsA("MeshPart") and part.TextureID ~= uri then
                        part.TextureID = uri
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
    return { models = changedModels, parts = changedParts }
end

return DecoPlacedAssetSync
