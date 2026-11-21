"""M409: explicit rig choice is scoped to selected geometry; no skeleton bypass for skinned rigs."""
import pathlib
import sys
import unittest
from collections import defaultdict
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTROL = ROOT / 'system' / 'control-center'
sys.path.insert(0, str(CONTROL))
from api.write_world import route
from services.studio_deco_bridge import run_deco_refresh_bridge


class RigChoiceTest(unittest.TestCase):
    def test_invalid_modes_and_out_of_scope_keys_rejected_before_bridge(self):
        base=dict(slug='lantern_01',binding_revision=3,model_asset_id='12345',
                  atlas_asset_id='777',phase='replace',scan_token='a'*32,
                  selected_keys=['p1'])
        for choices in ({'p2':'static'},{'p1':'skip_all'},{'p1':False},['static']):
            with self.subTest(choices=choices),self.assertRaises(ValueError):
                run_deco_refresh_bridge(**base,rig_choices=choices)

    def test_http_api_passes_rig_choice_without_changing_atlas_contract(self):
        class Assets:
            def __init__(self): self.atlases=self
            def get(self,slug):
                return dict(slug=slug,model_asset_id='12345',texture_asset_id='777',
                            bindingRevision=3,appearanceMode='material_atlas')
            def binding(self,*a): return {'revision':3}
            def export(self): pass
            def mark_synced(self,*a): return True
        assets=Assets()
        result=dict(operationId='a'*32,targetSlug='lantern_01',models=0,parts=0,
                    matchedModels=1,modelReferences=0,pendingGeometry=0,
                    geometryUpdated=0,meshPartsUpdated=0,replacedModels=0,
                    registryItems=1,changes=[],instances=[],fullySynced=False)
        sync=mock.Mock(return_value=result)
        deps=defaultdict(lambda:None,dict(location_assets=assets,
                    sync_location_assets_to_studio=sync,
                    location_asset_sync_history=mock.Mock()))
        payload={'slug':'lantern_01','phase':'replace','scanToken':'a'*32,
                 'selectedKeys':['p1'],'rigChoices':{'p1':'static'}}
        code,out=route('/api/location-assets/studio-sync',lambda:payload,deps)
        self.assertEqual(code,200,out)
        self.assertEqual(sync.call_args.kwargs['rig_choices'],{'p1':'static'})
        self.assertEqual(sync.call_args.kwargs['selected_keys'],['p1'])

    def test_static_mode_preserves_immutable_mesh_and_hierarchy_verification(self):
        loader=(ROOT/'system/studio-plugin/modules/DecoAssetLoader.luau').read_text()
        sync=(ROOT/'system/studio-plugin/modules/DecoPlacedAssetSync.luau').read_text()
        commands=(ROOT/'system/studio-plugin/modules/StudioDecoSyncCommands.luau').read_text()
        self.assertIn('if static then',loader)
        self.assertIn('item:IsA("Bone") or item.Name=="rig_carrier"',loader)
        self.assertIn('RetiredCleanup.CleanLocation(model)',loader)
        self.assertIn('historical rig manifest unavailable; no Place geometry modified',loader)
        self.assertIn('History.VerifyChildren(previousPublished,previousChildren)',sync)
        self.assertIn('History.MatchesInventory(model,entry)',sync)
        self.assertIn('Ownership.HasNestedPlacements(model)',sync)
        self.assertIn('RigSwap.Rollback(item.swap)',sync)
        self.assertIn('historicalRigChoices[entry.root]',sync)
        self.assertIn('rig selection must refer to a selected MeshPart',commands)


if __name__=='__main__': unittest.main()
