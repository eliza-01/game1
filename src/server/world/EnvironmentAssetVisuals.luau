local EnvironmentAssetVisuals = {}

local function textureUri(definition: any): string?
    local numericId = tonumber(definition and definition.textureAssetId)
    if numericId == nil or numericId <= 0 then
        return nil
    end
    return "rbxassetid://" .. tostring(math.floor(numericId))
end

function EnvironmentAssetVisuals.ApplyPart(part: BasePart, definition: any): boolean
    if not part:IsA("MeshPart") then
        return false
    end
    local uri = textureUri(definition)
    if uri == nil or part.TextureID == uri then
        return false
    end
    part.TextureID = uri
    return true
end

function EnvironmentAssetVisuals.ApplyModel(model: Model, definition: any): number
    local changed = 0
    for _, descendant in ipairs(model:GetDescendants()) do
        if descendant:IsA("BasePart") and EnvironmentAssetVisuals.ApplyPart(descendant, definition) then
            changed += 1
        end
    end
    return changed
end

return table.freeze(EnvironmentAssetVisuals)
