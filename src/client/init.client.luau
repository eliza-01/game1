local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
local ProjectInfo = require(Shared:WaitForChild("ProjectInfo"))
local RuntimeVersion = require(Shared:WaitForChild("RuntimeVersion"))

local CharacterRoot = script:WaitForChild("character")
local CombatRoot = script:WaitForChild("combat")
local MovementController = require(CharacterRoot:WaitForChild("MovementController"))
local CameraController = require(CharacterRoot:WaitForChild("CameraController"))
local PlayerStatusController = require(CharacterRoot:WaitForChild("PlayerStatusController"))
local AnimationRoot = CharacterRoot:WaitForChild("animation")
local CharacterAnimationController = require(AnimationRoot:WaitForChild("CharacterAnimationController"))
local AttackController = require(CombatRoot:WaitForChild("AttackController"))

print(("[game1][client] %s v%s · runtime %s")
    :format(ProjectInfo.Name, ProjectInfo.Version, RuntimeVersion.Version))

MovementController.Start()
CharacterAnimationController.Start()
CameraController.Start()
AttackController.Start(MovementController, CharacterAnimationController)
PlayerStatusController.Start()
