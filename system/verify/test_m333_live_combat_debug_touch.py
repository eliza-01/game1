"""Regression contracts for M333 on actual M332-based diagnostic state."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def source(name): return (ROOT/name).read_text(encoding="utf-8")

class PublishedRuntimeM333(unittest.TestCase):
    def test_mesh_unreadable_falls_back_in_same_query_pipeline(self):
        service=source("src/server/combat/EntityHitboxService.luau")
        builder=source("src/server/combat/HitboxDefinitionBuilder.luau")
        self.assertIn('if #records == 0 and not geometryUnavailable then',service)
        self.assertIn('HitboxDefinitionBuilder.Fallback(binding)',service)
        self.assertIn('binding.mode = if geometryUnavailable then "root_bounds_fallback"',service)
        self.assertIn('binding.root',builder)
        self.assertIn('kind = "root"',builder)
        self.assertIn('kind = "head"',builder)
        self.assertIn('HitboxSpatialQueries.BoxContact(binding',service)
        self.assertIn('HitboxSpatialQueries.AimContact(binding',service)
        self.assertNotIn('could not build hitboxes because %s is unreadable',service)

    def test_published_ui_requires_server_creator_authorization(self):
        policy=source('src/shared/dev/PublishedDebugAccess.luau')
        authorizer=source('src/server/dev/PublishedDebugAccessService.luau')
        self.assertIn('player:GetAttribute(AUTH_ATTRIBUTE) == true', policy)
        self.assertIn('Options.ShowPublishedDebugControls(device)', policy)
        self.assertIn('player.UserId == game.CreatorId',authorizer)
        self.assertIn('rank >= 200',authorizer)
        self.assertIn('PlayerAdded:Connect(authorize)',authorizer)
        for path in ['src/client/dev/CameraDebugController.luau','src/client/dev/HealthUiDebugController.luau',
                     'src/client/dev/TestLoadoutController.luau','src/client/dev/MovementDebugController.luau',
                     'src/client/dev/MonsterDebugController.luau','src/client/dev/CustomScalingDebugController.luau',
                     'src/client/dev/HouseSocketDebugController.luau','src/client/weapon/WeaponSelectionController.luau']:
            self.assertIn('PublishedDebugAccess.ClientAllowed()',source(path))
        for path in ['src/server/dev/TestLoadoutService.luau','src/server/dev/MovementDebugService.luau',
                     'src/server/dev/MonsterDebugService.luau','src/server/dev/CustomScalingDebugService.luau',
                     'src/server/dev/HouseSocketDebugService.luau','src/server/weapon/WeaponSelectionService.luau']:
            self.assertIn('ServerAllowed(',source(path))

    def test_right_two_thirds_and_pinch_lock(self):
        touch=source('src/client/character/MobileInputController.luau')
        camera=source('src/client/character/CameraController.luau')
        self.assertIn('position.X >= camera.ViewportSize.X / 3',touch)
        self.assertIn('if #lookFingers == 1 and not pinchLocked then',touch)
        self.assertIn('if #lookFingers == 0 then',touch)
        self.assertIn('pinchLocked = false',touch)
        self.assertIn('GameOptions.MobileCameraSpeed()',camera)
        self.assertIn('CameraTouchSensitivity * GameOptions.MobileCameraSpeed()',camera)

    def test_camera_options_validated_and_manifest_preserved(self):
        sys.path.insert(0,str(ROOT/'system/control-center'))
        from services.camera_settings import normalize_camera, DEFAULT_CAMERA
        self.assertAlmostEqual(normalize_camera({})['mobileLookSpeed'],1.5)
        with self.assertRaises(ValueError):normalize_camera({'mobileLookSpeed':5})
        with self.assertRaises(ValueError):normalize_camera({'mobileLookSpeed':-1})
        manifest=json.loads((ROOT/'assets/manifests/options.json').read_text(encoding='utf-8'))
        self.assertIn('mobileLookSpeed',manifest['camera'])
        self.assertIn('mobileLookSpeed',source('src/shared/GameOptionsRegistry.luau'))
        self.assertIn('mobileLookSpeed',source('system/control-center/static/options.js'))
        self.assertIn('option-camera-mobileLookSpeed',source('system/control-center/static/index.html'))

if __name__=='__main__':unittest.main()
