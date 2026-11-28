-- Read-only, per-template bounds for the entity shell. Runtime published
-- templates are immutable; a replacement Instance is a new revision.
-- No clone, skinned pose, Animator or per-entity descendant traversal here.
local Geometry = {}
local cache = setmetatable({}, {__mode = "k"})

local function collect(model)
    local parts = {}
    for _, part in ipairs(model:GetDescendants()) do
        if part:IsA("BasePart") and part.Name ~= "RootPart" and part.Name ~= "RootCollider" then
            local ancestor = part.Parent
            local removed = false
            while ancestor and ancestor ~= model do
                if ancestor:IsA("Humanoid") then removed = true; break end
                ancestor = ancestor.Parent
            end
            if not removed then table.insert(parts, {frame = part.CFrame, size = part.Size}) end
        end
    end
    return parts
end

local function describe(template)
    local cached = cache[template]
    if cached then return cached end
    if not template.Archivable then return nil end
    -- Unsupported non-archivable subtrees or empty bounds use the existing
    -- FULL path; do not guess a collider or change the source rig's shape.
    for _, child in ipairs(template:GetDescendants()) do
        if not child.Archivable then return nil end
    end
    local visual = template:FindFirstChild("ImportedRig")
    if not visual or not visual:IsA("Model") then visual = template end
    local wrapperParts = collect(template)
    local visualParts = wrapperParts
    if visual ~= template then visualParts = collect(visual) end
    if #wrapperParts == 0 or #visualParts == 0 then return nil end
    cached = {pivot = template:GetPivot(), wrapperParts = wrapperParts, visualParts = visualParts, revision = {}}
    cache[template] = cached
    return cached
end

local function bounds(parts, transform)
    local minimum = Vector3.new(math.huge, math.huge, math.huge)
    local maximum = Vector3.new(-math.huge, -math.huge, -math.huge)
    for _, part in ipairs(parts) do
        local frame = part.frame
        if transform then frame = transform * frame end
        local half = part.size * 0.5
        for x = -1, 1, 2 do
            for y = -1, 1, 2 do
                for z = -1, 1, 2 do
                    local corner = frame:PointToWorldSpace(Vector3.new(half.X*x, half.Y*y, half.Z*z))
                    minimum = Vector3.new(math.min(minimum.X, corner.X), math.min(minimum.Y, corner.Y), math.min(minimum.Z, corner.Z))
                    maximum = Vector3.new(math.max(maximum.X, corner.X), math.max(maximum.Y, corner.Y), math.max(maximum.Z, corner.Z))
                end
            end
        end
    end
    return (minimum + maximum) * 0.5, maximum - minimum
end

-- Shared exact bounds calculation for unsupported authored templates after
-- clone preparation. Empty visual bounds preserve the old GetBoundingBox rule.
function Geometry.VisibleBounds(model)
    local parts = collect(model)
    if #parts == 0 then return model:GetBoundingBox() end
    local center, size = bounds(parts, nil)
    return CFrame.new(center), size
end

function Geometry.Plan(template, rootFrame, surface, yaw, kind)
    local data = describe(template)
    if not data then return nil end
    local pivot = CFrame.new(surface) * CFrame.Angles(0, yaw, 0) * data.pivot.Rotation
    local transform = pivot * data.pivot:Inverse()
    local groundParts = data.wrapperParts
    if kind == "NPC" then groundParts = data.visualParts end
    local center, size = bounds(groundParts, transform)
    local lift = Vector3.new(0, surface.Y - (center.Y - size.Y*0.5), 0)
    local boxCenter, boxSize = bounds(data.visualParts, transform)
    return table.freeze({
        template = template,
        revision = data.revision,
        kind = kind,
        pivotOffset = rootFrame:ToObjectSpace(pivot + lift),
        colliderOffset = rootFrame:ToObjectSpace(CFrame.new(boxCenter + lift)),
        colliderSize = Vector3.new(math.max(0.5, boxSize.X), math.max(0.5, boxSize.Y), math.max(0.5, boxSize.Z)),
    })
end

function Geometry.IsCurrent(plan)
    local data = cache[plan.template]
    return data ~= nil and data.revision == plan.revision
end

-- Explicit invalidation for a future runtime template replacement/mutation owner.
function Geometry.Invalidate(template)
    cache[template] = nil
end

return table.freeze(Geometry)
