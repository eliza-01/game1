local EnvironmentAssetVisuals = {}

local function textureUri(definition: any): string?
    local numericId = tonumber(definition and definition.textureAssetId)
    if numericId == nil or numericId <= 0 then
        return nil
    end
    return "rbxassetid://" .. tostring(math.floor(numericId))
end

-- Runtime Location Asset binder. Studio uses its own equivalent adapter, because
-- the plugin does not depend on gameplay modules. Both honor the same contract:
-- textureAssetId + nullable textureUsesAlpha. Never clear TextureID on skinned meshes.
function EnvironmentAssetVisuals.ApplyPart(part: BasePart, definition: any): boolean
    if not part:IsA("MeshPart") then
        return false
    end
    local uri = textureUri(definition)
    if uri == nil then
        return false
    end
    local mesh = part :: MeshPart
    local surface = mesh:FindFirstChildOfClass("SurfaceAppearance")
    local usesAlpha = definition and definition.textureUsesAlpha
    local modeKnown = typeof(usesAlpha) == "boolean"
    local targetMode = if usesAlpha == true then Enum.AlphaMode.Transparency else Enum.AlphaMode.Overlay
    if mesh.TextureID == uri and surface ~= nil and surface.ColorMap == uri
        and (not modeKnown or surface.AlphaMode == targetMode) then
        return false
    end
    if surface == nil then
        surface = Instance.new("SurfaceAppearance")
        surface.Name = "SurfaceAppearance"
        surface.ColorMap = uri
        if modeKnown then
            surface.AlphaMode = targetMode
        end
        surface.Parent = mesh
    else
        surface.ColorMap = uri
        if modeKnown then
            surface.AlphaMode = targetMode
        end
    end
    mesh.TextureID = uri
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
