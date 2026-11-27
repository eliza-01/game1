-- Navigation bodies are the only physical actor colliders. Visual meshes and
-- combat RootColliders stay non-colliding, and world collision remains enabled.
-- On death, the same policy makes the entire retained visual rig a phantom.
local PhysicsService = game:GetService("PhysicsService")
local ActorCollisionPolicy = {}
local CHARACTER_GROUP = "Game1ActorBodies"
local NON_PLAYER_GROUP = "Game1NonPlayerBodies"
local initialized = false
function ActorCollisionPolicy.Assign(root: BasePart, kind: "Character" | "Monster" | "NPC")
    if not initialized then
        for _, group in ipairs({CHARACTER_GROUP, NON_PLAYER_GROUP}) do
            if not PhysicsService:IsCollisionGroupRegistered(group) then
                PhysicsService:RegisterCollisionGroup(group)
            end
            PhysicsService:CollisionGroupSetCollidable(group, "Default", true)
        end
        PhysicsService:CollisionGroupSetCollidable(CHARACTER_GROUP, CHARACTER_GROUP, true)
        PhysicsService:CollisionGroupSetCollidable(CHARACTER_GROUP, NON_PLAYER_GROUP, true)
        PhysicsService:CollisionGroupSetCollidable(NON_PLAYER_GROUP, NON_PLAYER_GROUP, false)
        initialized = true
    end
    -- AI-controlled actors are mutually non-solid; players retain normal contact.
    root.CollisionGroup = CHARACTER_GROUP
    if kind == "Monster" or kind == "NPC" then
        root.CollisionGroup = NON_PLAYER_GROUP
    end
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
