-- NPC client compositor: same lower-body attack locomotion as monsters,
-- but with the weapon-type movement policy supplied by the server.
-- No hit, pathfinding or animation-state authority on the client.
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local Config = require(script.Parent:WaitForChild("ActorAnimationCompositionConfig"))
local Skeleton = require(script.Parent:WaitForChild("ActorSkeletonMap"))
local Sampler = require(script.Parent:WaitForChild("ActorLocomotionSampler"))
local Pool = require(script.Parent:WaitForChild("ActorSamplerPool"))
local LowerBodyPose = require(script.Parent:WaitForChild("ActorLowerBodyPose"))

local LocalVisibility = require(script.Parent:WaitForChild("MnpcLocalVisibility"))
local RigObserver = require(script.Parent:WaitForChild("MnpcRigObserver"))
local Controller = {}
local started = false
local entries = {}
local active = {}
local warned = {}

local function warnOnce(key: string, message: string)
    if warned[key] then return end
    warned[key] = true
    warn("[game1][npc-locomotion] " .. message)
end

local function release(entry)
    if not entry.sampler then return end
    local sampler = entry.sampler
    entry.sampler = nil
    Pool:Release(sampler)
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
    if entry.acquiring or os.clock() < (entry.retrySamplerAt or 0) then return false end
    local animationId = tostring(entry.model:GetAttribute("NpcAttackPursuitAnimationId") or "")
    if not animationId:match("^%d+$") or animationId == "0" then return false end
    local key = "npc|" .. tostring(entry.model:GetAttribute("NpcSlug")) .. "|" .. animationId
    local phase = tonumber(entry.model:GetAttribute("NpcAttackPursuitPhase")) or 0
    local speed = tonumber(entry.model:GetAttribute("NpcAttackPursuitPlaybackSpeed")) or 1
    entry.acquiring = true
    local sampler, err = Pool:Acquire(key, function()
        return Sampler.new(entry.visual, animationId, speed, phase)
    end, speed, phase)
    entry.acquiring = false
    if not sampler then
        if err ~= "budget" then
            warnOnce(key, tostring(err or "cannot sample locomotion"))
            entry.retrySamplerAt = os.clock() + 2
        end
        return false
    end
    if entries[entry.model] ~= entry or not entry.model.Parent
        or not entry.root.Parent or not entry.visual.Parent
        or entry.model:GetAttribute("LifeState") ~= "Alive"
        or entry.model:GetAttribute("NpcAttackPursuitActive") ~= true or not LocalVisibility.Full(entry.model) then
        Pool:Release(sampler)
        return false
    end
    entry.sampler = sampler
    return true
end

local function bind(model: Model)
    if entries[model] or model:GetAttribute("Game1NpcRuntime") ~= true then return end
    local visual = model:FindFirstChild("ImportedRig")
    local root = model:FindFirstChild("HumanoidRootPart")
    if not visual or not visual:IsA("Model") or not root or not root:IsA("BasePart") then return end
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
    table.insert(entry.connections, model.AncestryChanged:Connect(function()
        if not model:IsDescendantOf(Workspace) then unbind(model) end
    end))
    if model:GetAttribute("NpcAttackPursuitActive") == true then active[entry] = true end
end

local function bindFolder(folder: Folder)
    RigObserver.Watch(folder, entries, bind, unbind)
end

local function step(dt: number)
    local camera = Workspace.CurrentCamera
    if not camera then return end
    for entry in pairs(active) do
        if not entry.model.Parent or not entry.root.Parent or not entry.visual.Parent then
            unbind(entry.model)
            continue
        end
        if entry.model:GetAttribute("LifeState") ~= "Alive" or not LocalVisibility.Full(entry.model) then
            entry.weight = 0
            release(entry)
            active[entry] = nil
            continue
        end
        local wants = entry.model:GetAttribute("NpcAttackPursuitActive") == true
            and entry.model:GetAttribute("LifeState") == "Alive"
            and (entry.root.Position - camera.CFrame.Position).Magnitude <= Config.MaxDistance
        if wants and not entry.sampler then
            acquire(entry)
        end
        local sampler = entry.sampler
        if sampler then
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
                -- Keep distant pursuit entries eligible when the camera returns;
                -- the server attribute may remain true without another event.
                if entry.model:GetAttribute("NpcAttackPursuitActive") ~= true
                    or entry.model:GetAttribute("LifeState") ~= "Alive" then active[entry] = nil end
            end
        elseif entry.model:GetAttribute("NpcAttackPursuitActive") ~= true
            or entry.model:GetAttribute("LifeState") ~= "Alive" then
            active[entry] = nil
        end
    end
    Pool:Cleanup(os.clock())
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
