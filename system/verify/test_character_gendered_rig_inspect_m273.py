"""M273: gendered Armature names and shared (common) geometry are separate axes.

Uses the real SQLite catalog with mocked Blender reports; no fake Roblox asset
is uploaded. Bind comparison must reject incompatible cross-gender rigs.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from character_core.components import CharacterComponents
from character_core.part_names import part_matches_source_rig, parse_part
from sqlite_connection import connect

IDENTITY = [1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.]


def report(rig_name, part_names, *, root_offset=0):
    m = IDENTITY[:]
    m[3] = root_offset
    bones = [dict(name='root', parent='', matrix=m),
             dict(name='hair_mount', parent='root', matrix=IDENTITY[:])]
    return dict(armature=rig_name+'_armature', bones=bones, parts=[
        dict(name=n, vertices=8, triangles=4, content_sha256=n,
             armature=rig_name+'_armature', skeleton=copy.deepcopy(bones), used_bones=['root'])
        for n in part_names])


class GenderedRigTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.src=self.root/'components.fbx'
        self.src.write_bytes(b'fixture')
        self.current=report('human_female', [
            'human_female_m001_head', 'human_female_m001_upper',
            'human_common_m001_gloves', 'human_common_m001_eye_l',
            'human_common_m001_eye_r', 'human_common_m001_eyebrow_l',
            'human_common_m001_eyebrow_r', 'human_common_m001_boots'])
        self.store=CharacterComponents(self.root, analyzer=self.analyzer)

    def analyzer(self, root, source, output=None):
        if output:
            output=Path(output)
            output.mkdir(parents=True, exist_ok=True)
            (output/'rig.fbx').write_bytes(b'rig')
            for part in self.current['parts']:
                (output/(part['name']+'.fbx')).write_bytes(b'mesh')
        return copy.deepcopy(self.current)

    def test_female_and_common_parts_inspect_without_rig_name_collision(self):
        plan=self.store.inspect(self.src)
        self.assertEqual(plan['rig_id'],'human_female')
        self.assertEqual(len(plan['parts']),8)
        self.assertEqual(plan['part_errors'],[])
        self.assertEqual({p['id']:p['allowedGenders'] for p in plan['parts']}['human_common_m001_boots'],['male','female'])
        self.store.register(plan['token'], [])
        self.assertEqual(self.store.get('part','human_female_m001_head')['rig_id'],'human_female')
        self.assertEqual(self.store.get('part','human_common_m001_boots')['rig_id'],'human_female')

    def test_male_named_mesh_rejected_on_female_rig(self):
        self.assertTrue(part_matches_source_rig(parse_part('human_common_m001_eye_l'),'human_female'))
        self.assertTrue(part_matches_source_rig(parse_part('human_female_m001_head'),'human_female'))
        self.assertFalse(part_matches_source_rig(parse_part('human_male_m001_head'),'human_female'))
        self.current['parts'].append(dict(name='human_male_m001_head', vertices=3, triangles=1,
                                          armature='human_female_armature', skeleton=self.current['bones'],
                                          content_sha256='wrong', used_bones=['root']))
        plan=self.store.inspect(self.src)
        self.assertTrue(plan['partial_required'])
        self.assertEqual(len(plan['parts']),8)
        self.assertIn('human_male_m001_head',plan['part_error'])

    def test_common_geometry_cross_rig_only_with_matching_published_bind_pose(self):
        plan=self.store.inspect(self.src)
        self.store.register(plan['token'], [])
        self.current=report('human_male',['human_male_m001_head'])
        plan=self.store.inspect(self.src)
        self.store.register(plan['token'], [])
        with connect(self.store.db) as db:
            db.execute("UPDATE character_component_records SET model_asset_id='12345',published_revision=revision WHERE kind='rig'")
        common=self.store.get('part','human_common_m001_gloves')
        female=self.store.get('part','human_female_m001_head')
        self.assertTrue(self.store.part_compatible_with_rig(common,'human_female'))
        self.assertTrue(self.store.part_compatible_with_rig(common,'human_male'))
        self.assertFalse(self.store.part_compatible_with_rig(female,'human_male'))
        # The male rig acquires a genuinely different bind pose. It is no
        # longer safe to reuse a skinned female-authored common MeshPart.
        male=self.store.get('rig','human_male')
        meta=json.loads(male['metadata_json'])
        meta['bones'][0]['matrix'][3]=1.0
        with connect(self.store.db) as db:
            db.execute("UPDATE character_component_records SET metadata_json=? WHERE kind='rig' AND id='human_male'", (json.dumps(meta),))
        self.assertFalse(self.store.part_compatible_with_rig(common,'human_male'))

    def test_standalone_gendered_hair_uses_existing_shared_rig_if_only_shared_exists(self):
        # A Blender report of a rigless female hair will name the proposed
        # rig human_female. If only human exists, bind to that registered rig.
        self.current=report('human',[])
        self.current['parts']=[dict(name='human_female_m004_hair', vertices=5, triangles=3,
            content_sha256='hair', armature='', skeleton=[], used_bones=[],
            attachment='hair_mount', attachment_mode='pivot')]
        plan=self.store.inspect(self.src)
        self.store.register(plan['token'],[])
        self.current['armature']='human_female_armature'
        self.current['rig_present']=False
        plan=self.store.inspect(self.src)
        self.assertEqual(plan['rig_id'],'human')
        self.assertEqual(plan['parts'][0]['id'],'human_female_m004_hair')


if __name__=='__main__':
    unittest.main()

class BlenderWeightReportTests(unittest.TestCase):
    def _inspect_invalid(self, weights):
        # Exercise the Blender-side validator without launching Blender.
        from test_character_rigid_hair_m194 import HairImportTests, FakeMesh
        from types import SimpleNamespace
        mesh=FakeMesh('human_female_m001_head')
        adapter,bpy,rig,_=HairImportTests().load_adapter(mesh)
        rig.name='human_female_armature'
        mesh.modifiers=[SimpleNamespace(type='ARMATURE',object=rig)]
        mesh.vertex_groups=[SimpleNamespace(index=0,name='root')]
        for index,vertex in enumerate(mesh.data.vertices):
            vertex.index=index
            vertex.groups=[SimpleNamespace(group=0,weight=weights)] if weights is not None else []
        with tempfile.TemporaryDirectory() as folder:
            adapter.main(Path(folder)/'test.fbx',Path(folder)/'report.json')

    def test_reports_missing_weights_instead_of_ambiguous_1_to_4_error(self):
        with self.assertRaisesRegex(ValueError,'vertex 0 has no weights to bones'):
            self._inspect_invalid(None)

    def test_normalizes_existing_vertex_weight_instead_of_rejecting_it(self):
        # 1 influenced bone with a weight of 0.8 becomes 1.0 in the staged FBX.
        # This adapter uses the real Blender normalization path via M274 mocks.
        from test_character_skin_auto_normalize_m274 import make_head, inspect_head
        mesh=make_head()
        for vertex in mesh.data.vertices:
            vertex.groups[0].weight = 0.8
            vertex.groups[1].weight = 0
        result=inspect_head(mesh)
        self.assertEqual(result['parts'][0]['normalized_vertices'],3)
        self.assertTrue(all(abs(v.groups[0].weight-1)<1e-6 for v in mesh.data.vertices))
