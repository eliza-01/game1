--!strict
-- Pure floor/key routing policy. A floor exists only when its actual
-- elevator socket is registered; never synthesize a third floor.
local Policy = {}

export type Option = {key: string, destination: number, action: string}

function Policy.SocketName(floor: number): string
    return ("elevator_%02d_socket"):format(floor)
end

function Policy.Floor(name: string): number?
    local digits = string.match(name, "^elevator_(%d%d)_socket$")
    return if digits then tonumber(digits) else nil
end

function Policy.TopFloor(present: {[number]: boolean}): number
    local top = 0
    for floor = 1, 3 do
        if not present[floor] then break end
        top = floor
    end
    return top
end

function Policy.Options(floor: number, present: {[number]: boolean}): {Option}
    local top = Policy.TopFloor(present)
    local options: {Option} = {}
    if floor < 1 or floor > top then return options end
    if top == 2 and floor == 2 then
        table.insert(options, {key = "E", destination = 1, action = "Спуститься на 1 этаж"})
    else
        if floor < top then
            table.insert(options, {key = "E", destination = floor + 1,
                action = ("Подняться на %d этаж"):format(floor + 1)})
        end
        if top >= 3 and floor > 1 then
            table.insert(options, {key = "F", destination = floor - 1,
                action = ("Спуститься на %d этаж"):format(floor - 1)})
        end
    end
    return options
end

-- Every destination uses its actual authored floor-spawn socket.
-- Do not extrapolate positions from an elevator bone or house geometry.
function Policy.DestinationSocket(_sourceFloor: number, destination: number): string
    return ("house_floor_%02d_spawn_socket"):format(destination)
end

function Policy.Resolve(floor: number, key: string, present: {[number]: boolean}): Option?
    for _, option in Policy.Options(floor, present) do
        if option.key == key then return option end
    end
    return nil
end

-- Use the authored spawn height, not the height of an aimed control. The
-- clearance is shared with the actual teleport. A midpoint is ambiguous.
Policy.SpawnClearance = 3

function Policy.CurrentFloor(rootY: number, heights: {[number]: number}, standingOffset: number): number?
    local best: number? = nil
    local distance = math.huge
    local second = math.huge
    for floor, height in heights do
        -- Accept the root while standing or while settling after the +3 teleport.
        local lower = height + math.min(standingOffset, Policy.SpawnClearance)
        local upper = height + math.max(standingOffset, Policy.SpawnClearance)
        local delta = math.max(lower - rootY, rootY - upper, 0)
        if delta < distance then
            second = distance
            best, distance = floor, delta
        elseif delta < second then
            second = delta
        end
    end
    if second - distance <= 0.15 then return nil end
    return best
end

return table.freeze(Policy)
