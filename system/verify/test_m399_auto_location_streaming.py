"""M399: all scanned registered types stream by default, independent of rig/effects/slug.

Explicit Off remains an author control. Failed verification must stop Preflight,
never silently keep a selected model in Workspace.
"""
import copy
import json
import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system'/'control-center'))
sys.path.insert(0, str(ROOT/'system'/'verify'))
from services.location_runtime_build import RuntimePlaceBuilder, build_rows
from services.location_streaming_config import DEFAULT_SETTINGS, runtime_mode, validate_settings
from test_m398_runtime_painter_physics import PainterRuntime, FakeRegistry


class AutomaticLocationCoverage(unittest.TestCase):
    def setUp(self):
        fixture=PainterRuntime('test_compiles_painter_without_losing_effects_or_changing_authoring')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.__dict__.update({k:v for k,v in fixture.__dict__.items() if k in ('root','external','report','overview','settings','source','path')})
        # New asset slug introduced after the project config was saved.
        # Its rig and children are unchanged and must need NO code/config change.
        new_slug='sconce_99'
        tree=ET.parse(self.source)
        for prop in tree.iter('string'):
            if prop.get('name')=='Name' and prop.text and 'lantern_02' in prop.text:
                prop.text=prop.text.replace('lantern_02',new_slug)
        tree.write(self.source, encoding='utf-8', xml_declaration=True)
        old=self.external['path']
        self.external['slug']=new_slug
        self.external['authorSlug']=new_slug
        self.external['path']=old.replace('lantern_02',new_slug)
        self.external['ownerPath']=self.external['path']
        self.external['name']=self.external['name'].replace('lantern_02',new_slug)
        self.external['hierarchy']=[dict(node, name=node['name'].replace('lantern_02',new_slug))
                                    for node in self.external['hierarchy']]
        self.overview['items'][0]['slug']=new_slug
        self.settings['modes']={}

    def rows(self):
        return build_rows(self.overview, FakeRegistry(self.report), self.settings)

    def test_new_slug_is_selected_automatically_and_effects_survive(self):
        slug='sconce_99'
        self.assertEqual(runtime_mode(self.settings,slug),'full')
        rows=self.rows()
        self.assertEqual([r['slug'] for r in rows],[slug])
        builder=RuntimePlaceBuilder(self.root)
        inspected=builder.inspect(rows,self.settings)
        result=builder.prepare(rows,expected_sha=inspected['sourceSha256'],
            snapshot_id=189,catalog_digest='unit',settings=self.settings)
        runtime=ET.parse(result['runtimePath'])
        classes=[node.get('class') for node in runtime.iter('Item')]
        self.assertIn('Part',classes)
        for kind in ('Bone','PointLight','Fire','ParticleEmitter','Weld'):
            self.assertIn(kind,classes)
        manifest=json.loads(Path(result['manifestPath']).read_text(encoding='utf8'))
        self.assertEqual(manifest['modes'][slug],'full')

    def test_explicit_off_only_disables_requested_slug(self):
        self.settings['modes']['sconce_99']='off'
        self.assertEqual(runtime_mode(self.settings,'sconce_99'),'off')
        self.assertEqual(runtime_mode(self.settings,'later_torch'),'full')
        with self.assertRaisesRegex(ValueError,'Select at least one'):
            self.rows()

    def test_new_slug_with_bad_physics_fails_preflight(self):
        target=next(n for n in self.external['hierarchy'] if n['name']=='sconce_99')
        target['canCollide']=True
        target['collisionFidelity']='Enum.CollisionFidelity.PreciseConvexDecomposition'
        with self.assertRaisesRegex(ValueError,'Box fidelity'):
            self.rows()

    def test_auto_settings_validation_and_existing_lod_modes(self):
        settings=copy.deepcopy(DEFAULT_SETTINGS)
        settings['modes']={'sconce_99':'auto','other_sconce':'lod1'}
        validate_settings(settings)
        self.assertEqual(runtime_mode(settings,'sconce_99'),'full')
        self.assertEqual(runtime_mode(settings,'other_sconce'),'lod1')

    def test_no_hardcoded_location_slug_in_shipped_profile(self):
        config=json.loads((ROOT/'config'/'location_streaming.json').read_text('utf8'))
        self.assertEqual(set(config['modes']),{'stone_fence_02','stone_pillar_03','stone_ladder_02'})

if __name__=='__main__': unittest.main()
