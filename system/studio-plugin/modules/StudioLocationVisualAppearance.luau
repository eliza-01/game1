-- Visual-only Location Asset appearance. Surface sound classification is separate.
-- Works on fresh publication clones and on explicitly selected placed meshes.
local Texture = require(script.Parent.StudioTextureAppearance)
local Physics = require(script.Parent.StudioMeshPhysicsCore)
local Visual = {}

local function visual(part: Instance): boolean
    return part:IsA("MeshPart") and not Physics.IsCollider(part.Name)
        and part.Name ~= "rig_carrier" and part:GetAttribute("Game1DecoPhysicsOnly") ~= true
end

function Visual.Capture(mesh: MeshPart): any
    local surfaces={}
    for _, child in ipairs(mesh:GetChildren()) do
        if child:IsA("SurfaceAppearance") then table.insert(surfaces,child:Clone()) end
    end
    return {mesh=mesh,texture=mesh.TextureID,material=mesh.Material,color=mesh.Color,
        mode=mesh:GetAttribute("Game1DecoAppearanceMode"),
        visualMaterial=mesh:GetAttribute("Game1DecoVisualMaterial"),
        visualColor=mesh:GetAttribute("Game1DecoVisualColor"),surfaces=surfaces}
end

function Visual.Restore(snapshot: any)
    local mesh=snapshot.mesh
    if not mesh.Parent then return end
    mesh.TextureID=snapshot.texture
    mesh.Material=snapshot.material
    mesh.Color=snapshot.color
    for _, child in ipairs(mesh:GetChildren()) do
        if child:IsA("SurfaceAppearance") then child:Destroy() end
    end
    for _, surface in ipairs(snapshot.surfaces) do surface.Parent=mesh end
    mesh:SetAttribute("Game1DecoAppearanceMode",snapshot.mode)
    mesh:SetAttribute("Game1DecoVisualMaterial",snapshot.visualMaterial)
    mesh:SetAttribute("Game1DecoVisualColor",snapshot.visualColor)
end

local function meshSettings(mesh: MeshPart, row: any): any
    local overrides=if typeof(row.meshOptions)=="table" then row.meshOptions[mesh.Name] else nil
    if typeof(overrides)~="table" then return row end
    return {
        appearanceMode=overrides.appearanceMode or row.appearanceMode,
        visualMaterial=overrides.visualMaterial or row.visualMaterial,
        visualColor=overrides.visualColor or row.visualColor,
        alphaEnabled=if type(overrides.alphaEnabled)=="boolean" then overrides.alphaEnabled else row.alphaEnabled,
        texture_asset_id=overrides.texture_asset_id or row.texture_asset_id,
    }
end

Visual.Settings = meshSettings

function Visual.IsCurrent(mesh: MeshPart, row: any): boolean
    row=meshSettings(mesh,row)
    if not visual(mesh) then return true end
    local mode=tostring(row.appearanceMode or "atlas")
    local surface=mesh:FindFirstChildOfClass("SurfaceAppearance")
    if mode=="material" then
        local material,color=Texture.MaterialColor(
            tostring(row.visualMaterial or "SmoothPlastic"),
            tostring(row.visualColor or "#FFFFFF"))
        return mesh.TextureID=="" and Texture.AlphaCurrent(mesh, false)
            and mesh.Material==material
            and mesh.Color==color
            and mesh:GetAttribute("Game1DecoAppearanceMode")=="material"
    end
    if mode~="atlas" and mode~="material_atlas" then
        error("invalid Location appearance mode "..mode)
    end
    local atlas=tostring(row.texture_asset_id or "")
    if atlas=="" then error("atlas mode requires a published Image ID") end
    local uri="rbxassetid://"..atlas
    local alpha=row.alphaEnabled==true
    local materialCurrent=true
    if mode=="material_atlas" then
        local material,color=Texture.MaterialColor(
            tostring(row.visualMaterial or "SmoothPlastic"),
            tostring(row.visualColor or "#FFFFFF"),true)
        materialCurrent=mesh.Material==material and mesh.Color==color
    else
        materialCurrent=mesh.Material==Enum.Material.SmoothPlastic
            and mesh.Color==Color3.new(1,1,1)
    end
    return materialCurrent and mesh.TextureID==uri
        and Texture.AlphaCurrent(mesh, alpha)
        and (not alpha or (surface ~= nil and surface.ColorMap == uri))
        and mesh:GetAttribute("Game1DecoAppearanceMode")==mode
end

function Visual.Apply(mesh: MeshPart, row: any): boolean
    row=meshSettings(mesh,row)
    if not visual(mesh) or Visual.IsCurrent(mesh,row) then return false end
    local before=Visual.Capture(mesh)
    local ok,err=pcall(function()
        if tostring(row.appearanceMode or "atlas")=="material" then
            Texture.ApplyVisual(mesh,row)
            mesh:SetAttribute("Game1DecoVisualMaterial",mesh.Material.Name)
            mesh:SetAttribute("Game1DecoVisualColor",row.visualColor)
            mesh:SetAttribute("Game1DecoAppearanceMode","material")
        else
            local atlas=tostring(row.texture_asset_id or "")
            if not atlas:match("^[1-9]%d*$") then error("atlas publication missing") end
            local mode=tostring(row.appearanceMode or "atlas")
            if mode=="atlas" then
                mesh.Material=Enum.Material.SmoothPlastic
                mesh.Color=Color3.new(1,1,1)
            end
            Texture.ApplyVisual(mesh,row,"rbxassetid://"..atlas)
            mesh:SetAttribute("Game1DecoVisualMaterial",if mode=="material_atlas" then mesh.Material.Name else nil)
            mesh:SetAttribute("Game1DecoVisualColor",if mode=="material_atlas" then row.visualColor else nil)
            mesh:SetAttribute("Game1DecoAppearanceMode",mode)
        end
    end)
    if not ok then
        pcall(Visual.Restore,before)
        error("Location appearance rolled back: "..tostring(err),2)
    end
    return true
end

-- Assert on the written mesh, not on a cached Studio Scan. Never report a
-- successful Sync while alpha-disabled visuals still have SurfaceAppearance.
function Visual.AssertCurrent(mesh: MeshPart, row: any)
    if visual(mesh) and not Visual.IsCurrent(mesh, row) then
        error("Location Appearance Sync incomplete for " .. mesh:GetFullName()
            .. "; re-scan this placement", 2)
    end
end

function Visual.ApplyModel(model: Model, row: any): number
    local count=0
    for _,item in ipairs(model:GetDescendants()) do
        if visual(item) then
            if Visual.Apply(item :: MeshPart,row) then count+=1 end
            Visual.AssertCurrent(item :: MeshPart,row)
        end
    end
    return count
end

return table.freeze(Visual)
