"""M168 validator regression tests; intentionally broken sources remain in memory."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/verify'))
from validators.studio_debug import check_studio_debug
from validators.death_runtime import check_death_runtime
from validators.attack_timelines import check_attack_timelines
from validators.authoring_tooling import check_authoring_tooling


def read(relative):
    return (ROOT / relative).read_text(encoding='utf-8')


def host_sources():
    return read('system/control-center/host_agent.py') + '\n' + '\n'.join(
        p.read_text(encoding='utf-8')
        for folder in ('api', 'services')
        for p in (ROOT / 'system/control-center' / folder).glob('*.py')
    )


def plugin_sources():
    return read('system/studio-plugin/Game1Bridge.server.luau') + '\n' + '\n'.join(
        read('system/studio-plugin/modules/' + name)
        for name in ('StudioModelLoadCommands.luau', 'StudioActorSpawnCommands.luau', 'StudioDebugPreferenceBridge.luau')
    )


def monster_sources():
    parts = ('MonsterSpawnerService', 'MonsterRigBuilder', 'MonsterSpawnGeometry',
             'MonsterAnimationTrackFactory', 'MonsterInitialAttributes', 'MonsterWanderController',
             'MonsterDeathLifecycle', 'MonsterIdlePresentation', 'MonsterPopulationController')
    data = [read(f'src/server/monster/{name}.luau') for name in parts]
    return SimpleNamespace(spawner_text=data[0], runtime_text='\n'.join(data))


class NewValidatorsM168Tests(unittest.TestCase):
    def intercept(self, path, change):
        target = ROOT / path
        original = Path.read_text

        def read_with_change(obj, *args, **kwargs):
            data = original(obj, *args, **kwargs)
            return change(data) if obj == target else data

        return patch.object(Path, 'read_text', read_with_change)

    def debug(self):
        issues = []
        boot = check_studio_debug(ROOT, issues.append,
                                 plugin_text=plugin_sources(),
                                 stats_service_text=read('src/server/character/CharacterStatsService.luau'),
                                 client_init_text=read('src/client/init.client.luau'))
        return issues, boot

    def death(self):
        issues = []
        service = check_death_runtime(ROOT, issues.append,
                                      animation_store_text=read('system/control-center/animation_store.py') + '\n' + '\n'.join(
                                          p.read_text(encoding='utf-8')
                                          for p in sorted((ROOT / 'system/control-center/animation_core').glob('*.py'))),
                                      monster_sources=monster_sources(),
                                      damage_resolver_text=read('src/server/combat/AttackDamageResolver.luau'))
        return issues, service

    def timeline(self):
        issues = []
        output = check_attack_timelines(ROOT, issues.append,
                                        attack_timeline_text=read('src/shared/combat/AttackTimelineConfig.luau'),
                                        attack_timeline_data_text=read('src/shared/combat/AttackTimelineData.luau'),
                                        studio_plugin_text=read('system/studio-plugin/Game1Bridge.server.luau') + '\n' + '\n'.join(
                                            p.read_text(encoding='utf-8')
                                            for p in (ROOT / 'system/studio-plugin/modules').glob('*.luau')),
                                        host_agent_text=host_sources())
        return issues, output

    def test_studio_debug_accepts_project_and_returns_bootstrap(self):
        issues, boot = self.debug()
        self.assertEqual(issues, [])
        self.assertIn('TestLoadoutService.Start()', boot)

    def test_studio_debug_rejects_missing_movement_api(self):
        with self.intercept('src/server/dev/MovementDebugService.luau',
                            lambda s: s.replace('GetMovementDebugCatalog', 'RemovedMovementCatalog')):
            issues, _ = self.debug()
        self.assertIn('Studio movement debugger server missing GetMovementDebugCatalog', issues)

    def test_studio_debug_rejects_removed_loadout_preview(self):
        with self.intercept('src/client/dev/TestLoadoutController.luau',
                            lambda s: s.replace('createAttackRadiusRing', 'RemovedRing')):
            issues, _ = self.debug()
        self.assertIn('Studio Test Loadout attack-radius preview missing createAttackRadiusRing', issues)

    def test_death_contract_accepts_project(self):
        issues, service = self.death()
        self.assertEqual(issues, [])
        self.assertIn('DeathTerminalReached', service)

    def test_death_contract_rejects_missing_terminal_policy(self):
        with self.intercept('src/shared/combat/DeathAnimationPolicy.luau',
                            lambda s: s.replace('DeathAnimationPolicy.LatchVisibleTerminalPose', 'RemovedTerminalPose')):
            issues, _ = self.death()
        self.assertIn('deterministic death terminal-hold policy missing function DeathAnimationPolicy.LatchVisibleTerminalPose', issues)

    def test_death_contract_rejects_missing_hit_sparks(self):
        with self.intercept('src/client/combat/effects/HitSparkBurst.luau',
                            lambda s: s.replace('NormalSparkCount', 'RemovedSparkCount')):
            issues, _ = self.death()
        self.assertIn('pooled hit sparks missing NormalSparkCount', issues)

    def test_timeline_contract_accepts_project_and_returns_shared_sources(self):
        issues, (html, bridge) = self.timeline()
        self.assertEqual(issues, [])
        self.assertIn('id="nav-timelines"', html)
        self.assertIn('run_timeline_editor_bridge', bridge)

    def test_timeline_contract_rejects_invalid_event_window(self):
        with self.intercept('assets/manifests/attack-timelines.json',
                            lambda s: json.dumps({**json.loads(s), 'schemaVersion': 99})):
            issues, _ = self.timeline()
        self.assertIn('m38 attack timeline manifest must use schemaVersion 2', issues)

    def test_timeline_contract_rejects_missing_studio_preview(self):
        with self.intercept('system/control-center/studio_bridge.py',
                            lambda s: s.replace('run_timeline_editor_bridge', 'RemovedTimelineBridge')):
            issues, _ = self.timeline()
        self.assertIn('m35 Studio timeline bridge missing run_timeline_editor_bridge', issues)

    def test_authoring_contract_accepts_project(self):
        issues = []
        check_authoring_tooling(ROOT, issues.append)
        self.assertEqual(issues, [])

    def test_authoring_contract_rejects_rojo_workspace_ownership(self):
        with self.intercept('default.project.json',
                            lambda s: json.dumps({**json.loads(s), 'tree': {
                                **json.loads(s)['tree'], 'Workspace': {'Baseplate': {}}}})):
            issues = []
            check_authoring_tooling(ROOT, issues.append)
        self.assertIn('m38 live Rojo Workspace must preserve unknown/authored Studio instances', issues)
        self.assertIn('m38 live Rojo must not own authored Workspace child Baseplate', issues)

    def test_authoring_contract_rejects_animation_ui_missing_help(self):
        with self.intercept('system/control-center/static/index.html',
                            lambda s: s.replace('each animation block is configured independently', 'RemovedHelpCopy')):
            issues = []
            check_authoring_tooling(ROOT, issues.append)
        self.assertIn('m40 Animation Speed help copy missing each animation block is configured independently', issues)


if __name__ == '__main__':
    unittest.main()
