"""M169: read-only Location/Deco/Environment validators, negative contracts and handoffs."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/verify'))

from validators.deco_studio import check_deco_studio
from validators.environment_bounce import check_environment_bounce
from validators.location_authoring import check_location_authoring
from validators.location_assets import check_location_assets_core
from validators.location_asset_categories import check_location_asset_categories
from validators.location_asset_variants import check_location_asset_variants
from validators.location_texture_sync import check_location_texture_sync


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def host_sources():
    return read('system/control-center/host_agent.py') + '\n' + '\n'.join(
        p.read_text(encoding='utf-8')
        for folder in ('api', 'services')
        for p in (ROOT / 'system/control-center' / folder).glob('*.py')
    )


def studio_sources():
    return read('system/studio-plugin/Game1Bridge.server.luau') + '\n' + '\n'.join(
        read('system/studio-plugin/modules/' + name)
        for name in ('StudioModelLoadCommands.luau', 'StudioActorSpawnCommands.luau', 'StudioDebugPreferenceBridge.luau')
    )


class LocationDecoEnvironmentM169Tests(unittest.TestCase):
    @staticmethod
    def change_file(relative, replace):
        target = ROOT / relative
        original = Path.read_text

        def injected(path, *args, **kwargs):
            text = original(path, *args, **kwargs)
            return replace(text) if path == target else text

        return patch.object(Path, 'read_text', injected)

    def setUp(self):
        self.host = host_sources()
        self.studio = studio_sources()
        self.sources = None

    def core(self):
        issues = []
        sources = check_location_assets_core(ROOT, issues.append,
            host_agent_text=self.host, studio_plugin_text=self.studio)
        return issues, sources

    def variants(self, sources=None):
        issues = []
        check_location_asset_variants(ROOT, issues.append,
            sources=sources or self.core()[1],
            host_agent_text=self.host, studio_plugin_text=self.studio)
        return issues

    def bounce(self, sources=None):
        issues = []
        result = check_environment_bounce(ROOT, issues.append,
            sources=sources or self.core()[1],
            host_agent_text=self.host, studio_plugin_text=self.studio)
        return issues, result

    def test_all_seven_domains_accept_project_and_share_explicit_sources(self):
        issues = []
        check_location_authoring(ROOT, issues.append,
            index_text=read('system/control-center/static/index.html'),
            host_agent_text=self.host,
            studio_bridge_text=read('system/control-center/studio_bridge.py'),
            studio_plugin_text=self.studio)
        core_issues, sources = self.core()
        self.assertEqual(core_issues, [])
        self.assertEqual(sources.manifest_path.name, 'location-assets.json')
        check_deco_studio(ROOT, issues.append, sources=sources,
                          host_agent_text=self.host, studio_plugin_text=self.studio)
        check_location_asset_variants(ROOT, issues.append, sources=sources,
                                      host_agent_text=self.host, studio_plugin_text=self.studio)
        check_environment_bounce(ROOT, issues.append, sources=sources,
                                 host_agent_text=self.host, studio_plugin_text=self.studio)
        check_location_texture_sync(ROOT, issues.append, sources=sources,
            environment_asset_service_text=read('src/server/world/EnvironmentAssetService.luau'))
        check_location_asset_categories(ROOT, issues.append, sources=sources,
            character_js_text=read('system/control-center/static/character-assets.js'),
            studio_plugin_text=self.studio, install_plugin_text=read('system/studio-plugin/install.ps1'))
        # Existing M168 behavior: post-exit M54 check emits an issue but the
        # legacy CLI still exits 0. Fixing that exit boundary is separate work.
        self.assertEqual(issues, ['m54 Location Assets markup missing game1 location asset · Oak Tree'])

    def test_locations_rejects_missing_polygon_validation(self):
        with self.change_file('system/control-center/location_store.py',
                              lambda s: s.replace('_validate_polygon', 'removed_polygon')):
            issues = []
            check_location_authoring(ROOT, issues.append,
                index_text=read('system/control-center/static/index.html'),
                host_agent_text=self.host,
                studio_bridge_text=read('system/control-center/studio_bridge.py'),
                studio_plugin_text=self.studio)
        self.assertIn('m41 LocationStore missing _validate_polygon', issues)

    def test_locations_rejects_manifest_project(self):
        with self.change_file('assets/manifests/locations.json',
                              lambda s: json.dumps({**json.loads(s), 'project': 'wrong'})):
            issues = []
            check_location_authoring(ROOT, issues.append,
                index_text=read('system/control-center/static/index.html'),
                host_agent_text=self.host,
                studio_bridge_text=read('system/control-center/studio_bridge.py'),
                studio_plugin_text=self.studio)
        self.assertEqual(issues, ['m41 locations.json schema/project is invalid'])

    def test_location_assets_rejects_invalid_category_order(self):
        with self.change_file('assets/manifests/location-assets.json',
                              lambda s: json.dumps({**json.loads(s), 'options': {'categories': [{'id': 'prop'}]}})):
            issues, _ = self.core()
        self.assertIn('m128 Location Assets manifest categories have invalid canonical order', issues)

    def test_location_assets_rejects_missing_published_status(self):
        with self.change_file('system/control-center/location_asset_store.py',
                              lambda s: s.replace('return "PUBLISHED"', 'return "BAD_STATUS"')):
            issues, _ = self.core()
        self.assertIn('m43 LocationAssetStore missing return "PUBLISHED"', issues)

    def test_deco_studio_save_rejects_missing_native_helper(self):
        issues, sources = self.core()
        self.assertEqual(issues, [])
        with self.change_file('system/control-center/studio_save.py',
                              lambda s: s.replace('request_active_studio_save', 'removed_native_save')):
            check_deco_studio(ROOT, issues.append, sources=sources,
                host_agent_text=self.host, studio_plugin_text=self.studio)
        self.assertIn('m45 Studio-native save helper missing request_active_studio_save', issues)

    def test_variants_reject_removed_shared_texture_owner(self):
        issues, sources = self.core()
        self.assertEqual(issues, [])
        altered = sources._replace(store_text=sources.store_text.replace('_resolve_texture_owner', 'removed_owner'))
        self.assertIn('m46 shared Location Asset texture support missing def _resolve_texture_owner',
                      self.variants(altered))

    def test_variants_reject_missing_authored_pivot(self):
        with self.change_file('system/studio-plugin/modules/DecoTransform.luau',
                              lambda s: s.replace('function DecoTransform.previewPivot', 'removed_preview_pivot')):
            issues = self.variants()
        self.assertIn('m48 DecoTransform missing function DecoTransform.previewPivot', issues)

    def test_environment_bounce_rejects_missing_damage_window_invalidation(self):
        with self.change_file('src/server/combat/AttackSessionStore.luau',
                              lambda s: s.replace('session.damageWindow = nil', 'removed_window = nil')):
            issues, _ = self.bounce()
        self.assertIn('m50 AttackSessionStore bounce invalidation missing session.damageWindow = nil', issues)

    def test_environment_bounce_rejects_nonboolean_manifest_policy(self):
        with self.change_file('assets/manifests/location-assets.json',
                              lambda s: json.dumps({**json.loads(s), 'items': [{**(json.loads(s)['items'][0]), 'destructible': 'yes'}]})):
            issues, _ = self.bounce()
        self.assertTrue(any('m50 Location Asset destructible policy missing/invalid' in e for e in issues))

    def test_texture_sync_rejects_legacy_in_place_image_updates(self):
        issues, sources = self.core()
        altered = sources._replace(store_text=sources.store_text + '\nupdate_image_asset')
        check_location_texture_sync(ROOT, issues.append, sources=altered,
            environment_asset_service_text=read('src/server/world/EnvironmentAssetService.luau'))
        self.assertIn('m51 Location Assets still contain legacy in-place Image Asset updates', issues)

    def test_categories_reject_missing_library_category_synchronization(self):
        issues, sources = self.core()
        altered = sources._replace(assets_js=sources.assets_js.replace("decoAssetUseCategory(category);", 'removed_category_sync();'))
        check_location_asset_categories(ROOT, issues.append, sources=altered,
            character_js_text=read('system/control-center/static/character-assets.js'),
            studio_plugin_text=self.studio, install_plugin_text=read('system/studio-plugin/install.ps1'))
        self.assertIn('m55 library category must synchronize editor category', issues)

    def test_checks_do_not_modify_manifests_or_create_database(self):
        tracked = [ROOT / 'assets/manifests/locations.json', ROOT / 'assets/manifests/location-assets.json']
        before = [p.read_bytes() for p in tracked]
        self.assertEqual(self.core()[0], [])
        self.assertEqual(self.variants(), [])
        self.assertEqual(self.bounce()[0], [])
        self.assertEqual(before, [p.read_bytes() for p in tracked])


if __name__ == '__main__':
    unittest.main()
