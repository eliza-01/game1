-- M342: remove retired dedicated COL meshes from managed templates and placements.
-- This is a destructive migration: no legacy COL physics survives a Studio Sync.
local HttpService = game:GetService("HttpService")
local Cleanup = {}

function Cleanup.IsRetiredName(name: string): boolean
    local lower = string.lower(name)
    return lower:sub(1, 4) == "col_" or lower:sub(-4) == "_col"
        or lower:find("_col_", 1, true) ~= nil
end

local function removeIds(model: Model): ()
    for _, attr in {"Game1RigAssetIds", "Game1TextureAssetIds"} do
        local raw = model:GetAttribute(attr)
        if typeof(raw) == "string" then
            local ok, values = pcall(function() return HttpService:JSONDecode(raw) end)
            if ok and typeof(values) == "table" then
                local changed = false
                for name in pairs(values) do
                    if Cleanup.IsRetiredName(tostring(name)) then
                        values[name] = nil
                        changed = true
                    end
                end
                if changed then model:SetAttribute(attr, HttpService:JSONEncode(values)) end
            end
        end
    end
end

function Cleanup.CleanEstate(root: Model): number
    local removed = 0
    -- Limit to Real Estate managed models, not user furniture or unrelated Models.
    if typeof(root:GetAttribute("Game1RealEstateSlug")) ~= "string" then return 0 end
    for _, child in ipairs(root:GetChildren()) do
        if child:IsA("Model") and (child:GetAttribute("Game1RealEstatePhysicsRig") == true
            or (child.Name ~= "HouseRig" and Cleanup.IsRetiredName(child.Name))) then
            child:Destroy()
            removed += 1
        elseif child:IsA("Model") and (child.Name == "HouseRig" or child.Name == "DoorAssembly") then
            for _, sub in ipairs(child:GetDescendants()) do
                if sub:IsA("MeshPart") and Cleanup.IsRetiredName(sub.Name) then
                    sub:Destroy()
                    removed += 1
                end
            end
        end
    end
    removeIds(root)
    return removed
end

function Cleanup.CleanLocation(root: Model): number
    local removed = 0
    local obsolete = {}
    for _, child in ipairs(root:GetDescendants()) do
        if child:IsA("MeshPart") and Cleanup.IsRetiredName(child.Name) then
            obsolete[child] = true
        end
    end
    -- Remove importer joints referencing a discarded mesh, not just the mesh.
    for _, child in ipairs(root:GetDescendants()) do
        if child:IsA("JointInstance") and (obsolete[child.Part0] or obsolete[child.Part1]) then
            child:Destroy()
        end
    end
    for child in pairs(obsolete) do
        child:Destroy()
        removed += 1
    end
    return removed
end

-- One-time COL removal from old authoring roots that predate managed IDs.
-- Only dedicated COL_* names and the deprecated physics rig flag are eligible.
function Cleanup.CleanLegacyAssetTree(root: Instance?): number
    if not root then return 0 end
    local obsolete = {}
    for _, obj in ipairs(root:GetDescendants()) do
        if obj:IsA("MeshPart") and Cleanup.IsRetiredName(obj.Name) then
            obsolete[obj] = true
        elseif obj:IsA("Model") and (Cleanup.IsRetiredName(obj.Name)
            or obj:GetAttribute("Game1RealEstatePhysicsRig") == true) then
            obsolete[obj] = true
        end
    end
    -- Joint instances referencing deleted meshes are not useful.
    for _, obj in ipairs(root:GetDescendants()) do
        if obj:IsA("JointInstance") or obj:IsA("WeldConstraint") then
            if (obj.Part0 and obsolete[obj.Part0]) or (obj.Part1 and obsolete[obj.Part1]) then
                obj:Destroy()
            end
        end
    end
    local removed = 0
    for obj in pairs(obsolete) do
        if obj.Parent ~= nil then
            local parent = obj.Parent
            local covered = false
            while parent and parent ~= root do
                if obsolete[parent] then covered = true break end
                parent = parent.Parent
            end
            if not covered then
                if obj:IsA("BasePart") and obj.Parent:IsA("Model")
                    and obj.Parent.PrimaryPart == obj then
                    obj.Parent.PrimaryPart = nil
                end
                obj:Destroy()
                removed += 1
            end
        end
    end
    return removed
end

function Cleanup.CleanManagedTree(root: Instance): {estate: number, location: number}
    local count = {estate = 0, location = 0}
    for _, instance in ipairs(root:GetDescendants()) do
        if instance:IsA("Model") then
            if typeof(instance:GetAttribute("Game1RealEstateSlug")) == "string" then
                count.estate += Cleanup.CleanEstate(instance)
            elseif typeof(instance:GetAttribute("Game1DecoAssetSlug")) == "string" then
                count.location += Cleanup.CleanLocation(instance)
            end
        end
    end
    return count
end

return table.freeze(Cleanup)
