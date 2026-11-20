-- Shared Studio-side material binding for all authored MeshParts.
-- Keep TextureID even when SurfaceAppearance owns ColorMap: imported skinned
-- rigs in the previous project required this compatibility invariant.
local CollectionService = game:GetService("CollectionService")
local StudioTextureAppearance = {}
local DISTANCE_TAG = "Game1DistanceVisual"

-- A published FBX may carry more than one old SurfaceAppearance. The policy
-- is per MeshPart, not per first matching child: no alpha means NONE remain.
local function surfaces(mesh: MeshPart): {SurfaceAppearance}
    local found = {}
    for _, child in ipairs(mesh:GetChildren()) do
        if child:IsA("SurfaceAppearance") then
            table.insert(found, child)
        end
    end
    return found
end

local function removeSurfaces(mesh: MeshPart): boolean
    local changed = false
    for _, surface in ipairs(surfaces(mesh)) do
        surface:Destroy()
        changed = true
    end
    return changed
end

-- Central mesh visual streaming authoring. All consumers share this contract;
-- inactive meshes carry no tag and cost nothing in the client update loop.
function StudioTextureAppearance.ApplyDistance(mesh: MeshPart, settings: any)
    local enabled = typeof(settings) == "table" and settings.distanceStreaming == true
    if enabled then
        local distance = settings.loadDistanceStuds
        if typeof(distance) ~= "number" or distance < 20 or distance > 1000
            or distance % 1 ~= 0 then error("Invalid per-mesh visual range", 2) end
        mesh:SetAttribute("Game1VisualDistanceStuds", distance)
        if not CollectionService:HasTag(mesh, DISTANCE_TAG) then
            CollectionService:AddTag(mesh, DISTANCE_TAG)
        end
    else
        if CollectionService:HasTag(mesh, DISTANCE_TAG) then
            CollectionService:RemoveTag(mesh, DISTANCE_TAG)
        end
        mesh:SetAttribute("Game1VisualDistanceStuds", nil)
    end
end

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
    -- Opaque atlases render through MeshPart.TextureID alone. Remove ALL
    -- imported/stale SurfaceAppearance children, even when TextureID is current.
    if usesAlpha ~= true then
        local allSurfaces = surfaces(mesh)
        if mesh.TextureID == uri and #allSurfaces == 0 then return false end
        local original = mesh.TextureID
        local ok, reason = pcall(function() mesh.TextureID = uri end)
        if not ok then
            mesh.TextureID = original
            error("Opaque atlas binding failed: " .. tostring(reason), 2)
        end
        removeSurfaces(mesh)
        return true
    end
    local allSurfaces = surfaces(mesh)
    if mesh.TextureID == uri and #allSurfaces == 1 and surface ~= nil
        and surface.ColorMap == uri and surface.AlphaMode == Enum.AlphaMode.Transparency then
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
    -- Do not leave duplicate imported SurfaceAppearance children in the rig.
    for _, extra in ipairs(allSurfaces) do
        if extra ~= surface then extra:Destroy() end
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
    local allSurfaces = surfaces(mesh)
    if not enabled then return #allSurfaces == 0 end
    return #allSurfaces == 1 and allSurfaces[1].AlphaMode == Enum.AlphaMode.Transparency
end

function StudioTextureAppearance.Capture(mesh: MeshPart): any
    local copies = {}
    for _, appearance in ipairs(surfaces(mesh)) do
        table.insert(copies, appearance:Clone())
    end
    return {mesh=mesh, texture=mesh.TextureID, surfaceCopies=copies}
end

function StudioTextureAppearance.Restore(snapshot: any)
    local mesh=snapshot.mesh
    mesh.TextureID=snapshot.texture
    removeSurfaces(mesh)
    for _, surface in ipairs(snapshot.surfaceCopies) do
        surface.Parent=mesh
    end
end

function StudioTextureAppearance.ApplyAlpha(mesh: MeshPart, enabled: boolean, uri: string?): boolean
    local allSurfaces = surfaces(mesh)
    local surface = allSurfaces[1]
    if not enabled then
        return removeSurfaces(mesh)
    end
    if #allSurfaces == 1 and surface.AlphaMode == Enum.AlphaMode.Transparency
        and (uri == nil or surface.ColorMap == uri) then return false end
    local content=uri or mesh.TextureID
    if content=="" then error("Alpha requires a published ColorMap; no change made",2) end
    return StudioTextureAppearance.Apply(mesh, content, true)
end

-- Shared conversion/validation used by all Studio visual appearance adapters.
function StudioTextureAppearance.MaterialColor(materialName: string, hex: string, hasAtlas: boolean?): (Enum.Material, Color3)
    local material=Enum.Material[materialName]
    if material == nil or material == Enum.Material.Air or material == Enum.Material.Water
        or (material == Enum.Material.ForceField and hasAtlas ~= true) then
        error("Unknown visual material " .. tostring(materialName),2)
    end
    if type(hex) ~= "string" or not hex:match("^#[%x][%x][%x][%x][%x][%x]$") then
        error("visual color must be #RRGGBB",2)
    end
    local color=Color3.fromRGB(tonumber(hex:sub(2,3),16),
        tonumber(hex:sub(4,5),16),tonumber(hex:sub(6,7),16))
    return material, color
end

function StudioTextureAppearance.ApplyMaterial(mesh: MeshPart, materialName: string, hex: string): boolean
    local material,color=StudioTextureAppearance.MaterialColor(materialName,hex)
    local allSurfaces = surfaces(mesh)
    if mesh.TextureID=="" and #allSurfaces==0 and mesh.Material==material
        and mesh.Color==color then return false end
    mesh.Material=material
    mesh.Color=color
    mesh.TextureID=""
    removeSurfaces(mesh)
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
        local changed = StudioTextureAppearance.ApplyMaterial(mesh,
            tostring(opts.visualMaterial or "SmoothPlastic"),
            tostring(opts.visualColor or "#FFFFFF"))
        StudioTextureAppearance.ApplyDistance(mesh, opts)
        return changed
    end
    if mode~="atlas" and mode~="material_atlas" then
        error("Invalid MeshPart appearance mode "..mode,2)
    end
    if type(uri)~="string" or uri=="" then
        error("Atlas mode requires a published Image Asset ID",2)
    end
    -- TextureID / alpha remain owned by the same central binder for BOTH
    -- Location Assets and Real Estate. Material + Atlas additionally saves
    -- material/color on the MeshPart (without extra SurfaceAppearance).
    local material: Enum.Material? = nil
    local color: Color3? = nil
    if mode=="material_atlas" then
        material,color=StudioTextureAppearance.MaterialColor(
            tostring(opts.visualMaterial or "SmoothPlastic"),
            tostring(opts.visualColor or "#FFFFFF"),true)
    end
    local applied=StudioTextureAppearance.ApplyLocation(mesh,uri,opts.alphaEnabled==true)
    if material and color then
        if mesh.Material~=material or mesh.Color~=color then
            mesh.Material=material
            mesh.Color=color
            applied=true
        end
    end
    StudioTextureAppearance.ApplyDistance(mesh, opts)
    return applied
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
