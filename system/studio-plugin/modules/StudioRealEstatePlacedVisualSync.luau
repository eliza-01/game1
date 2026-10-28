-- Full Real Estate sync: refresh visual rigs on *all managed placed* houses.
-- Preserve the house transform, existing door opening pivot, and any unmanaged
-- player-owned objects. Collision rigs have an independent synchronizer.
local Targets = require(script.Parent.StudioRealEstatePlacedTargets)
local VisualSync = {}

local function houseAnchor(root: Instance): MeshPart?
    local found: MeshPart? = nil
    for _, child in root:GetDescendants() do
        if child:IsA("MeshPart") and child.Name == "house" then
            if found then return nil end
            found = child
        end
    end
    return found
end

local function visuals(template: Model): {Model}
    local result = {}
    for _, child in template:GetChildren() do
        if child:IsA("Model") and child:GetAttribute("Game1RealEstatePhysicsRig") ~= true then
            table.insert(result, child)
        end
    end
    table.sort(result, function(a, b)
        if a.Name == "HouseRig" then return true end
        if b.Name == "HouseRig" then return false end
        return a.Name < b.Name
    end)
    return result
end

function VisualSync.Update(template: Model, slug: string, placedTargets: {Model}?): (number, number, {string})
    local targets = placedTargets or Targets.List(slug)
    local sourceHouse = houseAnchor(template)
    if not sourceHouse then return 0, #targets, {"Full visual sync skipped: template house anchor missing or ambiguous"} end
    local sources = visuals(template)
    local changed = 0
    local found = 0
    local warnings = {}
    for _, root in targets do
        found += 1
        local placedHouse = houseAnchor(root)
        if not placedHouse then
            table.insert(warnings, root:GetFullName() .. ": house anchor missing or ambiguous")
            continue
        end
        local frame = placedHouse.CFrame * sourceHouse.CFrame:Inverse()
        local stages = {}
        local complete = true
        for _, source in sources do
            local old = root:FindFirstChild(source.Name)
            if not old or not old:IsA("Model") then
                complete = false
                table.insert(warnings, root:GetFullName() .. ": unmanaged/missing " .. source.Name)
                break
            end
            local staged: Model? = nil
            local ok, problem = pcall(function()
                local candidate = source:Clone()
                staged = candidate
                -- Keep an already-open door at its previous pivot; all other
                -- visual meshes follow the authored relative house transform.
                local target = if source.Name == "DoorAssembly"
                    then (old :: Model):GetPivot() else frame * source:GetPivot()
                candidate:PivotTo(target)
            end)
            if not ok or not staged then
                complete = false
                if staged then staged:Destroy() end
                table.insert(warnings, root:GetFullName() .. ": " .. tostring(problem))
                break
            end
            table.insert(stages, {old = old :: Model, staged = staged :: Model, name = source.Name})
        end
        if not complete then
            for _, stage in stages do stage.staged:Destroy() end
            continue
        end
        local committed = {}
        local ok, problem = pcall(function()
            for _, stage in stages do
                stage.old.Name = stage.name .. "_M143_Previous"
                stage.staged.Name = stage.name
                stage.staged.Parent = root
                table.insert(committed, stage)
            end
        end)
        if not ok then
            for _, stage in stages do
                stage.staged:Destroy()
                stage.old.Name = stage.name
            end
            table.insert(warnings, root:GetFullName() .. ": update rolled back: " .. tostring(problem))
            continue
        end
        for _, stage in committed do stage.old:Destroy() end
        Targets.MarkPlaced(root)
        -- Keep published IDs on the placed instance consistent with its
        -- actual copied rigs; do not touch player-owned children or pivots.
        root:SetAttribute("Game1RigAssetIds", template:GetAttribute("Game1RigAssetIds"))
        root:SetAttribute("Game1HouseModelAssetId", template:GetAttribute("Game1HouseModelAssetId"))
        root:SetAttribute("Game1DoorModelAssetId", template:GetAttribute("Game1DoorModelAssetId"))
        root:SetAttribute("Game1ModelAssetId", template:GetAttribute("Game1ModelAssetId"))
        changed += 1
    end
    return changed, found, warnings
end

return table.freeze(VisualSync)
