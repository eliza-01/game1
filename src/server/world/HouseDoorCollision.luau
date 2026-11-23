--!strict
-- Temporarily suppress door-only collisions during the opening tween.
-- Restore each BasePart's authored CanCollide instead of forcing every
-- visual, rig carrier or non-collider to become a physical obstacle.
local Collision = {}

export type Snapshot = {[BasePart]: boolean}

function Collision.Suspend(door: Model): Snapshot
    local snapshot: Snapshot = {}
    for _, descendant in door:GetDescendants() do
        if descendant:IsA("BasePart") then
            snapshot[descendant] = descendant.CanCollide
            descendant.CanCollide = false
        end
    end
    return snapshot
end

function Collision.Restore(snapshot: Snapshot)
    for part, wasCollidable in snapshot do
        if part.Parent then
            part.CanCollide = wasCollidable
        end
    end
end

return table.freeze(Collision)
