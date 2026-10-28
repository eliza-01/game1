-- Repair *only* authoring-managed collision rigs of already placed Estates.
-- A Studio sync of a new COL_* Model Asset must not leave older placed
-- buildings walking on the obsolete visual-mesh collision approximation.
-- No repositioning / replacement of visual house, door, or edited props.
local CollisionPolicy = require(script.Parent.StudioRealEstateCollisionPolicy)
local Targets = require(script.Parent.StudioRealEstatePlacedTargets)
local Sync = {}

local function findHouse(root: Instance): MeshPart?
    local result: MeshPart? = nil
    for _, instance in root:GetDescendants() do
        if instance:IsA("MeshPart") and instance.Name == "house" then
            if result then return nil end -- ambiguous, don't guess frame
            result = instance
        end
    end
    return result
end

local function authoredRigs(template: Model): {[string]: Model}
    local result = {}
    for _, rig in template:GetChildren() do
        if rig:IsA("Model") and rig:GetAttribute("Game1RealEstatePhysicsRig") == true then
            local part = rig:GetAttribute("Game1RealEstatePhysicsMeshName")
            if typeof(part) == "string" and CollisionPolicy.IsCollider(part) then
                result[part] = rig
            end
        end
    end
    return result
end

function Sync.Update(template: Model, slug: string, placedTargets: {Model}?): (number, {string})
    local physicsRigs = authoredRigs(template)
    if next(physicsRigs) == nil then return 0, {} end
    local referenceHouse = findHouse(template)
    if not referenceHouse then
        return 0, {"collision sync skipped: template house anchor missing or ambiguous"}
    end
    local changed = 0
    local warnings = {}
    local targets = placedTargets or Targets.List(slug)
    for _, root in targets do
        local placedHouse = findHouse(root)
        if not placedHouse then
            table.insert(warnings, "collision sync skipped for " .. root:GetFullName()
                .. ": placed house anchor missing or ambiguous")
            continue
        end
        local relative = placedHouse.CFrame * referenceHouse.CFrame:Inverse()
        for part, source in physicsRigs do
            local old = root:FindFirstChild(source.Name)
            if old and (not old:IsA("Model") or old:GetAttribute("Game1RealEstatePhysicsRig") ~= true
                or old:GetAttribute("Game1RealEstatePhysicsMeshName") ~= part) then
                table.insert(warnings, "collision rig " .. source.Name
                    .. " already exists but is not managed in " .. root:GetFullName())
                continue
            end
            local clone: Model? = nil
            local ok, problem = pcall(function()
                local staged = source:Clone()
                clone = staged
                staged:PivotTo(relative * source:GetPivot())
                staged.Parent = root
            end)
            if not ok then
                if clone then clone:Destroy() end
                table.insert(warnings, "collision rig " .. part .. " could not be staged in "
                    .. root:GetFullName() .. ": " .. tostring(problem))
                continue
            end
            if old then old:Destroy() end
            changed += 1
        end
    end
    return changed, warnings
end

return table.freeze(Sync)
