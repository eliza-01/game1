-- Shared Studio-side material binding for all authored MeshParts.
-- Keep TextureID even when SurfaceAppearance owns ColorMap: imported skinned
-- rigs in the previous project required this compatibility invariant.
local StudioTextureAppearance = {}

function StudioTextureAppearance.Apply(mesh: MeshPart, uri: string, usesAlpha: any): boolean
    if uri == "" then
        return false
    end
    local surface = mesh:FindFirstChildOfClass("SurfaceAppearance")
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

return table.freeze(StudioTextureAppearance)
