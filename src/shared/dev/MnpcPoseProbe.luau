-- M627 Studio-only fixture helpers. No actor registrations or runtime consumers.
local RunService = game:GetService("RunService")
local CollectionService = game:GetService("CollectionService")
local Probe = {}
Probe.FolderName = "Game1MnpcPoseProbe"

function Probe.AssertStudio()
    assert(RunService:IsStudio() and RunService:IsRunning(), "MNPC probe requires Studio Play")
end

local function clearIdentity(instance: Instance)
    for _, tag in ipairs(CollectionService:GetTags(instance)) do
        CollectionService:RemoveTag(instance, tag)
    end
    for key in pairs(instance:GetAttributes()) do instance:SetAttribute(key, nil) end
end

local function copyBones(source: Instance, target: Instance)
    for _, child in ipairs(source:GetChildren()) do
        if child:IsA("Bone") then
            local bone = Instance.new("Bone")
            bone.Name = child.Name
            bone.CFrame = child.CFrame
            bone.Parent = target
            copyBones(child, bone)
        end
    end
end

-- The reference keeps mesh skin data; the experimental carrier has only Parts
-- and rest Bones. Preserve the authored names/hierarchy used by native binding.
function Probe.Build(visual: Model, meshReference: boolean): Model
    Probe.AssertStudio()
    local model = Instance.new("Model")
    model.Name = visual.Name
    local ancestors = {[visual] = model}
    local function parentFor(source: Instance): Instance
        if ancestors[source] then return ancestors[source] end
        assert(source:IsA("Model") or source:IsA("Folder"), "unsupported skeleton ancestor: " .. source.ClassName)
        local parent = parentFor(assert(source.Parent))
        local copy = Instance.new(source.ClassName)
        copy.Name = source.Name
        copy.Parent = parent
        ancestors[source] = copy
        return copy
    end
    local ok, err = pcall(function()
        local sourceBones = Probe.Bones(visual)
        local count = 0
        for _, source in ipairs(visual:GetDescendants()) do
            if source:IsA("MeshPart") and source:FindFirstChildOfClass("Bone") then
                count += 1
                local part: BasePart
                if meshReference then
                    part = assert(source:Clone(), "non-archivable mesh")
                    -- Keep the cloned Bone tree intact; discard any unrelated content
                    -- before parenting into the DataModel (scripts, constraints, etc).
                    for _, child in ipairs(part:GetDescendants()) do
                        if child:IsA("Bone") then
                            clearIdentity(child)
                            child.Transform = CFrame.identity
                        elseif child.Parent then child:Destroy() end
                    end
                else
                    part = Instance.new("Part")
                    copyBones(source, part)
                end
                clearIdentity(part)
                part.Name = source.Name
                part.Size = source.Size
                part.CFrame = source.CFrame + Vector3.new(0, 8, 0)
                part.Anchored = true
                part.CanCollide = false
                part.CanTouch = false
                part.CanQuery = false
                part.CastShadow = false
                part.Transparency = 1
                part.Parent = parentFor(assert(source.Parent))
            end
        end
        assert(count > 0, "no skinned MeshPart with direct Bones")
        -- Reject duplicate animation paths, rather than comparing arbitrary bones.
        local copied = Probe.Bones(model)
        for path in pairs(sourceBones) do assert(copied[path], "unsupported/missing source bone: " .. path) end
        for path in pairs(copied) do assert(sourceBones[path], "unexpected copied bone: " .. path) end
    end)
    if not ok then model:Destroy(); error(err) end
    return model
end

function Probe.Bones(model: Model): {[string]: Bone}
    local result = {}
    for _, bone in ipairs(model:GetDescendants()) do
        if bone:IsA("Bone") then
            local components = {}
            local node: Instance? = bone
            while node and node ~= model do
                table.insert(components, 1, tostring(#node.Name) .. ":" .. node.Name)
                node = node.Parent
            end
            local path = table.concat(components, "/")
            assert(not result[path], "duplicate bone path: " .. path)
            result[path] = bone
        end
    end
    return result
end

function Probe.Frames(model: Model): {[string]: CFrame}
    local frames = {}
    for path, bone in pairs(Probe.Bones(model)) do
        -- Same transformed frame consumed by HitboxRuntimeFrames, in mesh-local space.
        local root = bone.Parent
        while root and root:IsA("Bone") do root = root.Parent end
        assert(root and root:IsA("BasePart"), "invalid bone root")
        frames[path] = root.CFrame:ToObjectSpace(bone.TransformedWorldCFrame)
    end
    return frames
end

function Probe.Compare(a: {[string]: CFrame}, b: {[string]: CFrame}): any
    local count, missing, position, angle = 0, 0, 0, 0
    for path, frame in pairs(a) do
        if not b[path] then missing += 1 else
            count += 1
            local delta = frame:ToObjectSpace(b[path])
            local _, radians = delta:ToAxisAngle()
            position = math.max(position, delta.Position.Magnitude)
            angle = math.max(angle, math.abs(math.deg(radians)))
        end
    end
    for path in pairs(b) do if not a[path] then missing += 1 end end
    return {bones = count, missing = missing, maxStuds = position, maxDegrees = angle}
end

function Probe.Load(model: Model, animationId: string): (Animator, AnimationTrack)
    local controller = Instance.new("AnimationController")
    controller.Parent = model
    local animator = Instance.new("Animator")
    animator.Parent = controller
    local animation = Instance.new("Animation")
    animation.AnimationId = animationId
    animation.Parent = controller
    local track = animator:LoadAnimation(animation)
    track.Priority = Enum.AnimationPriority.Action4
    track.Looped = true
    track:Play(0, 1, 0)
    return animator, track
end

function Probe.WaitLoaded(track: AnimationTrack): boolean
    local deadline = os.clock() + 8
    while track.Length <= 0 and os.clock() < deadline do RunService.Heartbeat:Wait() end
    return track.Length > 0
end

function Probe.WaitFrames(count: number)
    for _ = 1, count do RunService.Heartbeat:Wait() end
end

function Probe.Motion(model: Model, seconds: number): any
    local initial = Probe.Frames(model)
    local maxStuds, maxDegrees, samples, missing = 0, 0, 0, 0
    local deadline = os.clock() + seconds
    repeat
        task.wait(0.15)
        if not model.Parent then return {status = "REMOVED"} end
        local delta = Probe.Compare(initial, Probe.Frames(model))
        maxStuds = math.max(maxStuds, delta.maxStuds)
        maxDegrees = math.max(maxDegrees, delta.maxDegrees)
        missing = math.max(missing, delta.missing)
        samples += 1
    until os.clock() >= deadline
    local animators, tracks, meshes, throttled, throttleReadable = 0, 0, 0, 0, 0
    for _, instance in ipairs(model:GetDescendants()) do
        if instance:IsA("Animator") then
            animators += 1
            tracks += #instance:GetPlayingAnimationTracks()
            local ok, value = pcall(function() return instance.EvaluationThrottled end)
            if ok then
                throttleReadable += 1
                if value then throttled += 1 end
            end
        elseif instance:IsA("MeshPart") then meshes += 1 end
    end
    return {status = "OBSERVED", samples = samples, bones = Probe.Compare(initial, initial).bones,
        meshes = meshes, animators = animators, tracks = tracks, missing = missing,
        throttleReadable = throttleReadable, throttled = throttled, maxStuds = maxStuds, maxDegrees = maxDegrees}
end

return table.freeze(Probe)
