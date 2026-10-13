-- Reusable server-owned MoveTo/path fallback component for world actors.
-- No targeting, attacks or animation responsibilities; owner controls the lifecycle.
local PathfindingService = game:GetService("PathfindingService")

local Navigator = {}
Navigator.__index = Navigator

local DIRECT_REISSUE = 0.3
local PATH_REISSUE = 0.8
local STUCK_SECONDS = 0.9
local STUCK_DISTANCE = 0.35
local DESTINATION_DELTA = 3
local WAYPOINT_TOLERANCE = 1.25

local function flatDistance(a: Vector3, b: Vector3): number
    return (Vector3.new(a.X - b.X, 0, a.Z - b.Z)).Magnitude
end

function Navigator.new(root: BasePart, humanoid: Humanoid)
    return setmetatable({
        root = root, humanoid = humanoid, active = true,
        destination = nil, path = nil, waypoints = nil, index = 1,
        nextRefresh = 0, progressAt = os.clock(), progressPosition = root.Position,
        blocked = false, pathPending = false, serial = 0, mode = "",
        blockedConnection = nil,
    }, Navigator)
end

function Navigator:_clearPath()
    if self.blockedConnection then self.blockedConnection:Disconnect(); self.blockedConnection = nil end
    self.path = nil
    self.waypoints = nil
    self.index = 1
end

function Navigator:_direct(position: Vector3, speed: number)
    self:_clearPath()
    self.mode = "Direct"
    self.destination = position
    self.nextRefresh = os.clock() + DIRECT_REISSUE
    self.humanoid.WalkSpeed = speed
    self.humanoid.AutoRotate = true
    self.humanoid:MoveTo(position)
end

function Navigator:_requestPath(position: Vector3, speed: number)
    if self.pathPending then return end
    self.pathPending = true
    self.serial += 1
    local serial = self.serial
    self.nextRefresh = os.clock() + PATH_REISSUE
    -- ComputeAsync yields: never block the NPC AI scheduler.
    task.spawn(function()
        local path = PathfindingService:CreatePath({
            AgentRadius = 1, AgentHeight = 4, AgentCanJump = false, WaypointSpacing = 3,
        })
        local success = pcall(function() path:ComputeAsync(self.root.Position, position) end)
        if not self.active or self.serial ~= serial then return end
        self.pathPending = false
        if not success or path.Status ~= Enum.PathStatus.Success then
            self.blocked = false
            self:_direct(position, speed)
            return
        end
        self:_clearPath()
        self.mode = "Path"
        self.path = path
        self.destination = position
        self.waypoints = path:GetWaypoints()
        self.index = math.min(2, #self.waypoints)
        self.blocked = false
        self.blockedConnection = path.Blocked:Connect(function(blockedIndex)
            if blockedIndex >= self.index then self.blocked = true end
        end)
        local waypoint = self.waypoints[self.index]
        if waypoint then self.humanoid:MoveTo(waypoint.Position) end
    end)
end

function Navigator:Chase(position: Vector3, speed: number)
    if not self.active or not self.root.Parent or not self.humanoid.Parent then return end
    local now = os.clock()
    local progressed = flatDistance(self.root.Position, self.progressPosition) >= STUCK_DISTANCE
    if progressed then
        self.progressAt = now
        self.progressPosition = self.root.Position
    elseif self.mode ~= "" and now - self.progressAt >= STUCK_SECONDS then
        self.blocked = true
        self.progressAt = now
    end
    local moved = not self.destination or flatDistance(self.destination, position) >= DESTINATION_DELTA
    if self.blocked then
        if not self.pathPending and (self.mode ~= "Path" or now >= self.nextRefresh or moved) then
            self:_requestPath(position, speed)
        end
    elseif self.mode == "Path" and moved and not self.pathPending and now >= self.nextRefresh then
        self:_requestPath(position, speed)
    elseif self.mode == "" or (self.mode == "Direct" and (moved or now >= self.nextRefresh)) then
        self:_direct(position, speed)
    end
    self.humanoid.WalkSpeed = speed
    if self.mode == "Path" and self.waypoints then
        local waypoint = self.waypoints[self.index]
        if waypoint and flatDistance(self.root.Position, waypoint.Position) <= WAYPOINT_TOLERANCE then
            self.index += 1
            waypoint = self.waypoints[self.index]
            if waypoint then
                self.humanoid:MoveTo(waypoint.Position)
            else
                self.blocked = false
                self:_direct(position, speed)
            end
        end
    end
end

function Navigator:Stop()
    if not self.active then return end
    self.serial += 1 -- discard any in-flight path request
    self.pathPending = false
    self.blocked = false
    self.mode = ""
    self.destination = nil
    self:_clearPath()
    if self.humanoid.Parent and self.root.Parent then
        self.humanoid:Move(Vector3.zero, false)
        self.humanoid:MoveTo(self.root.Position)
        self.humanoid.WalkSpeed = 0
    end
end

function Navigator:Destroy()
    self:Stop()
    self.active = false
end

return table.freeze(Navigator)
