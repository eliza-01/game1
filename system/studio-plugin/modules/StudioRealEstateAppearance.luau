-- Per-MeshPart visual authoring. No atlas and no SurfaceAppearance by default.
local Texture=require(script.Parent.StudioTextureAppearance)
local Appearance={}

function Appearance.Apply(mesh: MeshPart, options: any, publishedId: string?, alpha: any): boolean
    local settings=if typeof(options)=="table" then options else {}
    local mode=tostring(settings.appearanceMode or "atlas") -- old templates
    if mode=="material" then
        return Texture.ApplyVisual(mesh,settings)
    end
    if mode~="atlas" then error("Real Estate: invalid appearance mode "..mode) end
    local id=tostring(publishedId or "")
    if not id:match("^[1-9]%d*$") then error("Real Estate atlas is not published") end
    return Texture.ApplyVisual(mesh,settings,"rbxassetid://"..id)
end

return table.freeze(Appearance)
