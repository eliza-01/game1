-- Navigation bodies are the only physical actor colliders. Visual meshes and
-- combat RootColliders stay non-colliding, and world collision remains enabled.
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
return table.freeze(ActorCollisionPolicy)
