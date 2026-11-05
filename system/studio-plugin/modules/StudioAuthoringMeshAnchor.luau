-- Shared authoring-pivot resolver for published rigs. Used by Real Estate
-- and Location Assets; this module only identifies matching source anchors.
-- The actual alignment and child-rig transaction belong to StudioManagedRigSwap.
local MeshAnchor = {}

local POSITION_EPSILON = 0.025
local AXIS_DOT = 0.9999

local function sameFrame(a: CFrame, b: CFrame): boolean
    return (a.Position - b.Position).Magnitude <= POSITION_EPSILON
        and a.LookVector:Dot(b.LookVector) >= AXIS_DOT
        and a.UpVector:Dot(b.UpVector) >= AXIS_DOT
end

local function parts(root: Model): {MeshPart}
    local result = {}
    for _, item in ipairs(root:GetDescendants()) do
        if item:IsA("MeshPart") then table.insert(result, item) end
    end
    return result
end

-- Length-prefixed segments avoid collisions when Roblox Names contain '/' or ':'.
-- A repeated full path (same-named siblings) is NOT a unique authoring identity.
local function path(root: Model, item: Instance): string
    local segments = {}
    local current: Instance? = item
    while current and current ~= root do
        local name = current.Name
        table.insert(segments, 1, current.ClassName .. ":" .. tostring(#name) .. ":" .. name)
        current = current.Parent
    end
    if current ~= root then error("authoring mesh anchor lies outside model") end
    return table.concat(segments, "/")
end

local function uniqueIndex(root: Model, entries: {MeshPart}, usePath: boolean): {[string]: MeshPart | boolean}
    local indexed = {}
    for _, item in ipairs(entries) do
        local key = if usePath then path(root, item) else item.Name
        if indexed[key] ~= nil then
            indexed[key] = false
        else
            indexed[key] = item
        end
    end
    return indexed
end

function MeshAnchor.FindUniqueNamed(root: Instance, meshName: string): MeshPart?
    local found: MeshPart? = nil
    for _, item in ipairs(root:GetDescendants()) do
        if item:IsA("MeshPart") and item.Name == meshName then
            if found then return nil end
            found = item
        end
    end
    return found
end

-- Returns the old and published MeshPart plus the path of the published anchor.
-- Prefer an explicitly retained anchor or PrimaryPart; otherwise use a stable
-- hierarchy path and require agreement between the authoring-pivot transforms
-- of multiple matches. Never pick an arbitrary mesh if pivots disagree.
function MeshAnchor.Match(old: Model, published: Model, retainedPath: string?): (MeshPart, MeshPart, string)
    if retainedPath ~= nil and type(retainedPath) ~= "string" then
        error("invalid retained authoring anchor path; no Place geometry modified")
    end
    local before, after = parts(old), parts(published)
    if #before == 0 or #after == 0 then
        error("no MeshPart available to establish an authoring pivot")
    end
    if #before == 1 and #after == 1 then
        if retainedPath and retainedPath ~= "" and retainedPath ~= path(old, before[1]) then
            error("retained Location Asset authoring anchor no longer exists")
        end
        return before[1], after[1], path(published, after[1])
    end

    local oldPaths = uniqueIndex(old, before, true)
    local publishedPaths = uniqueIndex(published, after, true)
    local matches = {}
    for key, oldPart in pairs(oldPaths) do
        local newPart = publishedPaths[key]
        if oldPart and newPart then
            table.insert(matches, {old = oldPart, new = newPart,
                oldPath = key, newPath = key})
        end
    end

    -- Older Roblox FBX imports sometimes add/remove a container Model. Only
    -- use Name in that case when it is unique in BOTH rigs; never guess an
    -- occurrence index for same-named MeshParts or bones.
    if #matches == 0 then
        local oldNames = uniqueIndex(old, before, false)
        local newNames = uniqueIndex(published, after, false)
        for key, oldPart in pairs(oldNames) do
            local newPart = newNames[key]
            if oldPart and newPart then
                table.insert(matches, {old = oldPart, new = newPart,
                    oldPath = path(old, oldPart), newPath = path(published, newPart)})
            end
        end
    end

    if #matches == 0 then
        error("no uniquely matching MeshPart path/name between placed and published rigs; no Place geometry modified")
    end
    table.sort(matches, function(a, b) return a.oldPath < b.oldPath end)

    if retainedPath and retainedPath ~= "" then
        for _, match in ipairs(matches) do
            if match.oldPath == retainedPath then
                return match.old, match.new, match.newPath
            end
        end
        error("retained Location Asset authoring anchor is missing in the published rig; no Place geometry modified")
    end
    local primary = old.PrimaryPart
    if primary and primary:IsA("MeshPart") then
        for _, match in ipairs(matches) do
            if match.old == primary then
                return match.old, match.new, match.newPath
            end
        end
    end
    if #matches == 1 then
        local match = matches[1]
        return match.old, match.new, match.newPath
    end

    -- Multiple valid mesh names are NORMAL. They can all describe the same
    -- authoring transform. Accept the best agreement group, but refuse an
    -- unsupported tie or an inconsistent set instead of shifting a whole rig.
    local transforms = {}
    for i, match in ipairs(matches) do
        transforms[i] = match.old:GetPivot() * match.new:GetPivot():Inverse()
    end
    local winner, support = nil, 0
    for i, transform in ipairs(transforms) do
        local count = 0
        for _, other in ipairs(transforms) do
            if sameFrame(transform, other) then count += 1 end
        end
        if count > support then
            winner, support = i, count
        elseif count == support and winner and not sameFrame(transform, transforms[winner]) then
            winner = nil
        end
    end
    if not winner or support < 2 then
        error("multiple MeshPart authoring pivots disagree; specify a stable PrimaryPart before Sync; no Place geometry modified")
    end
    local match = matches[winner]
    return match.old, match.new, match.newPath
end

return table.freeze(MeshAnchor)
