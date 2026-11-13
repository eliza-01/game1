-- Navigation bodies are the only physical actor colliders. Visual meshes and
-- combat RootColliders stay non-colliding, and world collision remains enabled.
-- On death, the same policy makes the entire retained visual rig a phantom.
local PhysicsService = game:GetService("PhysicsService")
local ActorCollisionPolicy = {}
local GROUP = "Game1ActorBodies"
local initialized = false
function ActorCollisionPolicy.Assign(root: BasePart)
    if not initialized then
        initialized = true
        if not PhysicsService:IsCollisionGroupRegistered(GROUP) then
            PhysicsService:RegisterCollisionGroup(GROUP)
        end
        PhysicsService:CollisionGroupSetCollidable(GROUP, GROUP, true)
        PhysicsService:CollisionGroupSetCollidable(GROUP, "Default", true)
    end
    root.CollisionGroup = GROUP
    root.CanCollide = true
end

-- Preserve the Model, Bones and AnimationTracks for Death / DeathIdle; remove
-- *every* physical/query/touch surface, including navigation and debug proxies.
-- This is idempotent and deliberately never restores collision on a corpse.
function ActorCollisionPolicy.MakePhantom(actor: Model)
    for _, descendant in ipairs(actor:GetDescendants()) do
        if descendant:IsA("BasePart") then
            descendant.CanCollide = false
            descendant.CanTouch = false
            descendant.CanQuery = false
        end
    end
end

return table.freeze(ActorCollisionPolicy)
