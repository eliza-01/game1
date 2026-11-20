--!strict
-- Visual-only adapter to the existing LocationWorldStreamer; NO tick or
-- independent distance calculations. All rig_carrier Bones, attachments,
-- animation controllers, fire and lights remain server-owned in Workspace.
-- Recreated visual meshes are welded to their original Part proxies.
local Workspace = game:GetService("Workspace")
local Adapter = {}

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

function Adapter.Create(prototype: Model, record: any, paint: any, asset: any): Folder?
    local root = rootFor(record.modelPath)
    if not root then return nil end -- Roblox's own streaming may defer the technical root
    local confirmed = {}
    for _, spec in ipairs(record.components) do
        local proxy = root:FindFirstChild(spec.name, true)
        local source = prototype:FindFirstChild(spec.name)
        if not proxy or not proxy:IsA("Part") or not source or not source:IsA("MeshPart") then
            return nil -- never draw a detached or visually incomplete rig
        end
        table.insert(confirmed, {proxy = proxy, source = source})
    end
    local bundle = Instance.new("Folder")
    bundle.Name = "__Game1RuntimeVisuals"
    local ok, problem = pcall(function()
        for index, entry in ipairs(confirmed) do
            local proxy: Part = entry.proxy
            local part: MeshPart = entry.source:Clone()
            part.Size = proxy.Size
            part.CFrame = proxy.CFrame
            part.Anchored = false
            part.CanCollide = false
            part.CanTouch = false
            part.CanQuery = false
            paint(part, asset)
            part.Parent = bundle
            -- The server's original carrier, joints and Bone animation drive
            -- proxy CFrames; the client does not create a second skeleton.
            local joint = Instance.new("Weld")
            joint.Name = "Game1VisualProxyWeld"
            joint.C0 = CFrame.identity
            joint.C1 = CFrame.identity
            joint.Part0 = proxy
            joint.Part1 = part
            joint.Parent = part
        end
    end)
    if not ok then
        warn("[game1][LOD] composite visual assembly failed: " .. tostring(problem))
        bundle:Destroy()
        return nil
    end
    bundle.Parent = root -- same root as the original server-owned rig_carrier
    return bundle
end

return table.freeze(Adapter)
