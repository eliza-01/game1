-- Shared static Location LOD placement for Studio and compiled Runtime.
-- Only local visual clones; no physics, sockets, animation or scheduler ownership.
local Assembly = {}

function Assembly.Count(prototype)
    if prototype:IsA("MeshPart") then return 1 end
    if not prototype:IsA("Model") then return 0 end
    local expected = prototype:GetAttribute("Game1LodVisualCount")
    local count = 0
    for _, part in ipairs(prototype:GetChildren()) do
        if not part:IsA("MeshPart") then return 0 end
        count += 1
    end
    -- Replication can deliver a Model before all its children.
    if expected ~= count or count < 2 or count > 64
        or typeof(prototype:GetAttribute("Game1LodPublishedPivot")) ~= "CFrame" then return 0 end
    return count
end

-- Bounds in a shared oriented frame, including rotated individual meshes.
local function bounds(frame, parts)
    local low = Vector3.new(math.huge, math.huge, math.huge)
    local high = -low
    for _, part in ipairs(parts) do
        local relative = frame:ToObjectSpace(part.CFrame)
        local half = part.Size * 0.5
        for x = -1, 1, 2 do
            for y = -1, 1, 2 do
                for z = -1, 1, 2 do
                    local v = relative:PointToWorldSpace(Vector3.new(half.X*x, half.Y*y, half.Z*z))
                    low = Vector3.new(math.min(low.X,v.X),math.min(low.Y,v.Y),math.min(low.Z,v.Z))
                    high = Vector3.new(math.max(high.X,v.X),math.max(high.Y,v.Y),math.max(high.Z,v.Z))
                end
            end
        end
    end
    return low, high
end

local function base(low, high)
    return Vector3.new((low.X+high.X)*0.5, low.Y, (low.Z+high.Z)*0.5)
end

function Assembly.SourceName(mesh)
    return mesh:GetAttribute("Game1LodSourceName") or mesh.Name
end

-- Match published mesh identity, not the cached Model ID or child order.
function Assembly.AppearanceName(mesh, names)
    local name = Assembly.SourceName(mesh)
    if names[name] then return name end
    local normalized = string.lower(name):gsub("_lod[12]$", "")
    local match = nil
    for candidate in pairs(names) do
        if string.lower(candidate) == normalized then
            if match then return nil end
            match = candidate
        end
    end
    return match
end

function Assembly.Create(prototype, targetFrame, targetParts, applyAppearance)
    if Assembly.Count(prototype) == 0 or #targetParts == 0 then return nil end
    local bundle = Instance.new("Model")
    local ok, reason = pcall(function()
        local sources = if prototype:IsA("MeshPart") then {prototype} else prototype:GetChildren()
        local sourceFrame = prototype:GetAttribute("Game1LodPublishedPivot")
        if typeof(sourceFrame) ~= "CFrame" then
            assert(prototype:IsA("MeshPart"), "missing published LOD frame")
            sourceFrame = prototype.CFrame
        end
        local sourceLow, sourceHigh = bounds(sourceFrame, sources)
        local targetLow, targetHigh = bounds(targetFrame, targetParts)
        local sourceSize, targetSize = sourceHigh-sourceLow, targetHigh-targetLow
        -- A single uniform factor preserves all relative positions and rotations;
        -- use the dominant extent rather than stretching individual tree parts.
        local scale = if sourceSize.Y >= sourceSize.X and sourceSize.Y >= sourceSize.Z
            then targetSize.Y/sourceSize.Y elseif sourceSize.X >= sourceSize.Z
            then targetSize.X/sourceSize.X else targetSize.Z/sourceSize.Z
        assert(scale >= 0.001 and scale <= 1000, "invalid assembly scale")
        local sourceBase, targetBase = base(sourceLow, sourceHigh), base(targetLow, targetHigh)
        for _, source in ipairs(sources) do
            local copy = source:Clone()
            copy.Parent = bundle
            copy.Name = Assembly.SourceName(source)
            local relative = sourceFrame:ToObjectSpace(source.CFrame)
            copy.Size = source.Size * scale
            copy.CFrame = targetFrame * CFrame.new(targetBase + (relative.Position-sourceBase)*scale) * relative.Rotation
            copy.Anchored = true
            copy.CanCollide = false
            copy.CanTouch = false
            copy.CanQuery = false
            copy.LocalTransparencyModifier = 0
            applyAppearance(copy)
        end
        bundle.WorldPivot = targetFrame
    end)
    if not ok then
        bundle:Destroy()
        return nil, reason
    end
    return bundle
end

return table.freeze(Assembly)
