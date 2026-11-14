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
    local uri = textureUri(definition)
    local mesh = part :: MeshPart
    if definition and definition.appearanceMode == "material" then
        local material = Enum.Material[tostring(definition.visualMaterial or "SmoothPlastic")]
        if not material then return false end
        local raw = tostring(definition.visualColor or "#FFFFFF")
        if not raw:match("^#[%x][%x][%x][%x][%x][%x]$") then return false end
        local color = Color3.fromRGB(tonumber(raw:sub(2,3),16),
            tonumber(raw:sub(4,5),16),tonumber(raw:sub(6,7),16))
        local changed = mesh.Material ~= material or mesh.Color ~= color or mesh.TextureID ~= ""
        mesh.Material = material
        mesh.Color = color
        mesh.TextureID = ""
        return changed
    end
    if uri == nil then return false end
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
