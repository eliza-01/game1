-- NPC client compositor: same lower-body attack locomotion as monsters,
-- but with the weapon-type movement policy supplied by the server.
-- No hit, pathfinding or animation-state authority on the client.
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local Config = require(script.Parent:WaitForChild("ActorAnimationCompositionConfig"))
local Skeleton = require(script.Parent:WaitForChild("ActorSkeletonMap"))
local Sampler = require(script.Parent:WaitForChild("ActorLocomotionSampler"))
local LowerBodyPose = require(script.Parent:WaitForChild("ActorLowerBodyPose"))

local Controller = {}
local started = false
local entries = {}
local active = {}
local recycled = {}
local serial = 0
local lastCleanup = 0
local warned = {}

local function warnOnce(key: string, message: string)
    if warned[key] then return end
    warned[key] = true
    warn("[game1][npc-locomotion] " .. message)
end

local function release(entry)
    if not entry.sampler then return end
    entry.sampler.users = math.max(0, entry.sampler.users - 1)
    entry.sampler:Touch()
    entry.sampler = nil
end

local function unbind(model: Model)
    local entry = entries[model]
    if not entry then return end
    for _, conn in ipairs(entry.connections) do conn:Disconnect() end
    release(entry)
    entries[model] = nil
    active[entry] = nil
end

local function acquire(entry): boolean
    if entry.sampler then return true end
    local animationId = tostring(entry.model:GetAttribute("NpcAttackPursuitAnimationId") or "")
    if not animationId:match("^%d+$") or animationId == "0" then return false end
    local key = tostring(entry.model:GetAttribute("NpcSlug")) .. "|" .. animationId
    local sampler
    for _, candidate in pairs(recycled) do
        if candidate.baseKey == key and candidate.users == 0 then
            sampler = candidate
            break
        end
    end
    local phase = tonumber(entry.model:GetAttribute("NpcAttackPursuitPhase")) or 0
    local speed = tonumber(entry.model:GetAttribute("NpcAttackPursuitPlaybackSpeed")) or 1
    if not sampler then
        local created, err = Sampler.new(entry.visual, animationId, speed, phase)
        if not created then
            warnOnce(key, tostring(err or "cannot sample locomotion"))
            return false
        end
        sampler = created
        sampler.baseKey = key
        serial += 1
        recycled[key .. "#" .. tostring(serial)] = sampler
    else
        sampler:SetPhase(phase)
        sampler:SetPlaybackSpeed(speed)
    end
    sampler.users = 1
    sampler:Touch()
    entry.sampler = sampler
    return true
end

local function bind(model: Model)
    if entries[model] or model:GetAttribute("Game1NpcRuntime") ~= true then return end
    local visual = model:FindFirstChild("ImportedRig") or model
    local root = model:FindFirstChild("HumanoidRootPart")
    if not visual:IsA("Model") or not root or not root:IsA("BasePart") then return end
    local lower = Skeleton.ResolveLowerBodyPaths(visual)
    if #lower == 0 then return end
    local entry = {
        model = model, visual = visual, root = root,
        targetBones = Skeleton.BuildBonePathMap(visual),
        lowerPaths = lower,
        lowerRootPaths = Skeleton.ResolveIndependentLowerBodyRoots(visual, lower),
        visualRootOffsetRotation = root.CFrame:ToObjectSpace(visual:GetPivot()).Rotation,
        weight = 0, sampler = nil, connections = {},
    }
    entries[model] = entry
    table.insert(entry.connections, model:GetAttributeChangedSignal("NpcAttackPursuitActive"):Connect(function()
        if model:GetAttribute("NpcAttackPursuitActive") == true then active[entry] = true end
    end))
    table.insert(entry.connections, model:GetAttributeChangedSignal("NpcAttackPursuitPlaybackSpeed"):Connect(function()
        if entry.sampler then
            entry.sampler:SetPlaybackSpeed(tonumber(model:GetAttribute("NpcAttackPursuitPlaybackSpeed")) or 1)
        end
    end))
    table.insert(entry.connections, model.Destroying:Connect(function() unbind(model) end))
    if model:GetAttribute("NpcAttackPursuitActive") == true then active[entry] = true end
end

-- Model, attributes and navigation root do not necessarily replicate in order.
local function watchModel(model: Model)
    task.spawn(function()
        local deadline = os.clock() + 5
        while model.Parent and not entries[model] and os.clock() < deadline do
            if model:GetAttribute("Game1NpcRuntime") == true
                and model:FindFirstChild("HumanoidRootPart") then
                bind(model)
                return
            end
            task.wait(0.1)
        end
    end)
end

local function bindFolder(folder: Folder)
    for _, child in ipairs(folder:GetChildren()) do
        if child:IsA("Model") then watchModel(child) end
    end
    folder.ChildAdded:Connect(function(child)
        if child:IsA("Model") then watchModel(child) end
    end)
end

local function step(dt: number)
    local camera = Workspace.CurrentCamera
    if not camera then return end
    local composed = 0
    for entry in pairs(active) do
        if not entry.model.Parent or not entry.root.Parent or not entry.visual.Parent then
            unbind(entry.model)
            continue
        end
        local wants = entry.model:GetAttribute("NpcAttackPursuitActive") == true
            and entry.model:GetAttribute("LifeState") == "Alive"
            and (entry.root.Position - camera.CFrame.Position).Magnitude <= Config.MaxDistance
        if wants and not entry.sampler and composed < Config.MaxComposedActors then acquire(entry) end
        local sampler = entry.sampler
        if sampler then
            composed += 1
            sampler:AnchorNear(camera.CFrame, os.clock(), Config.SamplerAnchorInterval)
            local goal = if wants then 1 else 0
            local duration = if goal == 1 then Config.EntryBlendSeconds else Config.ExitBlendSeconds
            local alpha = if duration > 0 then math.clamp(dt / duration, 0, 1) else 1
            entry.weight += (goal - entry.weight) * alpha
            if entry.weight > 0.001 and sampler:IsReady() then
                for _, path in ipairs(entry.lowerPaths) do
                    local targetBone = entry.targetBones[path]
                    local sourceBone = sampler:GetBone(path)
                    if targetBone and targetBone.Parent and sourceBone and sourceBone.Parent then
                        targetBone.Transform = targetBone.Transform:Lerp(sourceBone.Transform, entry.weight)
                    end
                end
                LowerBodyPose.AlignToMovement(entry, dt)
            end
            if entry.weight < 0.01 and not wants then
                entry.weight = 0
                release(entry)
                active[entry] = nil
            end
        elseif not wants then
            active[entry] = nil
        end
    end
    local now = os.clock()
    if now - lastCleanup >= 2 then
        lastCleanup = now
        for key, sampler in pairs(recycled) do
            if sampler.users == 0 and now - sampler.lastUsedAt >= Config.SamplerIdleTtlSeconds then
                sampler:Destroy()
                recycled[key] = nil
            end
        end
    end
end

function Controller.Start()
    if started then return end
    started = true
    local folder = Workspace:FindFirstChild("NPCs")
    if folder and folder:IsA("Folder") then bindFolder(folder) end
    Workspace.ChildAdded:Connect(function(child)
        if child:IsA("Folder") and child.Name == "NPCs" then bindFolder(child) end
    end)
    RunService.PreSimulation:Connect(step)
end

return table.freeze(Controller)
