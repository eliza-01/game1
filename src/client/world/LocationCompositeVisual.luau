--!strict
-- Visual-only adapter to the existing LocationWorldStreamer; NO tick or
-- independent distance calculations. All rig_carrier Bones, attachments,
-- animation controllers, fire and lights remain server-owned in Workspace.
-- Recreated visual meshes are welded to their original Part proxies.
local Workspace = game:GetService("Workspace")
local Adapter = {}
local Job = require(script.Parent:WaitForChild("LodAssemblyJob"))

local function rootFor(path: {string}): Model?
    local current: Instance = Workspace
    for _, segment in ipairs(path) do
        local child = current:FindFirstChild(segment)
        if not child then return nil end
        current = child
    end
    if current:IsA("Model") then return current end
    return nil
end

-- Server retains the authored effect instances and all their live links.
-- Client-only visibility is part of the SAME distance scheduler as the
-- MeshParts, not a second Heartbeat or a destructive effect reconstruction.
local function visualEffect(obj: Instance): boolean
    return obj:IsA("Light") or obj:IsA("Fire") or obj:IsA("Smoke")
        or obj:IsA("Sparkles") or obj:IsA("ParticleEmitter")
        or obj:IsA("Beam") or obj:IsA("Trail")
end

function Adapter.SetEffects(record: any, active: boolean)
    local root = rootFor(record.modelPath)
    if not root then
        record.effectRoot = nil
        record.effectDefaults = nil
        record.effectState = nil
        return
    end
    if record.effectRoot ~= root then
        record.effectRoot = root
        record.effectDefaults = {}
        record.effectState = nil
    end
    if record.effectState == active then return end
    for _, descendant in ipairs(root:GetDescendants()) do
        if visualEffect(descendant) then
            local defaults = record.effectDefaults
            if defaults[descendant] == nil then
                defaults[descendant] = descendant.Enabled
            end
            descendant.Enabled = active and defaults[descendant] or false
        end
    end
    record.effectState = active
end

function Adapter.Prepare(prototype: Model, record: any, paint: any, asset: any, metadata: any): (any?, string?)
    local root = rootFor(record.modelPath)
    if not root then return nil, "root unavailable" end
    local job = Job.new(function(work)
        local bundle = work:Own(Instance.new("Folder"))
        bundle.Name = "__Game1RuntimeVisuals"
        work.bundle = bundle
        work:Unit()
        for _, spec in ipairs(record.components) do
            local proxy = root:FindFirstChild(spec.name, true)
            local source = metadata.childrenByName[spec.name]
            if not proxy or not proxy:IsA("Part") or not source or not source:IsA("MeshPart") then
                work.retryable = true
                error("component unavailable")
            end
            work:Unit()
            local part = work:Own(source:Clone())
            work:Unit()
            part.Size = proxy.Size
            part.CFrame = proxy.CFrame
            part.Anchored = false
            part.CanCollide = false
            part.CanTouch = false
            part.CanQuery = false
            paint(part, asset)
            work:Unit()
            part.Parent = bundle
            work:Unit()
            local joint = work:Own(Instance.new("Weld"))
            joint.Name = "Game1VisualProxyWeld"
            joint.C0 = CFrame.identity
            joint.C1 = CFrame.identity
            joint.Part1 = part
            joint.Parent = part
            -- Part0 remains unset until atomic commit, so staging never joins
            -- a server-owned assembly or changes the active physical rig.
            work.links[#work.links+1] = {proxy=proxy, part=part, joint=joint, name=spec.name}
            work:Unit()
        end
    end)
    job.root = root
    job.links = {}
    return job, nil
end

function Adapter.RootAlive(job: any, record: any): boolean
    return rootFor(record.modelPath) == job.root
end

-- Validate every link before mutating anything. This is an explicitly reserved
-- non-yielding commit batch (at most 64 proxy validations and 64 bindings).
function Adapter.BindForCommit(job: any, record: any): boolean
    if not Adapter.RootAlive(job, record) then return false end
    for _, entry in ipairs(job.links) do
        if job.root:FindFirstChild(entry.name, true) ~= entry.proxy then return false end
    end
    for _, entry in ipairs(job.links) do
        entry.part.Size = entry.proxy.Size
        entry.part.CFrame = entry.proxy.CFrame
        entry.joint.Part0 = entry.proxy
    end
    return true
end

return table.freeze(Adapter)
