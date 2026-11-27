-- Shared static Location LOD placement for Studio and compiled Runtime.
-- Only local visual clones; no physics, sockets, animation or scheduler ownership.
local Assembly = {}
local Job = require(script.Parent:WaitForChild("LodAssemblyJob"))

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
local function bounds(frame, parts, job)
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
        if job then job:Unit() end
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

function Assembly.BuildMetadata(prototype)
    if prototype:IsA("MeshPart") then
        local sourceFrame = prototype:GetAttribute("Game1LodPublishedPivot")
        if typeof(sourceFrame) ~= "CFrame" then sourceFrame = prototype.CFrame end
        local sourceLow, sourceHigh = bounds(sourceFrame, {prototype})
        local sourceSize = sourceHigh - sourceLow
        return {prototype = prototype, kind = "meshpart", count = 1,
            sourceFrame = sourceFrame, sourceLow = sourceLow, sourceHigh = sourceHigh,
            sourceSize = sourceSize, sourceBase = base(sourceLow, sourceHigh),
            sourceName = Assembly.SourceName(prototype), parts = {{
                source = prototype, relative = sourceFrame:ToObjectSpace(prototype.CFrame),
                size = prototype.Size, sourceName = Assembly.SourceName(prototype),
            }}}, "ready"
    end
    if not prototype:IsA("Model") then return nil, "invalid" end
    local expected = prototype:GetAttribute("Game1LodVisualCount")
    local sourceFrame = prototype:GetAttribute("Game1LodPublishedPivot")
    local children = prototype:GetChildren()
    if expected == nil or typeof(sourceFrame) ~= "CFrame" then
        return nil, "incomplete"
    end
    if type(expected) ~= "number" or expected < 2 or expected > 64
        or expected ~= math.floor(expected) then
        return nil, "invalid"
    end
    if #children < expected then return nil, "incomplete" end
    if #children > expected then return nil, "invalid" end
    local parts = {}
    for _, source in ipairs(children) do
        if not source:IsA("MeshPart") then return nil, "invalid" end
        local relative = sourceFrame:ToObjectSpace(source.CFrame)
        table.insert(parts, {source = source, relative = relative, size = source.Size,
            sourceName = Assembly.SourceName(source)})
    end
    local sourceLow, sourceHigh = bounds(sourceFrame, children)
    local sourceSize = sourceHigh - sourceLow
    local sourceBase = base(sourceLow, sourceHigh)
    return {prototype = prototype, kind = "model", count = #parts, sourceFrame = sourceFrame,
        sourceLow = sourceLow, sourceHigh = sourceHigh, sourceSize = sourceSize,
        sourceBase = sourceBase, parts = parts}, "ready"
end

function Assembly.Prepare(prototype, targetFrame, targetParts, applyAppearance, metadata)
    metadata = metadata or Assembly.BuildMetadata(prototype)
    if not metadata or metadata.prototype ~= prototype
        or (metadata.kind ~= "model" and metadata.kind ~= "meshpart")
        or metadata.count < 1 or metadata.count > 64 or #targetParts == 0 then
        return nil, "invalid assembly input"
    end
    return Job.new(function(job)
        local targetLow, targetHigh = bounds(targetFrame, targetParts, job)
        local targetSize = targetHigh - targetLow
        local sourceSize = metadata.sourceSize
        local scale = if sourceSize.Y >= sourceSize.X and sourceSize.Y >= sourceSize.Z
            then targetSize.Y/sourceSize.Y elseif sourceSize.X >= sourceSize.Z
            then targetSize.X/sourceSize.X else targetSize.Z/sourceSize.Z
        assert(scale >= 0.001 and scale <= 1000, "invalid assembly scale")
        local targetBase = base(targetLow, targetHigh)
        local bundle = job:Own(Instance.new("Model"))
        job.bundle = bundle
        job:Unit()
        for _, descriptor in ipairs(metadata.parts) do
            local source = descriptor.source
            local copy = job:Own(source:Clone(), "meshClones")
            job:Unit()
            copy.Name = descriptor.sourceName
            copy.Size = descriptor.size * scale
            copy.CFrame = targetFrame * CFrame.new(targetBase + (descriptor.relative.Position-metadata.sourceBase)*scale)
                * descriptor.relative.Rotation
            copy.Anchored = true
            copy.CanCollide = false
            copy.CanTouch = false
            copy.CanQuery = false
            copy.LocalTransparencyModifier = 0
            applyAppearance(copy)
            job:Unit()
            copy.Parent = bundle
            job:Unit()
        end
        bundle.WorldPivot = targetFrame
    end)
end

function Assembly.PrepareSingle(prototype, record, applyAppearance)
    return Job.new(function(job)
        local copy = job:Own(prototype:Clone(), "meshClones")
        job.bundle = copy
        job:Unit()
        copy.Name = Assembly.SourceName(prototype)
        copy.Anchored = true
        copy.CanCollide = false
        copy.CanTouch = false
        copy.CanQuery = false
        copy.Size = record.size
        copy.CFrame = record.cframe
        applyAppearance(copy)
    end)
end

function Assembly.Create(prototype, targetFrame, targetParts, applyAppearance, metadata)
    local job, reason = Assembly.Prepare(prototype, targetFrame, targetParts, applyAppearance, metadata)
    if not job then return nil, reason end
    return job:Finish()
end

return table.freeze(Assembly)
