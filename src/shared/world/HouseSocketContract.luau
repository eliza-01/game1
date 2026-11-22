--!strict
-- Shared definitions only. Authoring, presentation, and runtime handlers must
-- not infer mechanics from string fragments outside this contract.
local Contract = {}

export type SocketDefinition = {
    name: string,
    role: string,
    action: string,
    radius: number,
    hoverRadius: number?, -- enables center-reticle ray AIM sphere, separate from USE reach
    interact: boolean,
    placeholder: string?,
    optional: boolean?,
}

local definitions: {SocketDefinition} = {
    {name = "door_01_handle_outside_socket", role = "door", action = "Открыть дверь", radius = 8, interact = true},
    {name = "door_01_handle_inside_socket", role = "door", action = "Открыть дверь", radius = 8, interact = true},
    {name = "door_01_padlock_01_outside_socket", role = "padlock", action = "Снять замок", radius = 6, interact = true, placeholder = "padlock", optional = true},
    {name = "door_01_padlock_01_inside_socket", role = "padlock", action = "Снять замок", radius = 6, interact = true, optional = true},
    {name = "chest_01_socket", role = "chest", action = "Открыть сундук", radius = 8, hoverRadius = 4, interact = true, placeholder = "chest"},
    {name = "elevator_01_socket", role = "elevator", hoverRadius = 5, action = "Подняться на 2 этаж", radius = 10, interact = true},
    {name = "elevator_02_socket", role = "elevator", hoverRadius = 5, action = "Спуститься на 1 этаж", radius = 10, interact = true, optional = true},
    {name = "elevator_03_socket", role = "elevator", hoverRadius = 5, action = "Спуститься на 2 этаж", radius = 10, interact = true, optional = true},
    {name = "chimney_01_socket", role = "chimney", action = "Дымоход", radius = 8, interact = false},
    {name = "fireplace_01_socket", role = "fireplace", action = "Разжечь огонь", radius = 8, interact = true, optional = true},
    {name = "house_floor_03_spawn_socket", role = "spawn", action = "Этаж 3", radius = 8, interact = false, optional = true},
    {name = "house_floor_01_spawn_socket", role = "spawn", action = "Этаж 1", radius = 8, interact = false},
    {name = "house_floor_02_spawn_socket", role = "spawn", action = "Этаж 2", radius = 8, interact = false},
}
for i=1,15 do
    -- Match house_level5_01_remesh.blend: 01..09, then 010..015.
    local houseplantName = if i < 10
        then string.format("houseplant_%02d", i)
        else string.format("houseplant_%03d", i)
    table.insert(definitions, {name=houseplantName,role="houseplant",
        action="Растение",radius=8,interact=false,optional=true})
end
local byName: {[string]: SocketDefinition} = {}
for _, definition in definitions do
    byName[definition.name] = table.freeze(definition)
end

Contract.Definitions = table.freeze(definitions)
Contract.PadlockSockets = table.freeze({
    "door_01_padlock_01_outside_socket",
    "door_01_padlock_01_inside_socket",
})
function Contract.HasPadlock(sockets: {[string]: any}): boolean
    for _, name in Contract.PadlockSockets do
        if sockets[name] then return true end
    end
    return false
end
Contract.MaxDebugRadius = 30
Contract.MinDebugRadius = 2
Contract.MinHoverRadius = 1
Contract.MaxHoverRadius = 16

function Contract.Get(name: string): SocketDefinition?
    return byName[name]
end

function Contract.HoverRadiusAttribute(name: string): string
    return "Game1HouseSocketHoverRadius_" .. name
end

function Contract.RadiusAttribute(name: string): string
    -- Internal/debug only, never accept arbitrary player-defined names.
    return "Game1HouseSocketRadius_" .. name
end

return table.freeze(Contract)
