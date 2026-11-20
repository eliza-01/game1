--!strict
-- Single client appearance contract for Location FULL/LOD and House FULL.
-- Studio authoring has its own source-side TextureAppearance; this module
-- applies the very same three authored modes to runtime-created MeshParts.
local Visual = {}

local function color(hex: any): Color3
    if typeof(hex) ~= "string" or not hex:match("^#[%x][%x][%x][%x][%x][%x]$") then
        return Color3.new(1, 1, 1)
    end
    return Color3.fromRGB(tonumber(hex:sub(2, 3), 16) :: number,
        tonumber(hex:sub(4, 5), 16) :: number,
        tonumber(hex:sub(6, 7), 16) :: number)
end

function Visual.Apply(mesh: MeshPart, settings: any): boolean
    local mode = settings.mode
    if mode ~= "material" and mode ~= "atlas" and mode ~= "material_atlas" then
        return false
    end
    if mode == "atlas" then
        mesh.Material = Enum.Material.SmoothPlastic
        mesh.Color = Color3.new(1, 1, 1)
    else
        local material = Enum.Material[tostring(settings.material)]
        if not material then return false end
        mesh.Material = material
        mesh.Color = color(settings.color)
    end
    if mode == "material" then
        mesh.TextureID = ""
        local surface = mesh:FindFirstChildOfClass("SurfaceAppearance")
        if surface then surface:Destroy() end
        return true
    end
    local id = tostring(settings.textureId or "")
    if not id:match("^[1-9]%d*$") then return false end
    local uri = "rbxassetid://" .. id
    local appearance = mesh:FindFirstChildOfClass("SurfaceAppearance")
    if settings.alpha == true then
        local created = appearance == nil
        if not appearance then appearance = Instance.new("SurfaceAppearance") end
        -- Exactly the same TextureID + ColorMap invariant as the central
        -- StudioTextureAppearance binder; some imported rigs require both.
        local ok = pcall(function()
            appearance.ColorMap = uri
            appearance.AlphaMode = Enum.AlphaMode.Transparency
            mesh.TextureID = uri
            if created then appearance.Parent = mesh end
        end)
        if not ok then
            if created then appearance:Destroy() end
            return false
        end
    else
        mesh.TextureID = uri
        if appearance then appearance:Destroy() end
    end
    return true
end

return table.freeze(Visual)
