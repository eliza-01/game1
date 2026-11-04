-- Shared Studio mechanism for replacing AUTHORING-MANAGED child rigs while
-- retaining the placed root Model and its identity. Used by Real Estate and
-- Location Assets. Callers alone choose targets and authoring-space anchors.
local RigSwap = {}

local POSITION_EPSILON = 0.025
local AXIS_DOT = 0.9999

local function sameFrame(a: CFrame, b: CFrame): boolean
    return (a.Position - b.Position).Magnitude <= POSITION_EPSILON
        and a.LookVector:Dot(b.LookVector) >= AXIS_DOT
        and a.UpVector:Dot(b.UpVector) >= AXIS_DOT
end

function RigSwap.AlignToAnchor(rig: Model, sourceAnchor: BasePart, targetPivot: CFrame, label: string)
    if not sourceAnchor:IsDescendantOf(rig) then
        error(label .. ": source anchor is outside its rig")
    end
    rig:PivotTo(targetPivot * sourceAnchor:GetPivot():Inverse() * rig:GetPivot())
    if not sameFrame(sourceAnchor:GetPivot(), targetPivot) then
        error(label .. ": authored anchor shifted after alignment")
    end
end

-- This is a transaction, not a placed-Model clone. Old children remain alive
-- until EVERY target has passed commit. Rollback can reattach them unchanged.
function RigSwap.Prepare(root: Model, outgoing: {Instance}, incoming: {Instance}): any
    if not root:IsA("Model") or root.Parent == nil or #outgoing == 0 or #incoming == 0 then
        error("managed rig replacement requires a placed root and nonempty child lists")
    end
    local outgoingSet = {}
    local incomingNames = {}
    for index, child in ipairs(outgoing) do
        if child.Parent ~= root or outgoingSet[child] then
            error("managed rig replacement: outgoing child is not uniquely owned by placed root")
        end
        outgoingSet[child] = true
        local backupName = "_Game1RigSwapPending_" .. tostring(index)
        if root:FindFirstChild(backupName) then
            error("unresolved managed rig replacement staging: " .. backupName)
        end
    end
    for _, child in ipairs(incoming) do
        if child.Parent == root then
            error("managed rig replacement: staged child requires a separate staging container")
        end
        if child.Name:sub(1, 20) == "_Game1RigSwapPending" then
            error("managed rig replacement: reserved staging name")
        end
        if incomingNames[child.Name] then
            error("managed rig replacement: duplicate incoming child name " .. child.Name)
        end
        incomingNames[child.Name] = true
        local collision = root:FindFirstChild(child.Name)
        if collision and not outgoingSet[collision] then
            error("managed rig replacement would overwrite unmanaged child " .. child.Name)
        end
    end
    local rootPrimary = root.PrimaryPart
    local primaryPath = nil
    if rootPrimary and outgoingSet[rootPrimary] then
        primaryPath = rootPrimary.Name
    elseif rootPrimary then
        for _, child in ipairs(outgoing) do
            if rootPrimary:IsDescendantOf(child) then
                local segments = {}
                local cursor: Instance? = rootPrimary
                while cursor and cursor ~= root do
                    table.insert(segments, 1, cursor.Name)
                    cursor = cursor.Parent
                end
                primaryPath = segments
                break
            end
        end
    end
    local newPrimary: BasePart? = nil
    if primaryPath then
        if typeof(primaryPath) == "string" then
            for _, child in ipairs(incoming) do
                if child.Name == primaryPath and child:IsA("BasePart") then newPrimary = child end
            end
        else
            for _, child in ipairs(incoming) do
                if child.Name == primaryPath[1] then
                    local candidate: Instance? = child
                    for index = 2, #primaryPath do
                        candidate = if candidate then candidate:FindFirstChild(primaryPath[index]) else nil
                    end
                    if candidate and candidate:IsA("BasePart") then newPrimary = candidate end
                end
            end
        end
        if not newPrimary then
            error("managed rig replacement: published rig lacks matching PrimaryPart")
        end
    end
    local old = {}
    for index, child in ipairs(outgoing) do
        table.insert(old, {object = child, name = child.Name,
            pendingName = "_Game1RigSwapPending_" .. tostring(index)})
    end
    return {root = root, parent = root.Parent, pivot = root:GetPivot(),
        scale = root:GetScale(), primary = rootPrimary, newPrimary = newPrimary,
        old = old, incoming = incoming, committed = false, finished = false}
end

function RigSwap.Rollback(plan: any)
    if plan.finished then error("cannot roll back finalized rig replacement") end
    for _, child in ipairs(plan.incoming) do
        if child.Parent == plan.root then child.Parent = nil end
        child:Destroy()
    end
    for _, entry in ipairs(plan.old) do
        if entry.object.Parent == plan.root then entry.object.Name = entry.name end
    end
    plan.root.PrimaryPart = plan.primary
    if not plan.primary then plan.root.WorldPivot = plan.pivot end
    plan.committed = false
end

function RigSwap.Commit(plan: any)
    if plan.finished or plan.committed or plan.root.Parent ~= plan.parent then
        error("managed rig replacement transaction is stale")
    end
    local ok, reason = pcall(function()
        for _, entry in ipairs(plan.old) do
            if entry.object.Parent ~= plan.root or entry.object.Name ~= entry.name then
                error("managed rig changed since preflight")
            end
            entry.object.Name = entry.pendingName
        end
        for _, child in ipairs(plan.incoming) do child.Parent = plan.root end
        if plan.newPrimary then
            plan.root.PrimaryPart = plan.newPrimary
        elseif not plan.primary then
            -- WorldPivot is editor metadata; setting it does not move any part.
            -- Without this, Roblox auto-pivot may change when geometry changes.
            plan.root.WorldPivot = plan.pivot
        end
        if not sameFrame(plan.root:GetPivot(), plan.pivot)
            or math.abs(plan.root:GetScale() - plan.scale) > 0.000001
            or plan.root.Parent ~= plan.parent then
            error("placed root pivot, scale or parent changed; transaction rolled back")
        end
    end)
    if not ok then
        RigSwap.Rollback(plan)
        error(tostring(reason), 2)
    end
    plan.committed = true
end

function RigSwap.Finalize(plan: any)
    if not plan.committed or plan.finished then error("rig replacement is not committed") end
    -- The only destruction is of managed OLD CHILD RIGS, never of a placed root.
    for _, entry in ipairs(plan.old) do entry.object:Destroy() end
    plan.finished = true
end

return table.freeze(RigSwap)
