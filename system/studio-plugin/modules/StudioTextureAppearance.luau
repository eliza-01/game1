-- Shared Studio-side material binding for all authored MeshParts.
-- Keep TextureID even when SurfaceAppearance owns ColorMap: imported skinned
-- rigs in the previous project required this compatibility invariant.
local StudioTextureAppearance = {}

function StudioTextureAppearance.Apply(mesh: MeshPart, uri: string, usesAlpha: any, idsOnly: boolean?): boolean
    if uri == "" then
        return false
    end
    local surface = mesh:FindFirstChildOfClass("SurfaceAppearance")
    if idsOnly == true then
        -- M216 placed Location Asset sync. Only existing Asset ID fields are
        -- mutable; do not create SurfaceAppearance or rewrite AlphaMode/physics.
        if mesh.TextureID == uri and (surface == nil or surface.ColorMap == uri) then
            return false
        end
        local previousTexture = mesh.TextureID
        local previousMap = if surface then surface.ColorMap else nil
        local applied, reason = pcall(function()
            mesh.TextureID = uri
            if surface ~= nil then
                surface.ColorMap = uri
            end
        end)
        if not applied then
            pcall(function()
                mesh.TextureID = previousTexture
                if surface ~= nil and previousMap ~= nil then
                    surface.ColorMap = previousMap
                end
            end)
            error("ID-only appearance binding failed for " .. mesh:GetFullName() .. ": " .. tostring(reason), 2)
        end
        return true
    end
    -- A SurfaceAppearance is reserved for explicitly enabled atlas alpha.
    -- Opaque atlases render through MeshPart.TextureID alone.
    if usesAlpha ~= true then
        local unchanged = mesh.TextureID == uri and surface == nil
        if unchanged then return false end
        local original = mesh.TextureID
        local ok, reason = pcall(function() mesh.TextureID = uri end)
        if not ok then
            mesh.TextureID = original
            error("Opaque atlas binding failed: " .. tostring(reason), 2)
        end
        if surface then surface:Destroy() end
        return true
    end
    if mesh.TextureID == uri and surface ~= nil and surface.ColorMap == uri
        and surface.AlphaMode == Enum.AlphaMode.Transparency then
        return false
    end
    local created = false
    if surface == nil then
        surface = Instance.new("SurfaceAppearance")
        surface.Name = "SurfaceAppearance"
        created = true
    end
    local beforeTexture = mesh.TextureID
    local beforeColor = surface.ColorMap
    local beforeMode = surface.AlphaMode
    local ok, reason = pcall(function()
        surface.ColorMap = uri
        surface.AlphaMode = Enum.AlphaMode.Transparency
        mesh.TextureID = uri
        if created then surface.Parent = mesh end
    end)
    if not ok then
        mesh.TextureID = beforeTexture
        if created then surface:Destroy() else
            surface.ColorMap = beforeColor
            surface.AlphaMode = beforeMode
        end
        error("Alpha atlas binding failed: " .. tostring(reason), 2)
    end
    return true
end

-- Location-only alpha policy. Unlike Apply(), this NEVER substitutes Overlay
-- for Opaque, and it does not alter MeshPart.Transparency or physics.
function StudioTextureAppearance.AlphaMode(enabled: boolean): Enum.AlphaMode
    if type(enabled) ~= "boolean" then error("alphaEnabled must be boolean",2) end
    local mode = if enabled then Enum.AlphaMode.Transparency else Enum.AlphaMode.Opaque
    if mode == nil then error("Opaque AlphaMode unavailable in this Studio",2) end
    return mode
end

function StudioTextureAppearance.AlphaCurrent(mesh: MeshPart, enabled: boolean): boolean
    local appearance=mesh:FindFirstChildOfClass("SurfaceAppearance")
    if not enabled then return appearance==nil end
    return appearance~=nil and appearance.AlphaMode==Enum.AlphaMode.Transparency
end

function StudioTextureAppearance.Capture(mesh: MeshPart): any
    local appearance=mesh:FindFirstChildOfClass("SurfaceAppearance")
    return {mesh=mesh,texture=mesh.TextureID,
        surfaceCopy=if appearance then appearance:Clone() else nil}
end

function StudioTextureAppearance.Restore(snapshot: any)
    local mesh=snapshot.mesh
    mesh.TextureID=snapshot.texture
    for _, descendant in mesh:GetChildren() do
        if descendant:IsA("SurfaceAppearance") then descendant:Destroy() end
    end
    if snapshot.surfaceCopy then snapshot.surfaceCopy.Parent=mesh end
end

function StudioTextureAppearance.ApplyAlpha(mesh: MeshPart, enabled: boolean, uri: string?): boolean
    local surface=mesh:FindFirstChildOfClass("SurfaceAppearance")
    if not enabled then
        if surface == nil then return false end
        surface:Destroy()
        return true
    end
    if surface and surface.AlphaMode==Enum.AlphaMode.Transparency
        and (uri==nil or surface.ColorMap==uri) then return false end
    local content=uri or mesh.TextureID
    if content=="" then error("Alpha requires a published ColorMap; no change made",2) end
    return StudioTextureAppearance.Apply(mesh, content, true)
end

function StudioTextureAppearance.ApplyMaterial(mesh: MeshPart, materialName: string, hex: string): boolean
    local material=Enum.Material[materialName]
    if material == nil or material == Enum.Material.Air or material == Enum.Material.Water
        or material == Enum.Material.ForceField then
        error("Unknown visual material " .. tostring(materialName),2)
    end
    if not hex:match("^#[%x][%x][%x][%x][%x][%x]$") then
        error("visual color must be #RRGGBB",2)
    end
    local color=Color3.fromRGB(tonumber(hex:sub(2,3),16),
        tonumber(hex:sub(4,5),16),tonumber(hex:sub(6,7),16))
    local surface=mesh:FindFirstChildOfClass("SurfaceAppearance")
    if mesh.TextureID=="" and surface==nil and mesh.Material==material
        and mesh.Color==color then return false end
    mesh.Material=material
    mesh.Color=color
    mesh.TextureID=""
    if surface then surface:Destroy() end
    return true
end

-- Canonical appearance contract for ANY authored MeshPart, regardless of asset domain.
-- Each individual mesh supplies its own alphaEnabled flag; PNG pixel alpha
-- detection never opts a mesh into SurfaceAppearance.
function StudioTextureAppearance.ApplyVisual(mesh: MeshPart, settings: any, uri: string?): boolean
    local opts=if typeof(settings)=="table" then settings else {}
    local mode=tostring(opts.appearanceMode or "material")
    if mode=="material" then
        if opts.alphaEnabled==true then error("Alpha transparency requires an atlas",2) end
        return StudioTextureAppearance.ApplyMaterial(mesh,
            tostring(opts.visualMaterial or "SmoothPlastic"),
            tostring(opts.visualColor or "#FFFFFF"))
    end
    if mode~="atlas" then error("Invalid MeshPart appearance mode "..mode,2) end
    if type(uri)~="string" or uri=="" then
        error("Atlas mode requires a published Image Asset ID",2)
    end
    return StudioTextureAppearance.ApplyLocation(mesh,uri,opts.alphaEnabled==true)
end

function StudioTextureAppearance.ApplyLocation(mesh: MeshPart, uri: string, enabled: boolean): boolean
    local snapshot=StudioTextureAppearance.Capture(mesh)
    local ok,result=pcall(function()
        local ids=StudioTextureAppearance.Apply(mesh,uri,nil,true)
        local alpha=StudioTextureAppearance.ApplyAlpha(mesh,enabled,uri)
        return ids or alpha
    end)
    if not ok then
        pcall(StudioTextureAppearance.Restore,snapshot)
        error("Location appearance rolled back: "..tostring(result),2)
    end
    return result
end

return table.freeze(StudioTextureAppearance)
