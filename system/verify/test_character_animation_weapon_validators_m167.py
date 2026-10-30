"""M167 domain-validator regressions; mutation is intercepted in memory only."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/verify'))
from validators.characters import (
    check_character_manifest, check_character_rig, check_character_publication,
    check_character_identity, check_character_starting_stats,
)
from validators.animations import (
    check_character_animation, check_animation_scaling, check_manual_animation_reimport,
)
from validators.weapons import check_weapon_registration, check_weapon_attack_movement


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding='utf-8')


class DomainValidatorM167Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = read('system/control-center/host_agent.py') + '\n' + '\n'.join(
            p.read_text(encoding='utf-8')
            for folder in ('api', 'services')
            for p in (ROOT / 'system/control-center' / folder).glob('*.py')
        )
        cls.plugin = read('system/studio-plugin/Game1Bridge.server.luau') + '\n' + '\n'.join(
            read('system/studio-plugin/modules/' + name) for name in (
                'StudioModelLoadCommands.luau', 'StudioActorSpawnCommands.luau',
                'StudioDebugPreferenceBridge.luau',
            )
        )

    def swap_read(self, relative, change):
        """Never edit a user file or database, including during negative tests."""
        target = ROOT / relative
        original = Path.read_text

        def intercepted(path, *args, **kwargs):
            data = original(path, *args, **kwargs)
            return change(data) if path == target else data

        return patch.object(Path, 'read_text', intercepted)

    def character_inputs(self):
        issues = []
        archetypes, active_id = check_character_manifest(ROOT, issues.append)
        character_service, rig = check_character_rig(ROOT, issues.append)
        schema, ui, js, character_js = check_character_publication(
            ROOT, issues.append, host_agent_text=self.host,
            plugin_text=self.plugin, archetypes=archetypes,
        )
        self.assertEqual(issues, [])
        return archetypes, active_id, character_service, rig, schema, ui, js, character_js

    def animation_inputs(self):
        _, _, character_service, _, schema, ui, js, character_js = self.character_inputs()
        issues = []
        outputs = check_character_animation(
            ROOT, issues.append, schema_text=schema, ui=ui,
            js=js, character_service_text=character_service,
        )
        self.assertEqual(issues, [])
        return character_service, schema, ui, character_js, outputs

    def weapon_inputs(self):
        _, _, character_service, rig, schema, ui, js, character_js = self.character_inputs()
        _, _, controller, client_init, attack_controller, _, js_text = self.animation_inputs()[-1]
        issues = []
        sources = check_weapon_registration(
            ROOT, issues.append, schema_text=schema, ui=ui,
            host_agent_text=self.host, plugin_text=self.plugin, rig_text=rig,
            character_service_text=character_service,
            attack_text=read('src/server/combat/AttackService.luau'),
            controller_runtime=controller, attack_controller_text=attack_controller,
            client_init_text=client_init,
        )
        self.assertEqual(issues, [])
        return schema, ui, character_js, character_service, sources, js_text

    def test_all_three_domains_accept_project(self):
        archetypes, _, character_service, _, schema, ui, js, character_js = self.character_inputs()
        _, _, controller, _, _, _, js_text = self.animation_inputs()[-1]
        schema, ui, character_js, character_service, (stats_config, stats_service, _), js_text = self.weapon_inputs()
        issues = []
        check_character_identity(ROOT, issues.append, schema_text=schema, ui=ui, host_agent_text=self.host, js_text=js_text)
        check_character_starting_stats(ROOT, issues.append, character_service_text=character_service, stats_service_text=stats_service)
        check_animation_scaling(ROOT, issues.append, ui=ui, host_agent_text=self.host,
                                character_js_text=character_js,
                                animation_registry_text=self.animation_inputs()[-1][1],
                                attack_timeline_text=read('src/shared/combat/AttackTimelineConfig.luau'))
        studio_text = check_manual_animation_reimport(ROOT, issues.append, animation_store_text=self.animation_inputs()[-1][0],
                                                      character_js_text=character_js, host_agent_text=self.host)
        check_weapon_attack_movement(ROOT, issues.append, host_agent_text=self.host)
        self.assertEqual(issues, [])
        self.assertIn('model bridge v24', studio_text)

    def test_character_manifest_wrong_gender_pool(self):
        with self.swap_read('assets/manifests/character-archetypes.json',
                            lambda text: json.dumps({**json.loads(text), 'genderPool': ['male']})):
            issues = []
            check_character_manifest(ROOT, issues.append)
        self.assertIn('character gender pool must be male/female', issues)

    def test_character_rig_missing_authored_root(self):
        with self.swap_read('src/server/character/CharacterRigService.luau',
                            lambda text: text.replace('registered character template is missing ImportedRig/RootPart', 'MISSING_ROOT')):
            issues = []
            check_character_rig(ROOT, issues.append)
        self.assertIn('registered characters must require the canonical Studio-authored RootPart', issues)

    def test_publication_bone_weight_contract(self):
        archetypes = self.character_inputs()[0]
        with self.swap_read('system/asset-manager/bone_weight_survival.py',
                            lambda text: text.replace('MAX_INFLUENCES = 4', 'MAX_INFLUENCES = 8')):
            issues = []
            check_character_publication(ROOT, issues.append, host_agent_text=self.host, plugin_text=self.plugin, archetypes=archetypes)
        self.assertIn('shared publication bone-survival planner missing MAX_INFLUENCES = 4', issues)

    def test_animation_resolver_contract(self):
        _, _, character_service, _, schema, ui, js, _ = self.character_inputs()
        with self.swap_read('src/client/character/animation/AnimationResolver.luau',
                            lambda text: text.replace('ResolveLocomotion', 'RenamedLocomotion')):
            issues = []
            check_character_animation(ROOT, issues.append, schema_text=schema, ui=ui, js=js, character_service_text=character_service)
        self.assertIn('animation resolver missing ResolveLocomotion', issues)

    def test_animation_scaling_schema_contract(self):
        _, schema, ui, char_js, sources = self.animation_inputs()
        with self.swap_read('assets/manifests/animation-speed-scaling.json',
                            lambda text: json.dumps({**json.loads(text), 'schemaVersion': 9})):
            issues = []
            check_animation_scaling(ROOT, issues.append, ui=ui, host_agent_text=self.host,
                                    character_js_text=char_js, animation_registry_text=sources[1],
                                    attack_timeline_text=read('src/shared/combat/AttackTimelineConfig.luau'))
        self.assertIn('animation speed scaling manifest must be game1 schema 1', issues)

    def test_weapon_manifest_contract(self):
        inputs = self.character_inputs()
        _, _, controller, client_init, attack_controller, _, _ = self.animation_inputs()[-1]
        with self.swap_read('assets/manifests/weapons.json',
                            lambda text: json.dumps({**json.loads(text), 'schemaVersion': 99})):
            issues = []
            check_weapon_registration(
                ROOT, issues.append, schema_text=inputs[4], ui=inputs[5],
                host_agent_text=self.host, plugin_text=self.plugin, rig_text=inputs[3],
                character_service_text=inputs[2], attack_text=read('src/server/combat/AttackService.luau'),
                controller_runtime=controller, attack_controller_text=attack_controller, client_init_text=client_init,
            )
        self.assertIn('weapon manifest must be game1 schema 2', issues)

    def test_weapon_movement_contract(self):
        with self.swap_read('src/client/character/MovementController.luau',
                            lambda text: text.replace('BeginAttackMovement', 'RenamedAttackMovement')):
            issues = []
            check_weapon_attack_movement(ROOT, issues.append, host_agent_text=self.host)
        self.assertIn('moving attack runtime control missing BeginAttackMovement', issues)

    def test_manual_reimport_contract(self):
        _, schema, ui, char_js, sources = self.animation_inputs()
        with self.swap_read('system/control-center/animation_reimport_check.py',
                            lambda text: text.replace('find_confirmed_manual_reimport', 'renamed_manual_check')):
            issues = []
            check_manual_animation_reimport(ROOT, issues.append,
                                            animation_store_text=sources[0], character_js_text=char_js,
                                            host_agent_text=self.host)
        self.assertIn('manual animation reimport confirmation missing find_confirmed_manual_reimport', issues)

    def test_validation_never_writes_input_data(self):
        files = (ROOT / 'assets/manifests/character-archetypes.json',
                 ROOT / 'assets/manifests/animation-speed-scaling.json',
                 ROOT / 'assets/manifests/weapons.json')
        before = {p: p.read_bytes() for p in files}
        self.test_all_three_domains_accept_project()
        self.assertEqual(before, {p: p.read_bytes() for p in files})


if __name__ == '__main__':
    unittest.main()
