--!strict
-- Explicit startup dependencies; keep the existing execution order.
-- Each require occurs inside Start, so a failed NPC module cannot suppress
-- later independent debug remotes or monster lifecycle startup.
local ServiceCatalog = {}

function ServiceCatalog.Build(root: Instance)
    local character = root:WaitForChild("character")
    local combat = root:WaitForChild("combat")
    local dev = root:WaitForChild("dev")
    local monster = root:WaitForChild("monster")
    local npc = root:WaitForChild("npc")
    local world = root:WaitForChild("world")

    return {
        {name = "EnvironmentAssetService", critical = true, start = function()
            local EnvironmentAssetService = require(world:WaitForChild("EnvironmentAssetService"))
            EnvironmentAssetService.Start()
        end},
        {name = "HouseSocketService", critical = false, start = function()
            require(world:WaitForChild("HouseSocketService")).Start()
        end},
        {name = "EntityHitboxService", critical = true, start = function()
            local EntityHitboxService = require(combat:WaitForChild("EntityHitboxService"))
            EntityHitboxService.Start()
        end},
        {name = "WeaponBounceService", critical = false, start = function()
            local WeaponBounceService = require(combat:WaitForChild("WeaponBounceService"))
            WeaponBounceService.Start()
        end},
        {name = "HitEffectService", critical = false, start = function()
            require(combat:WaitForChild("HitEffectService")).Start()
        end},
        {name = "CombatFeedbackService", critical = false, start = function()
            require(combat:WaitForChild("CombatFeedbackService")).Start()
        end},
        {name = "AttackService", critical = true, dependsOn = {"EntityHitboxService"}, start = function()
            require(combat:WaitForChild("AttackService")).Start()
        end},
        {name = "CharacterService", critical = true, dependsOn = {"EntityHitboxService", "AttackService"}, start = function()
            require(character:WaitForChild("CharacterService")).Start()
        end},
        {name = "MonsterSpawnerService", critical = false, dependsOn = {"EntityHitboxService", "CharacterService"}, start = function()
            local MonsterSpawnerService = require(monster:WaitForChild("MonsterSpawnerService"))
            MonsterSpawnerService.Start()
        end},
        {name = "MonsterAIService", critical = false, dependsOn = {"MonsterSpawnerService"}, start = function()
            require(monster:WaitForChild("MonsterAIService")).Start()
        end},
        {name = "NpcSpawnerService", critical = false, dependsOn = {"EntityHitboxService", "CharacterService"}, start = function()
            require(npc:WaitForChild("NpcSpawnerService")).Start()
        end},
        {name = "MovementDebugService", critical = false, start = function()
            local MovementDebugService = require(dev:WaitForChild("MovementDebugService"))
            MovementDebugService.Start()
        end},
        {name = "CustomScalingDebugService", critical = false, start = function()
            require(dev:WaitForChild("CustomScalingDebugService")).Start()
        end},
        {name = "MonsterDebugService", critical = false, start = function()
            require(dev:WaitForChild("MonsterDebugService")).Start()
        end},
        {name = "TestLoadoutService", critical = false, dependsOn = {"CharacterService", "AttackService"}, start = function()
            local TestLoadoutService = require(dev:WaitForChild("TestLoadoutService"))
            TestLoadoutService.Start()
        end},
        {name = "HouseSocketDebugService", critical = false, dependsOn = {"HouseSocketService"}, start = function()
            require(dev:WaitForChild("HouseSocketDebugService")).Start()
        end},
        {name = "TrainingDummyService", critical = false, dependsOn = {"EntityHitboxService"}, start = function()
            require(dev:WaitForChild("TrainingDummyService")).Start()
        end},
    }
end

return ServiceCatalog
