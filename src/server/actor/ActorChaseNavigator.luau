-- Reusable server-owned MoveTo/path fallback component for world actors.
-- No targeting, attacks or animation responsibilities; owner controls the lifecycle.
local Budget = require(script.Parent:WaitForChild("NavigationScheduler"))

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
        blocked = false, pathRequest = nil, mode = "",
        blockedConnection = nil,
    }, Navigator)
end

function Navigator:_clearPath()
    if self.blockedConnection then self.blockedConnection:Disconnect(); self.blockedConnection = nil end
    Budget.Cancel(self.pathRequest)
    self.pathRequest = nil
    if self.path then self.path:Destroy() end
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
    self:_clearPath()
    self.mode = "Path"
    self.destination = position
    self.pathRequest = Budget.Request(self, self.root, position)
    self.nextRefresh = os.clock() + PATH_REISSUE
    self.humanoid:MoveTo(self.root.Position)
    self.progressPosition = self.root.Position
    self.progressAt = os.clock()
    if not self.pathRequest then
        self.blocked = true
        self.nextRefresh = 0
    end
end

function Navigator:_consumePath(position: Vector3, speed: number)
    local ticket = self.pathRequest
    if not ticket then return false end
    Budget.UpdateQueued(ticket, position)
    self.destination = ticket.destination
    local ready, result = Budget.Take(ticket)
    if not ready then
        self.progressPosition = self.root.Position
        self.progressAt = os.clock()
        return true
    end
    self.pathRequest = nil
    if Budget.IsStale(result, self.root, self.destination, position, DESTINATION_DELTA) then
        Budget.Dispose(result)
        self:_requestPath(position, speed)
        return true
    end
    self.progressPosition = self.root.Position
    self.progressAt = os.clock()
    self.nextRefresh = self.progressAt + PATH_REISSUE
    local path = result and result.path
    self.blocked = false
    if not path then
        self:_direct(position, speed)
        return true
    end
    self.mode = "Path"
    self.path = path
    self.waypoints = path:GetWaypoints()
    self.index = math.min(2, #self.waypoints)
    self.blockedConnection = path.Blocked:Connect(function(blockedIndex)
        if blockedIndex >= self.index then self.blocked = true end
    end)
    local waypoint = self.waypoints[self.index]
    if waypoint then self.humanoid:MoveTo(waypoint.Position) end
    return true
end

function Navigator:Chase(position: Vector3, speed: number)
    if not self.active or not self.root.Parent or not self.humanoid.Parent then return end
    self.humanoid.WalkSpeed = speed
    if self:_consumePath(position, speed) then return end
    local now = os.clock()
    -- The first movement command owns a fresh progress window. Time spent
    -- idle/attacking must not count as time stuck in navigation.
    if self.mode == "" then
        self.progressAt = now
        self.progressPosition = self.root.Position
    end
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
        if not self.pathRequest and (self.mode ~= "Path" or now >= self.nextRefresh or moved) then
            self:_requestPath(position, speed)
        end
    elseif self.mode == "Path" and moved and not self.pathRequest and now >= self.nextRefresh then
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
