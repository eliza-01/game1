"""M353: deliberate shear override and focus, without bypassing transaction safety."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.location_instance_manager import LocationInstanceManager
from services.studio_location_instance_bridge import run_location_instance_bridge
from test_location_instance_manager_m344 import FakeAssets
from services.place_registry.catalog import build_catalog


class UnrestrictedFocusContract(unittest.TestCase):
    def setUp(self):
        self.requests=[]
        self.manager=LocationInstanceManager(FakeAssets(),lambda **kw:
            self.requests.append(kw) or {'count':1})
        self.guid='12345678-1234-1234-1234-123456789abc'
        self.base=dict(phase='focus',sourceSlug='stone_fence_01',targetSlug='stone_fence_02',
                       scope='selected',scanToken=self.guid,anchorId='geometry',
                       inspectionToken=self.guid,focusIndex=1,focusPartId='wall')

    def test_focus_requires_specific_inspection_and_warning(self):
        self.manager.operate(dict(self.base))
        self.assertEqual(self.requests[-1]['focus_index'],1)
        self.assertEqual(self.requests[-1]['focus_part_id'],'wall')
        for modifications in ({'inspectionToken':''},{'focusIndex':0},{'focusIndex':True},
                              {'focusIndex':1001},{'focusPartId':'bad name'},
                              {'approveShear':True}):
            with self.subTest(modifications=modifications),self.assertRaises(ValueError):
                self.manager.operate({**self.base,**modifications})
        with self.assertRaises(ValueError):
            self.manager.operate({**self.base,'phase':'replace','focusIndex':1})

    def test_clear_is_bound_to_specific_inspection(self):
        data={**self.base,'phase':'clear','focusIndex':0,'focusPartId':''}
        self.manager.operate(data)
        self.assertEqual(self.requests[-1]['inspection_token'],self.guid)
        with self.assertRaises(ValueError):
            self.manager.operate({**data,'approveShear':True})
        self.manager.operate({**data,'inspectionToken':''})
        self.assertEqual(self.requests[-1]['inspection_token'],'')

    def test_transport_does_not_accept_focus_without_token(self):
        catalog=build_catalog(FakeAssets())
        base=dict(catalog=catalog, phase='focus',source_slug='stone_fence_01',
                  target_slug='stone_fence_02',scope='selected', scan_token=self.guid,
                  anchor_id='geometry',inspection_token=self.guid,focus_index=1,focus_part_id='wall')
        for change in ({'inspection_token':''},{'focus_index':0},
                       {'focus_part_id':'bad:name'}, {'approve_shear':True}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                run_location_instance_bridge(**{**base,**change},timeout_seconds=0.01)

    def test_studio_focus_preserves_selection_and_newer_token(self):
        lua=(ROOT/'system/studio-plugin/modules/StudioLocationInstanceReplace.luau').read_text(encoding='utf8')
        ghost=(ROOT/'system/studio-plugin/modules/StudioLocationInstanceCollisionPreview.luau').read_text(encoding='utf8')
        html=(ROOT/'system/control-center/static/index.html').read_text(encoding='utf8')
        js=(ROOT/'system/control-center/static/location-instance-manager.js').read_text(encoding='utf8')
        self.assertIn('current.inspectedProblems',lua)
        self.assertIn('command.inspectionToken ~= current.inspectedToken',lua)
        self.assertIn('Stale collision cleanup ignored',lua)
        self.assertIn('CollisionPreview.Focus(config.Workspace,overlay',lua)
        self.assertIn('session = nil',lua)
        self.assertIn('camera.CFrame = CFrame.lookAt',ghost)
        focus=ghost[ghost.index('function Preview.Focus('):ghost.index('function Preview.Clear(')]
        self.assertNotIn('Selection:Set',focus)
        self.assertIn('data-li-focus-index=',js)
        self.assertIn("send('focus',p.token,inspection.token",js)
        self.assertIn('Были бы заблокированы:',js)
        self.assertIn('Разрешить увеличенные / приближённые коллизии',html)
        self.assertIn('li-approve-shear',html)
        self.assertIn('if excessive and allowExcessive ~= true',
            (ROOT/'system/studio-plugin/modules/StudioLocationCollisionTransform.luau').read_text(encoding='utf8'))

if __name__=='__main__':unittest.main()
