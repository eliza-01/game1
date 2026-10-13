-- In-attack velocity follower shared independently of target selection/attack timing.
-- Uses the monster continuous Humanoid:Move contract; never issues MoveTo inside a hit.
local Pursuit = {}
Pursuit.__index = Pursuit
local STOP_MARGIN = 0.35
local FOLLOW_GAIN = 5.5
local MIN_CATCHUP = 0.75
local IDLE_EPSILON = 0.08

function Pursuit.new(root: BasePart, humanoid: Humanoid)
    return setmetatable({root = root, humanoid = humanoid, active = false}, Pursuit)
end

function Pursuit:Stop()
    if not self.active then return end
    self.active = false
    if self.humanoid.Parent then
        self.humanoid:Move(Vector3.zero, false)
        self.humanoid.WalkSpeed = 0
    end
end

-- Returns active locomotion and actual world speed (studs/sec).
function Pursuit:Step(targetRoot: BasePart, attackRadius: number, maximumSpeed: number): (boolean, number)
    if maximumSpeed <= 0 or not self.root.Parent or not self.humanoid.Parent then
        self:Stop()
        return false, 0
    end
    local offset = targetRoot.Position - self.root.Position
    local flat = Vector3.new(offset.X, 0, offset.Z)
    local distance = flat.Magnitude
    if distance <= 0.001 then
        self:Stop()
        return false, 0
    end
    local direction = flat.Unit
    local velocity = targetRoot.AssemblyLinearVelocity
    local retreat = math.max(0, Vector3.new(velocity.X, 0, velocity.Z):Dot(direction))
    local preferred = math.max(0, attackRadius - STOP_MARGIN)
    local errorDistance = math.max(0, distance - preferred)
    local desired = math.min(maximumSpeed, retreat + errorDistance * FOLLOW_GAIN)
    if distance > attackRadius then
        desired = math.max(desired, math.min(maximumSpeed, retreat + MIN_CATCHUP))
    end
    if desired <= IDLE_EPSILON then
        self:Stop()
        return false, 0
    end
    self.active = true
    self.humanoid.WalkSpeed = desired
    -- Rotation is owned by ActorFacingTracker during attacks.
    self.humanoid:Move(direction, false)
    return true, desired
end

return table.freeze(Pursuit)
