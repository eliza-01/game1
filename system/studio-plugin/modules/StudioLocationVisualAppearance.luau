-- Visual-only Location Asset appearance. Surface sound classification is separate.
-- Works on fresh publication clones and on explicitly selected placed meshes.
local Texture = require(script.Parent.StudioTextureAppearance)
local Physics = require(script.Parent.StudioMeshPhysicsCore)
local Visual = {}

local function visual(part: Instance): boolean
    return part:IsA("MeshPart") and not Physics.IsCollider(part.Name)
        and part.Name ~= "rig_carrier" and part:GetAttribute("Game1DecoPhysicsOnly") ~= true
end

local function hexColor(value: any): Color3
    if type(value) ~= "string" or not value:match("^#[%x][%x][%x][%x][%x][%x]$") then
        error("invalid Location Asset visualColor")
    end
    return Color3.fromRGB(tonumber(value:sub(2,3),16),
        tonumber(value:sub(4,5),16),tonumber(value:sub(6,7),16))
end

local function materialEnum(name: any): Enum.Material
    local item = Enum.Material[tostring(name or "SmoothPlastic")]
    if not item or item==Enum.Material.Air or item==Enum.Material.Water
        or item==Enum.Material.ForceField then
        error("invalid textureless Roblox visual material " .. tostring(name))
    end
    return item
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

function Visual.IsCurrent(mesh: MeshPart, row: any): boolean
    if not visual(mesh) then return true end
    local mode=tostring(row.appearanceMode or "atlas")
    local surface=mesh:FindFirstChildOfClass("SurfaceAppearance")
    if mode=="material" then
        return mesh.TextureID=="" and surface==nil
            and mesh.Material==materialEnum(row.visualMaterial)
            and mesh.Color==hexColor(row.visualColor)
            and mesh:GetAttribute("Game1DecoAppearanceMode")=="material"
    end
    local atlas=tostring(row.texture_asset_id or "")
    if atlas=="" then error("atlas mode requires a published Image ID") end
    local uri="rbxassetid://"..atlas
    return mesh.TextureID==uri and surface~=nil and surface.ColorMap==uri
        and surface.AlphaMode==Texture.AlphaMode(row.alphaEnabled==true)
        and mesh:GetAttribute("Game1DecoAppearanceMode")~="material"
end

function Visual.Apply(mesh: MeshPart, row: any): boolean
    if not visual(mesh) or Visual.IsCurrent(mesh,row) then return false end
    local before=Visual.Capture(mesh)
    local ok,err=pcall(function()
        if tostring(row.appearanceMode or "atlas")=="material" then
            local material=materialEnum(row.visualMaterial)
            local color=hexColor(row.visualColor)
            -- A stale texture/SufaceAppearance overrides the base material.
            mesh.TextureID=""
            for _, child in ipairs(mesh:GetChildren()) do
                if child:IsA("SurfaceAppearance") then child:Destroy() end
            end
            mesh.Material=material
            mesh.Color=color
            mesh:SetAttribute("Game1DecoVisualMaterial",material.Name)
            mesh:SetAttribute("Game1DecoVisualColor",row.visualColor)
            mesh:SetAttribute("Game1DecoAppearanceMode","material")
        else
            local atlas=tostring(row.texture_asset_id or "")
            if not atlas:match("^[1-9]%d*$") then error("atlas publication missing") end
            if mesh:GetAttribute("Game1DecoAppearanceMode")=="material" then
                mesh.Material=Enum.Material.SmoothPlastic
                mesh.Color=Color3.new(1,1,1)
            end
            Texture.ApplyLocation(mesh,"rbxassetid://"..atlas,row.alphaEnabled==true)
            mesh:SetAttribute("Game1DecoVisualMaterial",nil)
            mesh:SetAttribute("Game1DecoVisualColor",nil)
            mesh:SetAttribute("Game1DecoAppearanceMode","atlas")
        end
    end)
    if not ok then
        pcall(Visual.Restore,before)
        error("Location appearance rolled back: "..tostring(err),2)
    end
    return true
end

function Visual.ApplyModel(model: Model, row: any): number
    local count=0
    for _,item in ipairs(model:GetDescendants()) do
        if visual(item) and Visual.Apply(item :: MeshPart,row) then count+=1 end
    end
    return count
end

return table.freeze(Visual)
