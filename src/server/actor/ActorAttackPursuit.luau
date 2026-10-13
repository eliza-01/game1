-- Shared in-attack pursuit for NPCs and monsters. Movement stays Humanoid-owned.
-- A filtered target velocity and acceleration-limited WalkSpeed prevent rapid
-- speed/start/stop thrashing as two actors travel at similar high speeds.
local Pursuit = {}
Pursuit.__index = Pursuit

local STOP_MARGIN = 0.35
local FOLLOW_GAIN = 5.5
local MIN_CATCHUP = 0.75
local ENTER_SPEED = 0.45
local EXIT_SPEED = 0.12
local TARGET_FILTER_RESPONSE = 10 -- /second
local MAX_ACCELERATION = 65 -- studs/s^2

local function horizontal(vector: Vector3): Vector3
    return Vector3.new(vector.X, 0, vector.Z)
end

function Pursuit.new(root: BasePart, humanoid: Humanoid)
    return setmetatable({
        root = root, humanoid = humanoid, active = false,
        filteredRetreat = nil, commandedSpeed = 0, lastStep = nil,
    }, Pursuit)
end

function Pursuit:Stop()
    self.filteredRetreat = nil
    self.commandedSpeed = 0
    self.lastStep = nil
    if not self.active then return end
    self.active = false
    if self.humanoid.Parent then
        self.humanoid:Move(Vector3.zero, false)
        self.humanoid.WalkSpeed = 0
    end
end

-- Returns locomotion activity and commanded world speed (studs/sec).
-- The attack timer/animation are not owned or modified by this component.
function Pursuit:Step(targetRoot: BasePart, attackRadius: number, maximumSpeed: number): (boolean, number)
    if maximumSpeed <= 0 or not self.root.Parent or not self.humanoid.Parent then
        self:Stop()
        return false, 0
    end
    local offset = horizontal(targetRoot.Position - self.root.Position)
    local distance = offset.Magnitude
    if distance <= 0.001 then
        self:Stop()
        return false, 0
    end
    local direction = offset.Unit
    local now = os.clock()
    local dt = if self.lastStep then math.clamp(now - self.lastStep, 0.001, 0.10) else 0.05
    self.lastStep = now
    local retreat = math.max(0, horizontal(targetRoot.AssemblyLinearVelocity):Dot(direction))
    local velocityAlpha = 1 - math.exp(-TARGET_FILTER_RESPONSE * dt)
    self.filteredRetreat = if self.filteredRetreat then self.filteredRetreat + (retreat - self.filteredRetreat) * velocityAlpha else retreat
    local preferred = math.max(0, attackRadius - STOP_MARGIN)
    local errorDistance = math.max(0, distance - preferred)
    local desired = math.min(maximumSpeed, self.filteredRetreat + errorDistance * FOLLOW_GAIN)
    if distance > attackRadius then
        desired = math.max(desired, math.min(maximumSpeed, self.filteredRetreat + MIN_CATCHUP))
    end
    if desired <= (if self.active then EXIT_SPEED else ENTER_SPEED) then
        self:Stop()
        return false, 0
    end
    -- Bound changes of commanded speed without decreasing the target-following cap.
    local change = MAX_ACCELERATION * dt
    local speed = math.clamp(desired, math.max(0, self.commandedSpeed - change), self.commandedSpeed + change)
    self.commandedSpeed = speed
    self.active = true
    self.humanoid.WalkSpeed = speed
    -- ActorFacingTracker owns yaw while attacks run, Move owns translation.
    self.humanoid:Move(direction, false)
    return true, speed
end

return table.freeze(Pursuit)
