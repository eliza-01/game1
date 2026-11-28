-- Explicit command-bar experiment; never required by game bootstrap.
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local HttpService = game:GetService("HttpService")
local ServerStorage = game:GetService("ServerStorage")
local Probe = require(ReplicatedStorage.Game1Shared.dev.MnpcPoseProbe)
local Service = {}
local running = false

local function report(value: any)
    print("[MNPC627][server] " .. HttpService:JSONEncode(value))
end

local function candidates(): any
    local result = {}
    for _, model in ipairs(workspace:GetDescendants()) do
        if model:IsA("Model") and model:GetAttribute("LifeState") == "Alive" then
            local kind = if model:GetAttribute("Game1MonsterRuntime") == true then "Monster"
                elseif model:GetAttribute("Game1NpcRuntime") == true then "NPC" else nil
            if kind and not result[kind] then
                local visual = model:FindFirstChild("ImportedRig") or model
                local controller = visual:FindFirstChildWhichIsA("AnimationController", true)
                local animator = controller and controller:FindFirstChildOfClass("Animator")
                if animator and controller.Parent == visual and visual:IsA("Model") then
                    for _, track in ipairs(animator:GetPlayingAnimationTracks()) do
                        local id = track.Animation and track.Animation.AnimationId
                        if id and id:match("^rbxassetid://%d+$") and track.Length > 0 and track.WeightCurrent > 0.5 then
                            result[kind] = {visual = visual, animationId = id, name = model.Name}
                            break
                        end
                    end
                end
            end
        end
    end
    return result
end

local function compareCase(kind: string, source: any, world: Folder, templates: Folder)
    local case = Instance.new("Folder")
    case.Name = kind
    case.Parent = world
    local reference = Probe.Build(source.visual, true)
    reference.ModelStreamingMode = Enum.ModelStreamingMode.Persistent
    reference.Parent = case
    local carrier = Probe.Build(source.visual, false)
    carrier.ModelStreamingMode = Enum.ModelStreamingMode.Persistent
    carrier.Parent = case
    -- Keep native binding root name unchanged; object identity is explicit.
    local link = Instance.new("ObjectValue")
    link.Name = "Carrier"
    link.Value = carrier
    link.Parent = case
    -- Persistent fixtures avoid confusing native stream-out with stopped evaluation.
    local refAnimator, refTrack = Probe.Load(reference, source.animationId)
    local _, carrierTrack = Probe.Load(carrier, source.animationId)
    assert(Probe.WaitLoaded(refTrack) and Probe.WaitLoaded(carrierTrack), "animation unavailable or binding load timeout")
    local rest, referenceMoved, allMatch = nil, false, true
    local samples = {}
    for _, phase in ipairs({0.1, 0.35, 0.6, 0.85}) do
        refTrack.TimePosition = refTrack.Length * phase
        carrierTrack.TimePosition = carrierTrack.Length * phase
        Probe.WaitFrames(5)
        local frames = Probe.Frames(reference)
        rest = rest or frames
        local movement = Probe.Compare(rest, frames)
        referenceMoved = referenceMoved or movement.maxStuds > 0.001 or movement.maxDegrees > 0.1
        local delta = Probe.Compare(frames, Probe.Frames(carrier))
        delta.phase = phase
        table.insert(samples, delta)
        allMatch = allMatch and delta.bones > 0 and delta.missing == 0 and delta.maxStuds <= 0.01 and delta.maxDegrees <= 0.5
    end
    report({kind = kind, source = source.name, animationId = source.animationId, samples = samples,
        status = if not referenceMoved then "INCONCLUSIVE_REFERENCE_STATIC" elseif allMatch then "CARRIER_MATCH" else "CARRIER_MISMATCH"})
    -- Test both a fresh private load and a previously loaded carrier moved out
    -- of Workspace. A returned track alone does not establish evaluation.
    local private = Probe.Build(reference, false)
    local privateOk, privateResult = pcall(function()
        private.Parent = ServerStorage
        local _, track = Probe.Load(private, source.animationId)
        if not Probe.WaitLoaded(track) then return {status = "LOAD_TIMEOUT"} end
        track:AdjustSpeed(1)
        return Probe.Motion(private, 1.5)
    end)
    private:Destroy()
    report({kind = kind, experiment = "PRIVATE_LOAD", accepted = privateOk,
        result = if privateOk then privateResult else tostring(privateResult)})

    local moved = Probe.Build(reference, false)
    local moveOk, moveResult = pcall(function()
        moved.Parent = case
        local _, track = Probe.Load(moved, source.animationId)
        if not Probe.WaitLoaded(track) then return {status = "LOAD_TIMEOUT"} end
        track:AdjustSpeed(1)
        local before = Probe.Motion(moved, 1.5)
        moved.Parent = ServerStorage
        local after = Probe.Motion(moved, 1.5)
        return {before = before, after = after}
    end)
    moved:Destroy()
    report({kind = kind, experiment = "MOVE_TO_PRIVATE", accepted = moveOk,
        result = if moveOk then moveResult else tostring(moveResult)})

    -- Reference is no longer a replicated animated mesh. Preserve only a static
    -- template for optional local FULL comparison. No native playback in storage.
    refTrack:Stop(0)
    refAnimator.Parent:Destroy()
    for _, bone in pairs(Probe.Bones(reference)) do bone.Transform = CFrame.identity end
    reference.ModelStreamingMode = Enum.ModelStreamingMode.Default
    local folder = Instance.new("Folder")
    folder.Name = kind
    folder.Parent = templates
    reference.Parent = folder
    case:SetAttribute("AnimationId", source.animationId)
    carrierTrack.TimePosition = 0
    carrierTrack:AdjustSpeed(1)
    case:SetAttribute("Ready", true)
    report({kind = kind, experiment = "REPLICATED_CARRIER", motion = Probe.Motion(carrier, 2)})
end

function Service.Start()
    Probe.AssertStudio()
    assert(RunService:IsServer(), "run in server command bar")
    assert(not running, "probe already running")
    assert(not workspace:FindFirstChild(Probe.FolderName) and not ReplicatedStorage:FindFirstChild(Probe.FolderName), "probe fixtures already exist")
    running = true
    local world = Instance.new("Folder")
    local templates = Instance.new("Folder")
    world.Name = Probe.FolderName
    templates.Name = Probe.FolderName
    world.Parent = workspace
    templates.Parent = ReplicatedStorage
    task.spawn(function()
        local ok, err = xpcall(function()
            local sources = candidates()
            for _, kind in ipairs({"Monster", "NPC"}) do
                if sources[kind] then
                    local success, failure = pcall(compareCase, kind, sources[kind], world, templates)
                    if not success then
                        local case = world:FindFirstChild(kind)
                        if case then case:Destroy() end
                        local template = templates:FindFirstChild(kind)
                        if template then template:Destroy() end
                        report({kind = kind, status = "INCONCLUSIVE", detail = tostring(failure)})
                    end
                else report({kind = kind, status = "SKIPPED_NO_ACTIVE_ACTOR"}) end
            end
            report({status = "CLIENT_OBSERVATION_WINDOW", seconds = 60})
            task.wait(60)
        end, debug.traceback)
        world:Destroy()
        templates:Destroy()
        running = false
        if not ok then warn("[MNPC627][server] " .. tostring(err)) end
        report({status = "CLEANED"})
    end)
end

return table.freeze(Service)
