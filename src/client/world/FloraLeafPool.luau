--!strict
-- Bounded local particle pool. Published MeshPart/atlas are loaded once,
-- prewarmed, then reused. Never updates server-owned Instances or physics.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ContentProvider = game:GetService("ContentProvider")
local Workspace = game:GetService("Workspace")
local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local Registry = require(Shared:WaitForChild("world"):WaitForChild("LocationAssetRegistry"))
local Appearance = require(Shared:WaitForChild("world"):WaitForChild("RuntimeVisualAppearance"))
local Pool = {}
local available: {MeshPart} = {}
local all: {MeshPart} = {}
local baseSizes: {[MeshPart]: Vector3} = {}
local configured = false
local folder: Folder? = nil

function Pool.Start(slug: string, capacity: number): boolean
    if configured then return #all > 0 end
    configured = true
    local templates = ReplicatedStorage:WaitForChild("Game1ResidentEffectTemplates", 30)
    if not templates then warn("[game1][flora] resident template folder missing"); return false end
    local source = templates:WaitForChild(slug, 30)
    if not source or not source:IsA("MeshPart") then
        warn("[game1][flora] resident leaf MeshPart missing: " .. slug)
        return false
    end
    local asset = Registry.assets[slug]
    if not asset or asset.category ~= "leaf" or asset.status ~= "PUBLISHED" then return false end
    folder = Instance.new("Folder")
    folder.Name = "Game1FloraLeafPool"
    folder.Parent = ReplicatedStorage -- stays referenced independent of Workspace LOD
    local base = source:Clone()
    base.Anchored, base.CanCollide, base.CanTouch, base.CanQuery = true, false, false, false
    local override = (asset.meshOptions or {})[source.Name] or (asset.meshOptions or {})[slug]
    local settings = if override and override.appearanceMode then override else asset
    local applied = Appearance.Apply(base, {
        mode = settings.appearanceMode,
        material = settings.visualMaterial,
        color = settings.visualColor,
        textureId = settings.texture_asset_id or asset.textureAssetId,
        alpha = settings.alphaEnabled == true,
    })
    if not applied then warn("[game1][flora] invalid leaf material/atlas"); base:Destroy(); return false end
    -- Best effort GPU/cache warm-up. Roblox may independently evict textures;
    -- keeping this pool resident avoids asset fetches when every burst starts.
    local allReady = true
    local ok, err = pcall(function()
        ContentProvider:PreloadAsync({base}, function(assetId, status)
            if status ~= Enum.AssetFetchStatus.Success then
                allReady = false
                warn("[game1][flora] asset not ready: " .. tostring(assetId))
            end
        end)
    end)
    if not ok or not allReady then
        warn("[game1][flora] leaf preload incomplete; skipping VFX instead of rendering untextured leaves: " .. tostring(err))
        base:Destroy()
        return false
    end
    for i = 1, capacity do
        local part = base:Clone()
        part.Name = "FloraLeaf_" .. i
        part.Transparency = 1
        part.Parent = folder
        baseSizes[part] = part.Size
        table.insert(available, part)
        table.insert(all, part)
    end
    base:Destroy()
    return #all > 0
end
function Pool.Acquire(): MeshPart?
    local part = table.remove(available)
    if part then
        part.Transparency = 0
        part.LocalTransparencyModifier = 0
        part.Parent = Workspace
    end
    return part
end
function Pool.Release(part: MeshPart)
    if not folder or part.Parent == folder then return end
    part.LocalTransparencyModifier = 0
    part.Size = baseSizes[part] or part.Size
    part.Transparency = 1
    part.Parent = folder
    table.insert(available, part)
end
return table.freeze(Pool)
