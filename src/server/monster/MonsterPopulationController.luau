-- M93: authored spawn records, live slots and delayed respawns.
-- MonsterSpawnerService injects the creation callback; no require cycle.
local SpawnRegistry = require(script.Parent:WaitForChild("MonsterSpawnRegistry"))

local MonsterPopulationController = {}

local function finite(value: any, fallback: number): number
    local number = tonumber(value)
    if number == nil or number ~= number or number == math.huge or number == -math.huge then
        return fallback
    end
    return number
end

local function recordAppliesHere(record: any): boolean
    if record.enabled == false then
        return false
    end
    local placeId = math.floor(finite(record.placeId, 0))
    return placeId == 0 or game.PlaceId == 0 or placeId == game.PlaceId
end

function MonsterPopulationController.new(spawnOne: (any) -> Model?): any
    local states = {}
    local controller = {}

    local function liveCount(state: any): number
        local alive = 0
        for model in pairs(state.instances) do
            -- Dying/DeathIdle continues to occupy a slot until corpse release.
            if model.Parent then
                alive += 1
            end
        end
        return alive
    end

    local function spawnReserved(state: any): Model?
        -- spawnOne can yield while assets/tracks load. Reserve the capacity first:
        -- concurrent timer callbacks must never claim the same vacant slot.
        state.creating += 1
        local ok, result = pcall(spawnOne, state)
        state.creating -= 1
        if not ok then
            warn("[game1][monster-spawn] could not create monster: " .. tostring(result))
            return nil
        end
        return result
    end

    local function fill(state: any)
        if not state.enabled then
            return
        end
        local target = math.max(1, math.floor(finite(state.record.maxAlive, 1)))
        while liveCount(state) + state.creating < target do
            if not spawnReserved(state) then
                break
            end
        end
    end

    function controller:States(): any
        return states
    end

    function controller:RegisterInstance(state: any, model: Model, entry: any)
        state.instances[model] = entry
    end

    function controller:UnregisterInstance(state: any, model: Model)
        state.instances[model] = nil
    end

    function controller:ScheduleRespawn(state: any, diedAt: number?)
        if state.enabled then
            local delaySeconds = math.max(0, finite(state.record.respawnSeconds, 10))
            -- The timer belongs to this death, not the spawn record. Corpse
            -- retention still occupies maxAlive until it has been released.
            local elapsed = if diedAt then math.max(0, os.clock() - diedAt) else 0
            local remaining = math.max(0, delaySeconds - elapsed)
            -- One released corpse owns exactly one timer and one replacement.
            -- Calling fill() here would refill *every* vacant maxAlive slot when
            -- the earliest timer expires, collapsing staggered deaths into one wave.
            task.delay(remaining, function()
                if not state.enabled then
                    return
                end
                local target = math.max(1, math.floor(finite(state.record.maxAlive, 1)))
                if liveCount(state) + state.creating < target then
                    spawnReserved(state)
                end
            end)
        end
    end

    function controller:Start(): number
        local count = 0
        for _, record in ipairs(SpawnRegistry.records or {}) do
            if recordAppliesHere(record) then
                local state = {
                    record = record,
                    enabled = true,
                    instances = {},
                    creating = 0,
                }
                state.fill = function()
                    fill(state)
                end
                states[tostring(record.spawnId or count + 1)] = state
                fill(state)
                count += 1
            end
        end
        return count
    end

    return table.freeze(controller)
end

return table.freeze(MonsterPopulationController)
