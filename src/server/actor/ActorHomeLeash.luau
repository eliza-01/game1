-- Shared NPC/monster pursuit termination rules. No scheduler or actor state.
-- Boundary is horizontal so authored vertical spawn offsets do not alter the territory.
local ActorHomeLeash = {}

function ActorHomeLeash.Outside(home: Vector3, position: Vector3, radius: number): boolean
    local dx, dz = position.X - home.X, position.Z - home.Z
    return dx * dx + dz * dz > radius * radius
end

function ActorHomeLeash.NoDamageTimeout(lastDamageAt: number, now: number, timeout: number): boolean
    return lastDamageAt > 0 and now - lastDamageAt >= timeout
end

return table.freeze(ActorHomeLeash)
