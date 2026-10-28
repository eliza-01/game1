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

-- Floor 1/2 transfers arrive at their authored spawn; elevator bones only
-- determine the origin and the offered controls. Floor 3 keeps its optional
-- lift destination until an authored floor spawn is explicitly required.
function Policy.DestinationSocket(_sourceFloor: number, destination: number): string
    if destination == 1 then return "house_floor_01_spawn_01_socket" end
    if destination == 2 then return "house_floor_02_spawn_01_socket" end
    return Policy.SocketName(destination)
end

function Policy.Resolve(floor: number, key: string, present: {[number]: boolean}): Option?
    for _, option in Policy.Options(floor, present) do
        if option.key == key then return option end
    end
    return nil
end

return table.freeze(Policy)
