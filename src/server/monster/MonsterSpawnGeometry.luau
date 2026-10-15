-- Spawn-circle sampling and terrain projection for monster navigation.
-- Random and folder provider are injected so the shared RNG stream and
-- Workspace.Monsters raycast exclusion retain their original behavior.
local Workspace = game:GetService("Workspace")
local MonsterSpawnGeometry = {}
local GROUND_RAY_START = 96
local GROUND_RAY_LENGTH = 384

local function finite(value: any, fallback: number): number
    local number = tonumber(value)
    if number == nil or number ~= number or number == math.huge or number == -math.huge then
        return fallback
    end
    return number
end

local function spawnCenter(record: any): Vector3
    local position = record.position or {}
    return Vector3.new(finite(position.x, 0), finite(position.y, 0), finite(position.z, 0))
end

local function surfacePoint(self: any, candidate: Vector3): Vector3
    local params = RaycastParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = { self.ensureMonstersFolder() }
    params.IgnoreWater = false
    params.RespectCanCollide = false
    local origin = candidate + Vector3.new(0, GROUND_RAY_START, 0)
    local hit = Workspace:Raycast(origin, Vector3.new(0, -GROUND_RAY_LENGTH, 0), params)
    return if hit then hit.Position else candidate
end

local function randomSpawnPoint(self: any, record: any): Vector3
    local center = spawnCenter(record)
    local radius = math.max(0, finite(record.spawnRadius, 0))
    local candidate = center
    if radius > 0 then
        local angle = self.random:NextNumber(0, math.pi * 2)
        local distance = math.sqrt(self.random:NextNumber(0, 1)) * radius
        candidate = center + Vector3.new(math.cos(angle) * distance, 0, math.sin(angle) * distance)
    end
    return surfacePoint(self, candidate)
end

local function horizontalDistance(left: Vector3, right: Vector3): number
    return Vector3.new(right.X - left.X, 0, right.Z - left.Z).Magnitude
end

local function chooseWanderTarget(self: any, record: any, current: Vector3): (Vector3?, number, boolean)
    local center = spawnCenter(record)
    local radius = math.max(0, finite(record.spawnRadius, 0))
    if radius <= 0 then
        return nil, 0, false
    end

    local toCenter = Vector3.new(center.X - current.X, 0, center.Z - current.Z)
    local distanceToCenter = toCenter.Magnitude
    local outsideSpawn = distanceToCenter > radius
    local maximumLength = radius * 2
    local direction: Vector3
    if outsideSpawn and distanceToCenter > 0.001 then
        -- Same contract as RobloxLineage: if a straight wander route ended outside
        -- the authored circle, the next route is forced inward and cannot pass the center.
        direction = toCenter.Unit
        maximumLength = math.min(maximumLength, distanceToCenter)
    else
        local angle = self.random:NextNumber(0, math.pi * 2)
        direction = Vector3.new(math.cos(angle), 0, math.sin(angle))
    end
    if maximumLength <= 0.001 then
        return nil, 0, outsideSpawn
    end

    local routeLength = self.random:NextNumber(0, maximumLength)
    local flatDestination = current + direction * routeLength
    local destination = surfacePoint(self, Vector3.new(flatDestination.X, current.Y, flatDestination.Z))
    return destination, routeLength, outsideSpawn
end


function MonsterSpawnGeometry.new(random: Random, ensureFolder: () -> Folder)
    assert(random ~= nil and ensureFolder ~= nil, "MonsterSpawnGeometry requires RNG and folder provider")
    local context = { random = random, ensureMonstersFolder = ensureFolder }
    return table.freeze({
        RandomSpawnPoint = function(_, record: any): Vector3
            return randomSpawnPoint(context, record)
        end,
        ChooseWanderTarget = function(_, record: any, current: Vector3): (Vector3?, number, boolean)
            return chooseWanderTarget(context, record, current)
        end,
    })
end
MonsterSpawnGeometry.HorizontalDistance = horizontalDistance
return table.freeze(MonsterSpawnGeometry)
