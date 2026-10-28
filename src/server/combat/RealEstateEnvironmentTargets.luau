-- Published Real Estate physics meshes participate in the same weapon-bounce
-- detection as solid Location Assets. This service indexes tagged collider
-- parts, not every Workspace object on every attack sample.
-- Destructible means "weapon passes through" until the destruction pipeline exists.
local CollectionService = game:GetService("CollectionService")
local Workspace = game:GetService("Workspace")

local Targets = {}
local TAG = "Game1RealEstateCollider"
local watchers: {[MeshPart]: {RBXScriptConnection}} = {}
local dirty = true
local revision = 0
local eligible: {MeshPart} = {}

local function markDirty()
    dirty = true
    revision += 1
end

local function findManagedHouse(part: BasePart): Model?
    local cursor: Instance? = part.Parent
    while cursor and cursor ~= Workspace do
        if cursor:IsA("Model") and typeof(cursor:GetAttribute("Game1RealEstateSlug")) == "string"
            and cursor:GetAttribute("Game1RealEstateSlug") ~= "" then
            return cursor
        end
        cursor = cursor.Parent
    end
    return nil
end

local function valid(part: Instance): boolean
    return part:IsA("MeshPart") and part:IsDescendantOf(Workspace)
        and CollectionService:HasTag(part, TAG)
        and part:GetAttribute("Game1RealEstatePhysicsOnly") == true
        and part:GetAttribute("Game1RealEstateDestructible") ~= true
        and part.CanQuery and findManagedHouse(part) ~= nil
end

local function detach(part: MeshPart)
    local connections = watchers[part]
    if not connections then return end
    for _, connection in connections do connection:Disconnect() end
    watchers[part] = nil
    markDirty()
end

local function attach(instance: Instance)
    if not instance:IsA("MeshPart") or watchers[instance] then return end
    local part: MeshPart = instance
    watchers[part] = {
        part:GetAttributeChangedSignal("Game1RealEstateDestructible"):Connect(markDirty),
        part:GetAttributeChangedSignal("Game1RealEstatePhysicsOnly"):Connect(markDirty),
        part:GetPropertyChangedSignal("CanQuery"):Connect(markDirty),
        part.AncestryChanged:Connect(markDirty),
    }
    markDirty()
end

for _, instance in CollectionService:GetTagged(TAG) do attach(instance) end
CollectionService:GetInstanceAddedSignal(TAG):Connect(attach)
CollectionService:GetInstanceRemovedSignal(TAG):Connect(function(instance)
    if instance:IsA("MeshPart") then detach(instance) end
end)
-- A tagged prefab can enter Workspace after tag assignment.
Workspace.DescendantAdded:Connect(function(instance)
    if instance:IsA("MeshPart") and CollectionService:HasTag(instance, TAG) then
        attach(instance)
        markDirty()
    end
end)
Workspace.DescendantRemoving:Connect(function(instance)
    if instance:IsA("MeshPart") and watchers[instance] then markDirty() end
end)

function Targets.GetBlockingSnapshot(): ({MeshPart}, number)
    if dirty then
        local nextParts = {}
        for part in watchers do
            if valid(part) then table.insert(nextParts, part) end
        end
        eligible = nextParts
        dirty = false
    end
    return eligible, revision
end

function Targets.ResolvePart(part: BasePart): (Model?, any?)
    if not valid(part) then return nil, nil end
    local house = findManagedHouse(part)
    if not house then return nil, nil end
    return house, {slug = tostring(house:GetAttribute("Game1RealEstateSlug")),
        destructible = false, kind = "real_estate_collision"}
end

return table.freeze(Targets)
