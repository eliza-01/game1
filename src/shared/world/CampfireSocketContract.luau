--!strict
-- The placed Location campfire has two actual FBX sockets. Only fire_socket
-- owns interaction and AIM ranges; cooking_pot_01_socket is a mount marker.
-- Debug attributes are player-local and never mutate authored Bone geometry.
local Config = require(script.Parent:WaitForChild("FireplaceMechanicsConfig"))
local Contract = {}
local Options = require(script.Parent.Parent:WaitForChild("GameOptionsRegistry"))
local tuned = if Options.socketRanges and Options.socketRanges.campfire
    then Options.socketRanges.campfire.fire_socket else nil

local fire = table.freeze({
    name = "fire_socket", role = "campfire", action = "Разжечь огонь",
    radius = if tuned then tuned.useRadius else Config.CampfireInteractionRadius,
    hoverRadius = if tuned then tuned.aimRadius else Config.CampfireAimRadius, interact = true,
})
local pot = table.freeze({
    name = "cooking_pot_01_socket", role = "pot_mount", action = "HEAD · котёл",
    radius = 0, interact = false,
})
Contract.Fire = fire
Contract.Pot = pot
Contract.Definitions = table.freeze({fire, pot})

function Contract.Get(name: string): any?
    if name == fire.name then return fire end
    if name == pot.name then return pot end
    return nil
end

function Contract.RadiusAttribute(name: string): string
    return "Game1CampfireSocketRadius_" .. name
end

function Contract.HoverRadiusAttribute(name: string): string
    return "Game1CampfireSocketHoverRadius_" .. name
end

return table.freeze(Contract)
