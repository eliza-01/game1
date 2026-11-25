"""Retired dummy source and old standalone probe must not ship."""
from pathlib import Path
import unittest
import test_m501_runtime_stabilization as runtime
from test_m501_runtime_stabilization import item, expected_scripts, verify_scripts

ROOT = Path(__file__).resolve().parents[2]


class RetiredDebugCleanup(unittest.TestCase):
    def test_no_dummy_service_or_startup_registration(self):
        self.assertFalse((ROOT / 'src/server/dev/TrainingDummyService.luau').exists())
        catalog = (ROOT / 'src/server/bootstrap/ServiceCatalog.luau').read_text()
        self.assertNotIn('TrainingDummyService', catalog)
        self.assertIn('EntityHitboxService', catalog)
        self.assertIn('MonsterSpawnerService', catalog)
        scripts, _ = expected_scripts(ROOT)
        self.assertFalse(any('TrainingDummyService' in key or 'Game1LodProbeClient' in key for key in scripts))

    def test_cleanup_is_edit_only_and_targets_exact_names(self):
        source = (ROOT / 'system/verify/studio_retired_debug_cleanup_m506.luau').read_text()
        self.assertIn('assert(not game:GetService("RunService"):IsRunning()', source)
        self.assertIn('child.Name == "Game1LodProbeClient" and child:IsA("LuaSourceContainer")', source)
        self.assertIn('child.Name == "game1TrainingDummy" and child:IsA("Model")', source)
        self.assertNotIn('GetDescendants', source)
        self.assertIn('history:SetWaypoint', source)


class RetiredPlaceInstances(unittest.TestCase):
    setUp = runtime.RuntimeScripts.setUp

    def test_standalone_probe_outside_managed_scope_is_rejected(self):
        scripts = self.tree.getroot().find('./Item[@class="StarterPlayer"]/Item[@class="StarterPlayerScripts"]')
        probe = item(scripts, 'Game1LodProbeClient', 'LocalScript', 'print("old probe")')
        with self.assertRaisesRegex(ValueError, 'retired Place instance StarterPlayer.StarterPlayerScripts.Game1LodProbeClient'):
            verify_scripts(self.root, self.tree)
        scripts.remove(probe)
        item(scripts, 'OtherAuthoringScript', 'LocalScript', 'print("other")')
        self.assertEqual(verify_scripts(self.root, self.tree)['scriptCount'], 4)

    def test_retired_dummy_model_is_rejected_without_rejecting_other_models(self):
        workspace = self.tree.getroot().find('./Item[@class="Workspace"]')
        dummy = item(workspace, 'game1TrainingDummy', 'Model')
        with self.assertRaisesRegex(ValueError, 'retired Place instance Workspace.game1TrainingDummy'):
            verify_scripts(self.root, self.tree)
        workspace.remove(dummy)
        item(workspace, 'OtherModel', 'Model')
        self.assertEqual(verify_scripts(self.root, self.tree)['scriptCount'], 4)
