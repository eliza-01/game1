--!strict
-- Runtime location binder. The Studio authoring adapter owns SurfaceAppearance
-- ColorMap/AlphaMode (Plugin capability), which gameplay threads cannot read
-- or write. Published SurfaceAppearance content is preserved unchanged here.
local EnvironmentAssetVisuals = {}
local MeshPhysics = require(game:GetService("ReplicatedStorage"):WaitForChild("Game1Shared")
    :WaitForChild("world"):WaitForChild("MeshPhysicsCore"))

local function textureUri(definition: any): string?
    local numericId = tonumber(definition and definition.textureAssetId)
    if numericId == nil or numericId <= 0 then return nil end
    return "rbxassetid://" .. tostring(math.floor(numericId))
end

function EnvironmentAssetVisuals.ApplyPart(part: BasePart, definition: any): boolean
    if not part:IsA("MeshPart") or MeshPhysics.IsCollider(part.Name)
        or MeshPhysics.IsLocationCarrier(part) then return false end
    local mesh = part :: MeshPart
    local override = if definition and typeof(definition.meshOptions)=="table"
        then definition.meshOptions[mesh.Name] else nil
    local settings = if typeof(override)=="table" and override.appearanceMode
        then override else definition
    local uri = textureUri(if settings and settings.texture_asset_id then
        {textureAssetId=settings.texture_asset_id} else definition)
    local mode=tostring(settings and settings.appearanceMode or "atlas")
    if mode=="material" or mode=="material_atlas" then
        local material = Enum.Material[tostring(settings.visualMaterial or "SmoothPlastic")]
        if not material then return false end
        local raw = tostring(settings.visualColor or "#FFFFFF")
        if not raw:match("^#[%x][%x][%x][%x][%x][%x]$") then return false end
        local color = Color3.fromRGB(tonumber(raw:sub(2,3),16),
            tonumber(raw:sub(4,5),16),tonumber(raw:sub(6,7),16))
        local changed = mesh.Material ~= material or mesh.Color ~= color
        mesh.Material = material
        mesh.Color = color
        if mode=="material" then
            changed=changed or mesh.TextureID~=""
            mesh.TextureID=""
            return changed
        end
        -- Combined mode keeps its Atlas TextureID. Runtime never mutates
        -- SurfaceAppearance; Studio owns alpha and imported appearance.
        if uri and not mesh:FindFirstChildOfClass("SurfaceAppearance") and mesh.TextureID~=uri then
            mesh.TextureID=uri
            changed=true
        end
        return changed
    end
    if uri == nil then return false end
    -- Atlas-only is neutral white, matching the Studio authoring policy.
    local changed = mesh.Material~=Enum.Material.SmoothPlastic or mesh.Color~=Color3.new(1,1,1)
    mesh.Material=Enum.Material.SmoothPlastic
    mesh.Color=Color3.new(1,1,1)
    -- Existing authored SurfaceAppearance (and textureUsesAlpha) must be
    -- handled at Studio Sync, not mutated from a server gameplay thread.
    if mesh:FindFirstChildOfClass("SurfaceAppearance") then return changed end
    if mesh.TextureID == uri then return changed end
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
