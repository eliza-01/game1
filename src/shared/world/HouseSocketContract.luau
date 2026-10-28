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
    {name = "door_01_padlock_01_socket", role = "padlock", action = "Снять замок", radius = 6, interact = true, placeholder = "padlock"},
    {name = "chest_01_socket", role = "chest", action = "Открыть сундук", radius = 8, hoverRadius = 4, interact = true, placeholder = "chest"},
    {name = "elevator_01_socket", role = "elevator", hoverRadius = 5, action = "Подняться на 2 этаж", radius = 10, interact = true},
    {name = "elevator_02_socket", role = "elevator", hoverRadius = 5, action = "Спуститься на 1 этаж", radius = 10, interact = true, optional = true},
    {name = "elevator_03_socket", role = "elevator", hoverRadius = 5, action = "Спуститься на 2 этаж", radius = 10, interact = true, optional = true},
    {name = "chimney_01_socket", role = "chimney", action = "Дымоход", radius = 8, interact = false},
    {name = "house_floor_03_spawn_01_socket", role = "spawn", action = "Этаж 3", radius = 8, interact = false, optional = true},
    {name = "land_spawn_01_socket", role = "spawn", action = "Участок", radius = 8, interact = false},
    {name = "house_floor_01_spawn_01_socket", role = "spawn", action = "Этаж 1", radius = 8, interact = false},
    {name = "house_floor_02_spawn_01_socket", role = "spawn", action = "Этаж 2", radius = 8, interact = false},
}
local byName: {[string]: SocketDefinition} = {}
for _, definition in definitions do
    byName[definition.name] = table.freeze(definition)
end

Contract.Definitions = table.freeze(definitions)
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
