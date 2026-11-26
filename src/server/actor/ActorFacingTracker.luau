-- Physics-owned yaw tracking for actors attacking a moving target.
-- Never teleport/assign the HumanoidRootPart CFrame on Heartbeat: doing so
-- fights the Humanoid solver and creates replication corrections at high speed.
local RunService = game:GetService("RunService")

local Tracker = {}
local active: {[Model]: any} = {}
local connected = false

local TURN_RESPONSE = 12
local MAX_TURN_RATE = math.rad(420)
local MAX_TORQUE = 10000000

local function release(entry)
    if entry.align then entry.align:Destroy() end
    if entry.attachment then entry.attachment:Destroy() end
    if entry.humanoid.Parent then
        entry.humanoid.AutoRotate = entry.autoRotate
    end
end

local function stop(model: Model)
    local entry = active[model]
    if not entry then return end
    active[model] = nil
    release(entry)
end

local function updateGoal(entry, targetRoot: BasePart)
    local delta = targetRoot.Position - entry.root.Position
    local flat = Vector3.new(delta.X, 0, delta.Z)
    if flat.Magnitude > 0.01 then
        -- Only the constraint goal rotates; the solver owns the physical root.
        entry.align.CFrame = CFrame.lookAlong(Vector3.zero, flat.Unit, Vector3.yAxis)
    end
end

local function step(_dt: number)
    for model, entry in pairs(active) do
        local root = entry.root
        local targetRoot = entry.resolve(entry.target)
        if not root.Parent or not model.Parent or not entry.humanoid.Parent
            or model:GetAttribute("LifeState") ~= "Alive" then
            stop(model)
            continue
        end
        if not targetRoot or not targetRoot.Parent then continue end
        updateGoal(entry, targetRoot)
    end
end

function Tracker.Track(model: Model, root: BasePart, humanoid: Humanoid, target: Model, resolver: (Model) -> BasePart?, rigid: boolean?)
    local entry = active[model]
    if entry then
        if entry.root ~= root or entry.humanoid ~= humanoid then
            stop(model)
        else
            entry.target = target
            entry.resolve = resolver
            entry.align.RigidityEnabled = rigid == true
            if rigid then
                local targetRoot = resolver(target)
                if targetRoot and targetRoot.Parent then updateGoal(entry, targetRoot) end
            end
            return
        end
    end
    local attachment = Instance.new("Attachment")
    attachment.Name = "Game1FacingAttachment"
    attachment.Parent = root
    local align = Instance.new("AlignOrientation")
    align.Name = "Game1AttackFacing"
    align.Mode = Enum.OrientationAlignmentMode.OneAttachment
    align.Attachment0 = attachment
    align.RigidityEnabled = rigid == true
    align.ReactionTorqueEnabled = false
    align.Responsiveness = TURN_RESPONSE
    align.MaxAngularVelocity = MAX_TURN_RATE
    align.MaxTorque = MAX_TORQUE
    align.CFrame = root.CFrame.Rotation
    align.Parent = root
    active[model] = {
        root = root, humanoid = humanoid, target = target, resolve = resolver,
        autoRotate = humanoid.AutoRotate, attachment = attachment, align = align,
    }
    humanoid.AutoRotate = false
    if rigid then
        local targetRoot = resolver(target)
        if targetRoot and targetRoot.Parent then updateGoal(active[model], targetRoot) end
    end
    if not connected then
        connected = true
        RunService.Heartbeat:Connect(step)
    end
end

Tracker.Stop = stop
return table.freeze(Tracker)
