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
    local desiredMode = if usesAlpha == true then Enum.AlphaMode.Transparency else Enum.AlphaMode.Overlay
    local modeKnown = typeof(usesAlpha) == "boolean"
    local alreadyCurrent = mesh.TextureID == uri
        and surface ~= nil and surface.ColorMap == uri
        and (not modeKnown or surface.AlphaMode == desiredMode)
    if alreadyCurrent then
        return false
    end

    -- Do not change normals, roughness, metalness, mesh geometry or physics.
    -- Parent a new appearance only after its properties have been set.
    local created = false
    if surface == nil then
        surface = Instance.new("SurfaceAppearance")
        surface.Name = "SurfaceAppearance"
        created = true
    end
    local previousTexture = mesh.TextureID
    local previousMap = surface.ColorMap
    local previousMode = surface.AlphaMode
    local ok, reason = pcall(function()
        mesh.TextureID = uri
        surface.ColorMap = uri
        if modeKnown then
            surface.AlphaMode = desiredMode
        end
        if created then
            surface.Parent = mesh
        end
    end)
    if not ok then
        pcall(function()
            mesh.TextureID = previousTexture
            if created then
                surface:Destroy()
            else
                surface.ColorMap = previousMap
                surface.AlphaMode = previousMode
            end
        end)
        error("SurfaceAppearance binding failed for " .. mesh:GetFullName() .. ": " .. tostring(reason), 2)
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
    return appearance~=nil and appearance.AlphaMode==StudioTextureAppearance.AlphaMode(enabled)
end

function StudioTextureAppearance.Capture(mesh: MeshPart): any
    local surface=mesh:FindFirstChildOfClass("SurfaceAppearance")
    return {mesh=mesh,texture=mesh.TextureID,surface=surface,
        color=if surface then surface.ColorMap else nil,
        mode=if surface then surface.AlphaMode else nil}
end

function StudioTextureAppearance.Restore(snapshot: any)
    local mesh=snapshot.mesh
    mesh.TextureID=snapshot.texture
    local current=mesh:FindFirstChildOfClass("SurfaceAppearance")
    if snapshot.surface then
        if current~=snapshot.surface and current then current:Destroy() end
        if snapshot.surface.Parent~=mesh then snapshot.surface.Parent=mesh end
        snapshot.surface.ColorMap=snapshot.color
        snapshot.surface.AlphaMode=snapshot.mode
    elseif current then
        current:Destroy() -- newly introduced by a failed transaction
    end
end

function StudioTextureAppearance.ApplyAlpha(mesh: MeshPart, enabled: boolean, uri: string?): boolean
    local mode=StudioTextureAppearance.AlphaMode(enabled)
    local surface=mesh:FindFirstChildOfClass("SurfaceAppearance")
    if surface and surface.AlphaMode==mode then return false end
    if surface then
        surface.AlphaMode=mode
        return true
    end
    local content=uri or mesh.TextureID
    if content=="" then error("Alpha requires a published ColorMap; no change made",2) end
    local created=Instance.new("SurfaceAppearance")
    local ok,reason=pcall(function()
        created.Name="SurfaceAppearance"
        created.ColorMap=content
        created.AlphaMode=mode
        created.Parent=mesh
    end)
    if not ok then created:Destroy();error(tostring(reason),2) end
    return true
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
