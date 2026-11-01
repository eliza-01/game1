--!strict
-- Applies published character atlas Images to runtime MeshParts.
-- No authoring-only SurfaceAppearance properties or EditableImage allocations.
local CharacterAtlasBinder = {}

function CharacterAtlasBinder.Apply(mesh: MeshPart, imageId: string?): boolean
    if imageId == nil or imageId == "" then
        -- No override: keep the appearance authored into the published mesh.
        return false
    end
    assert(imageId:match("^[1-9]%d*$") ~= nil, "invalid character atlas Image Asset ID: " .. imageId)

    -- MeshPart.TextureID supports published Image Asset URIs at runtime.
    -- A pre-existing SurfaceAppearance wins over TextureID; remove it ONLY
    -- after the new texture has been assigned successfully.
    mesh.TextureID = "rbxassetid://" .. imageId
    for _, child in mesh:GetChildren() do
        if child:IsA("SurfaceAppearance") then
            child:Destroy()
        end
    end
    return true
end

return table.freeze(CharacterAtlasBinder)
