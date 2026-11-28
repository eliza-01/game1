local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Game1Shared")
-- Language selection is mounted before the gameplay surfaces. It is optional
-- to gameplay boot and its preference load does not block movement or combat.
local LanguageState = require(script:WaitForChild("localization"):WaitForChild("LanguageState"))
LanguageState.Start()
require(script:WaitForChild("localization"):WaitForChild("LanguageMenuController")).Start()
local ProjectInfo = require(Shared:WaitForChild("ProjectInfo"))
local RuntimeVersion = require(Shared:WaitForChild("RuntimeVersion"))

local CharacterRoot = script:WaitForChild("character")
local CombatRoot = script:WaitForChild("combat")
local DevRoot = script:WaitForChild("dev")
local MovementController = require(CharacterRoot:WaitForChild("MovementController"))
local CameraController = require(CharacterRoot:WaitForChild("CameraController"))
local MobileInputController = require(CharacterRoot:WaitForChild("MobileInputController"))
local MnpcOverheadController = require(CombatRoot:WaitForChild("MnpcOverheadController"))
local PlayerHealthHudController = require(CombatRoot:WaitForChild("PlayerHealthHudController"))
local DeathRespawnController = require(CharacterRoot:WaitForChild("DeathRespawnController"))
local AnimationRoot = CharacterRoot:WaitForChild("animation")
local CharacterAnimationController = require(AnimationRoot:WaitForChild("CharacterAnimationController"))
local AttackController = require(CombatRoot:WaitForChild("AttackController"))
local HitEffectController = require(CombatRoot:WaitForChild("HitEffectController"))
local CombatFeedbackController = require(CombatRoot:WaitForChild("CombatFeedbackController"))
local WeaponBounceController = require(CombatRoot:WaitForChild("WeaponBounceController"))
local AimPoseController = require(CombatRoot:WaitForChild("AimPoseController"))
local WeaponRoot = script:WaitForChild("weapon")
local WeaponSelectionController = require(WeaponRoot:WaitForChild("WeaponSelectionController"))
local NpcWeaponVisibilityController = require(WeaponRoot:WaitForChild("NpcWeaponVisibilityController"))
local HouseSocketPromptController = require(script:WaitForChild("world"):WaitForChild("HouseSocketPromptController"))
local MonsterRoot = script:WaitForChild("monster")
local MonsterAttackLocomotionController = require(MonsterRoot:WaitForChild("MonsterAttackLocomotionController"))
local NpcAttackLocomotionController = require(script:WaitForChild("actor"):WaitForChild("NpcAttackLocomotionController"))

print(("[game1][client] %s v%s · runtime %s")
    :format(ProjectInfo.Name, ProjectInfo.Version, RuntimeVersion.Version))

MovementController.Start()
CharacterAnimationController.Start()
require(AnimationRoot:WaitForChild("RemotePlayerAttackController")).Start()
require(AnimationRoot:WaitForChild("WorldAnimationPreloader")).Start()
require(AnimationRoot:WaitForChild("FaceAnimationController")).Start()
WeaponSelectionController.Start()
NpcWeaponVisibilityController.Start()
AimPoseController.Start()
CameraController.Start()
-- Character Creation camera shares CameraController, never replaces the game camera.
task.spawn(function()
    require(CharacterRoot:WaitForChild("CharacterCreationController")).Start()
end)
HitEffectController.Start()
require(MonsterRoot:WaitForChild("MonsterHomeRecallVisuals")).Start()
CombatFeedbackController.Start()
MonsterAttackLocomotionController.Start()
NpcAttackLocomotionController.Start()
AttackController.Start(MovementController, CharacterAnimationController, AimPoseController)
MobileInputController.Start(MovementController, CameraController, AttackController)
WeaponBounceController.Start(CharacterAnimationController, AttackController)
require(CombatRoot:WaitForChild("BowShotVisualController")).Start()
MnpcOverheadController.Start()
PlayerHealthHudController.Start()
require(CombatRoot:WaitForChild("WalletHud")).Start()
DeathRespawnController.Start()
HouseSocketPromptController.Start()
-- Presentation is optional. A HUD error must not cancel startup of
-- subsequent world visuals or the entire Studio development toolbar.
local fireplaceOk, fireplaceError = pcall(function()
    require(script:WaitForChild("world"):WaitForChild("HouseFireplaceController", 5)).Start()
end)
if not fireplaceOk then
    warn("[game1][client] fireplace information UI failed; other modules remain available: " .. tostring(fireplaceError))
end
-- Windmill bone skinning is evaluated independently on every client.
local windmillOk, windmillError = pcall(function()
    require(script:WaitForChild("world"):WaitForChild("WindmillVisualController")).Start()
end)
if not windmillOk then warn("[game1][client] windmill visuals failed: " .. tostring(windmillError)) end
require(script:WaitForChild("world"):WaitForChild("LandscapeSwayController")).Start()
require(script:WaitForChild("world"):WaitForChild("LocationWorldStreamer")).Start()
-- Lightweight foliage contact visual; independent of World LOD transitions.
local floraOk, floraError = pcall(function()
    require(script:WaitForChild("world"):WaitForChild("FloraLeafBurstController")).Start()
end)
if not floraOk then warn("[game1][client] flora effect startup failed: " .. tostring(floraError)) end
require(script:WaitForChild("world"):WaitForChild("BoneOrbController")).Start()
require(script:WaitForChild("world"):WaitForChild("BoneFireController")).Start()
-- Debug modules are optional: Studio or global published debug enabled.
-- GP remains Studio-only.
local DebugAccess = require(Shared:WaitForChild("dev"):WaitForChild("PublishedDebugAccess"))
if DebugAccess.ClientAllowed() then
    local profile = require(DevRoot:WaitForChild("DebugDockProfile")).Resolve(
        game:GetService("UserInputService").TouchEnabled, DebugAccess.GameplayTestEnabled())
    if DebugAccess.GameplayTestEnabled() then
        task.spawn(function()
            local ok, err = pcall(function()
                local module = assert(DevRoot:WaitForChild("GameplayTestController", 20), "GameplayTestController missing")
                require(module).Start()
            end)
            if not ok then warn("[game1][gameplay-test] client startup failed: " .. tostring(err)) end
        end)
        if profile.slots.AG ~= nil then
            task.spawn(function() require(DevRoot:WaitForChild("GameplayAggroController")).Start() end)
        end
        task.spawn(function() require(DevRoot:WaitForChild("GameplayBufferController")).Start() end)
    end
    if profile.slots.HS ~= nil then
        local HouseSocketDebugController = require(DevRoot:WaitForChild("HouseSocketDebugController"))
        HouseSocketDebugController.Start()
    end
    require(DevRoot:WaitForChild("CameraDebugController")).Start()
    require(DevRoot:WaitForChild("HealthUiDebugController")).Start()
    require(DevRoot:WaitForChild("UiPresentationDebugController")).Start()
    if profile.slots.TL ~= nil then
        local TestLoadoutController = require(DevRoot:WaitForChild("TestLoadoutController"))
        TestLoadoutController.Start()
    end
    if profile.slots.CS ~= nil then
        require(DevRoot:WaitForChild("CustomScalingDebugController")).Start()
    end
    local lodDebugOk, lodDebugError = pcall(function()
        require(DevRoot:WaitForChild("LodDebugController")).Start()
    end)
    if not lodDebugOk then warn("[game1][LOD] diagnostics UI failed: " .. tostring(lodDebugError)) end
end
