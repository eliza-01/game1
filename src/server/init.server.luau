local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local ProjectInfo = require(Shared:WaitForChild("ProjectInfo"))
local RuntimeVersion = require(Shared:WaitForChild("RuntimeVersion"))

local CharacterRoot = script:WaitForChild("character")
local CombatRoot = script:WaitForChild("combat")
local DevRoot = script:WaitForChild("dev")
local MonsterRoot = script:WaitForChild("monster")

local CharacterService = require(CharacterRoot:WaitForChild("CharacterService"))
local EntityHitboxService = require(CombatRoot:WaitForChild("EntityHitboxService"))
local AttackService = require(CombatRoot:WaitForChild("AttackService"))
local HitEffectService = require(CombatRoot:WaitForChild("HitEffectService"))
local TrainingDummyService = require(DevRoot:WaitForChild("TrainingDummyService"))
local TestLoadoutService = require(DevRoot:WaitForChild("TestLoadoutService"))
local MonsterSpawnerService = require(MonsterRoot:WaitForChild("MonsterSpawnerService"))

print(("[game1][server] %s v%s · runtime %s")
    :format(ProjectInfo.Name, ProjectInfo.Version, RuntimeVersion.Version))

EntityHitboxService.Start()
HitEffectService.Start()
AttackService.Start()
CharacterService.Start()
MonsterSpawnerService.Start()
TestLoadoutService.Start()
TrainingDummyService.Start()
