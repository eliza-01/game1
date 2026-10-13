-- One server-owned yaw tracker shared by NPC and monster attacks.
-- Physics/navigation still owns translation; no per-actor threads or bone hacks.
local RunService = game:GetService("RunService")
local Tracker = {}
local active: {[Model]: any} = {}
local connected = false
local TURN_RESPONSE = 10 -- exponential responsiveness (1/s)
local MAX_TURN_RATE = math.rad(420) -- physical yaw cap in radians/s

local function stop(model: Model)
    local entry = active[model]
    if not entry then return end
    active[model] = nil
    if entry.humanoid.Parent then
        entry.humanoid.AutoRotate = entry.autoRotate
    end
end

local function step(dt: number)
    for model, entry in pairs(active) do
        local root = entry.root
        local target = entry.target
        local targetRoot = entry.resolve(target)
        if not root.Parent or not model.Parent or not entry.humanoid.Parent
            or model:GetAttribute("LifeState") ~= "Alive" then
            stop(model)
            continue
        end
        if not targetRoot or not targetRoot.Parent then continue end
        local delta = targetRoot.Position - root.Position
        local flat = Vector3.new(delta.X, 0, delta.Z)
        if flat.Magnitude <= 0.01 then continue end
        local desired = flat.Unit
        local look = root.CFrame.LookVector
        local current = Vector3.new(look.X, 0, look.Z)
        if current.Magnitude <= 0.001 then current = desired else current = current.Unit end
        local cross = current.X * desired.Z - current.Z * desired.X
        local dot = math.clamp(current:Dot(desired), -1, 1)
        local angle = math.atan2(cross, dot)
        local absolute = math.abs(angle)
        if absolute <= 0.00001 then continue end
        local response = 1 - math.exp(-TURN_RESPONSE * math.clamp(dt, 0, 0.25))
        local stepAngle = math.min(absolute * response, MAX_TURN_RATE * math.max(0, dt))
        local sign = if angle < 0 then -1 else 1
        local yaw = CFrame.fromAxisAngle(Vector3.yAxis, -sign * stepAngle)
        local nextDirection = yaw:VectorToWorldSpace(current)
        root.CFrame = CFrame.lookAt(root.Position, root.Position + nextDirection, Vector3.yAxis)
    end
end

function Tracker.Track(model: Model, root: BasePart, humanoid: Humanoid, target: Model, resolver: (Model) -> BasePart?)
    local entry = active[model]
    if entry then
        entry.target = target
        entry.resolve = resolver
        return
    end
    if not connected then
        connected = true
        RunService.Heartbeat:Connect(step)
    end
    active[model] = {
        root = root, humanoid = humanoid, target = target,
        resolve = resolver, autoRotate = humanoid.AutoRotate,
    }
    humanoid.AutoRotate = false
end

Tracker.Stop = stop
return table.freeze(Tracker)
