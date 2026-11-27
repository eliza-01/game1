-- Samples a single bound root without writes, scans, or per-frame network traffic.
local Statistics = require(script.Parent:WaitForChild("NetworkMotionStatistics"))
local Capture = {}
local function horizontal(v)
    return math.sqrt(v.X * v.X + v.Z * v.Z)
end
function Capture.Root(player)
    local character = player.Character
    local root = character and character:FindFirstChild("NavigationRoot")
    if root and root:IsA("BasePart") and root:IsDescendantOf(workspace) then return root end
    return nil
end
function Capture.New(player, startAt, rendered)
    local root = Capture.Root(player)
    if not root then return nil end
    return {player = player, root = root, startAt = startAt, endAt = startAt + Statistics.Duration,
        rendered = rendered, stats = Statistics.New()}
end
function Capture.Step(session, now)
    if now < session.startAt then return false end
    local root = session.root
    if not root.Parent or session.player.Character ~= root.Parent then return true, "character changed" end
    local sampledAt = os.clock()
    local position = root.Position
    local rendered = session.rendered and root:GetRenderCFrame().Position or nil
    if session.previousAt then
        local dt = sampledAt - session.previousSampledAt
        if dt <= 0 then return false end
        local keep = Statistics.Add(session.stats, dt, horizontal(position - session.previous),
            rendered and horizontal(rendered - session.previousRender) or nil, horizontal(root.AssemblyLinearVelocity))
        if not keep then return true, "sample limit" end
    else
        if now >= session.endAt then return true, "capture window missed" end
        session.actualStart = now
    end
    session.previousAt = now
    session.previousSampledAt = sampledAt
    session.previous = position
    session.previousRender = rendered
    return now >= session.endAt
end
function Capture.Finish(session, reason)
    local report = Statistics.Finish(session.stats)
    report.actualStart = session.actualStart or 0
    report.actualEnd = session.previousAt or 0
    report.reason = reason or "complete"
    report.target = session.player.Name
    return report
end
return Capture
