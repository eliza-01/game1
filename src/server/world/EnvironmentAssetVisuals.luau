--!strict
-- Runtime location binder. The Studio authoring adapter owns SurfaceAppearance
-- ColorMap/AlphaMode (Plugin capability), which gameplay threads cannot read
-- or write. Published SurfaceAppearance content is preserved unchanged here.
local EnvironmentAssetVisuals = {}

local function textureUri(definition: any): string?
    local numericId = tonumber(definition and definition.textureAssetId)
    if numericId == nil or numericId <= 0 then return nil end
    return "rbxassetid://" .. tostring(math.floor(numericId))
end

function EnvironmentAssetVisuals.ApplyPart(part: BasePart, definition: any): boolean
    if not part:IsA("MeshPart") then return false end
    local uri = textureUri(definition)
    if uri == nil then return false end
    local mesh = part :: MeshPart
    -- Existing authored SurfaceAppearance (and textureUsesAlpha) must be
    -- handled at Studio Sync, not mutated from a server gameplay thread.
    if mesh:FindFirstChildOfClass("SurfaceAppearance") then return false end
    if mesh.TextureID == uri then return false end
    mesh.TextureID = uri
    return true
end

function EnvironmentAssetVisuals.ApplyModel(model: Model, definition: any): number
    local changed = 0
    for _, descendant in model:GetDescendants() do
        if descendant:IsA("BasePart") and EnvironmentAssetVisuals.ApplyPart(descendant, definition) then
            changed += 1
        end
    end
    return changed
end

return table.freeze(EnvironmentAssetVisuals)
