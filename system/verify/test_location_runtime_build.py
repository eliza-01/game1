"""Runtime draft build safety: only vetted visual MeshParts, backup before deletion."""
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from services.location_runtime_build import RuntimePlaceBuilder, _sha, build_rows


def sample_cframe(x):
    return [x, 20, 30, 1, 0, 0, 0, 1, 0, 0, 0, 1]


def part(parent, name, classname, cframe, size, mesh_id=None, referent=None):
    node = ET.SubElement(parent, 'Item', {'class':classname,'referent':referent or ('RBX_' + name)})
    props = ET.SubElement(node, 'Properties')
    ET.SubElement(props, 'string', name='Name').text = name
    cf = ET.SubElement(props, 'CoordinateFrame', name='CFrame')
    for axis, value in zip(('X','Y','Z','R00','R01','R02','R10','R11','R12','R20','R21','R22'),cframe):
        ET.SubElement(cf, axis).text = str(value)
    vec = ET.SubElement(props, 'Vector3', name='size')
    for axis,value in zip(('X','Y','Z'),size):
        ET.SubElement(vec,axis).text = str(value)
    if mesh_id:
        ET.SubElement(ET.SubElement(props,'Content',name='MeshContent'),'uri').text='rbxassetid://' + mesh_id
    return node


def fixture(tmp):
    root = ET.Element('roblox',version='4')
    workspace = ET.SubElement(root,'Item',{'class':'Workspace','referent':'RBX_WS'})
    ET.SubElement(ET.SubElement(workspace,'Properties'),'string',name='Name').text='Workspace'
    replicated = ET.SubElement(root,'Item',{'class':'ReplicatedStorage','referent':'RBX_RS'})
    ET.SubElement(ET.SubElement(replicated,'Properties'),'string',name='Name').text='ReplicatedStorage'
    folder = ET.SubElement(workspace,'Item',{'class':'Folder','referent':'RBX_FOLDER'})
    ET.SubElement(ET.SubElement(folder,'Properties'),'string',name='Name').text='Fences'
    placements=[]
    for index, slug in enumerate(('stone_fence_02','stone_pillar_03')):
        name = slug+'__0000000'+str(index)
        model = ET.SubElement(folder,'Item',{'class':'Model','referent':'RBX_MODEL_'+str(index)})
        ET.SubElement(ET.SubElement(model,'Properties'),'string',name='Name').text=name
        cf=sample_cframe(index+1)
        part(model,slug,'MeshPart',cf,[4,5,6],str(700+index),'RBX_MESH_'+str(index))
        part(model,'__Game1Collision_Part','Part',cf,[4,5,6],None,'RBX_COLL_'+str(index))
        placements.append({'slug':slug,'path':'Workspace.Fences.'+name,'placementId':'uuid-'+str(index),'meshId':str(700+index),'hierarchy':[
            {'class':'Model','name':name},
            {'class':'MeshPart','name':slug,'cframe':cf,'size':[4,5,6]},
            {'class':'Part','name':'__Game1Collision_Part','cframe':cf,'size':[4,5,6]},
        ],'issues':[], 'pivotEvidence':{'modelPivot':cf}})
    # External model remains exactly in the runtime Place.
    foreign=ET.SubElement(folder,'Item',{'class':'Model','referent':'RBX_OTHER'})
    ET.SubElement(ET.SubElement(foreign,'Properties'),'string',name='Name').text='UnmanagedPackage'
    source = tmp/'place'/'game1_runtime_source.rbxlx'
    source.parent.mkdir()
    ET.ElementTree(root).write(source,encoding='utf-8',xml_declaration=True)
    return source,placements


class RuntimeBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source,self.rows=fixture(self.root)
        self.builder=RuntimePlaceBuilder(self.root)

    def test_backup_is_binary_identical_and_runtime_strips_only_visuals(self):
        before=self.source.read_bytes()
        inspected=self.builder.inspect(self.rows)
        self.assertEqual(inspected['eligible'],2)
        result=self.builder.prepare(self.rows,expected_sha=inspected['sourceSha256'],snapshot_id=133,catalog_digest='digest')
        self.assertEqual(self.source.read_bytes(),before)
        self.assertEqual(Path(result['backupPath']).read_bytes(),before)
        runtime=ET.parse(result['runtimePath'])
        self.assertEqual(len(list(runtime.iter('Item'))), 9)
        self.assertEqual([x.get('class') for x in runtime.iter('Item')].count('MeshPart'),0)
        self.assertEqual([x.get('class') for x in runtime.iter('Item')].count('Part'),2)
        self.assertTrue(any(e.text == 'UnmanagedPackage' for e in runtime.iter('string')))
        manifest=json.loads(Path(result['manifestPath']).read_text(encoding='utf-8'))
        self.assertEqual(manifest['removedVisualMeshParts'],2)
        self.assertFalse(manifest['publishAllowed'])

    def test_reveal_completed_runtime_from_actual_build_result(self):
        from services.location_lod_manager import LocationLodManager
        from api.write_dispatch import dispatch_post
        inspected = self.builder.inspect(self.rows)
        result = self.builder.prepare(self.rows, expected_sha=inspected['sourceSha256'],
                                      snapshot_id=133, catalog_digest='digest')
        manager = LocationLodManager.__new__(LocationLodManager)
        manager.builder = self.builder
        deps = {'lod_manager': manager}
        def reveal(payload):
            return dispatch_post('/api/lod-manager/reveal-build', lambda: payload, deps)
        with patch('services.windows_explorer.reveal_folder') as explorer:
            self.assertEqual(reveal({'buildId': result['buildId']}), (200, {'opened': True}))
            explorer.assert_called_once_with(Path(result['runtimePath']).parent)
            for invalid in ({}, {'buildId': '../outside'}, {'buildId': str(self.root)},
                            {'buildId': 'runtime_20000101T000000_deadbeef'},
                            {'buildId': result['buildId'], 'path': str(self.root)}):
                self.assertEqual(reveal(invalid)[0], 400)
            Path(result['reportPath']).unlink()
            self.assertEqual(reveal({'buildId': result['buildId']})[0], 400)
            self.assertEqual(explorer.call_count, 1)

    def test_reveal_refuses_redirected_folder(self):
        folder = self.builder.destination / 'runtime_20261122T025510_1d8c6a6d'
        folder.parent.mkdir(parents=True)
        outside = self.root / 'outside'
        outside.mkdir()
        try:
            folder.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('Directory symlink unavailable')
        with self.assertRaisesRegex(ValueError, 'redirected'):
            self.builder.completed_build_folder(folder.name)

    def test_legacy_mesh_id_and_mesh_id_caps_remain_supported(self):
        for legacy in ('MeshId', 'MeshID'):
            with self.subTest(legacy=legacy):
                tree = ET.parse(self.source)
                mesh = next(x for x in tree.iter('Item') if x.get('class') == 'MeshPart')
                content = next(x for x in mesh.findall('./Properties/Content')
                               if x.get('name') == 'MeshContent')
                content.set('name', legacy)
                content.find('uri').tag = 'url'
                tree.write(self.source, encoding='utf-8', xml_declaration=True)
                self.assertEqual(self.builder.inspect(self.rows)['eligible'], 2)
                # Return to modern serialization for the next subtest.
                content.set('name', 'MeshContent')
                content.find('url').tag = 'uri'
                tree.write(self.source, encoding='utf-8', xml_declaration=True)

    def test_mixed_legacy_and_new_properties_must_agree(self):
        tree = ET.parse(self.source)
        mesh = next(x for x in tree.iter('Item') if x.get('class') == 'MeshPart')
        props = mesh.find('Properties')
        legacy = ET.SubElement(props, 'Content', name='MeshId')
        ET.SubElement(legacy, 'url').text = 'rbxassetid://700'
        tree.write(self.source, encoding='utf-8', xml_declaration=True)
        self.assertEqual(self.builder.inspect(self.rows)['eligible'], 2)
        legacy.find('url').text = 'rbxassetid://701'
        tree.write(self.source, encoding='utf-8', xml_declaration=True)
        with self.assertRaisesRegex(ValueError, 'conflicting MeshContent/MeshId'):
            self.builder.inspect(self.rows)

    def test_new_content_null_object_and_unparseable_uri_fail_closed(self):
        original = self.source.read_bytes()
        for source_tag, value in (('null', None), ('object', 'RBX_OTH'),
                                  ('uri', 'rbxasset://unverified/mesh'),
                                  ('uri', 'rbxassetid://700_other')):
            with self.subTest(source_tag=source_tag, value=value):
                tree = ET.parse(self.source)
                mesh = next(x for x in tree.iter('Item') if x.get('class') == 'MeshPart')
                prop = next(x for x in mesh.findall('./Properties/Content')
                            if x.get('name') == 'MeshContent')
                prop.clear()
                prop.set('name', 'MeshContent')
                ET.SubElement(prop, source_tag).text = value
                tree.write(self.source, encoding='utf-8', xml_declaration=True)
                with self.assertRaisesRegex(ValueError, 'unsupported'):
                    self.builder.inspect(self.rows)
                # Recreate the valid fixture before the next case.
                self.source.write_bytes(original)

    def test_mesh_id_real_roblox_asset_delivery_uri(self):
        tree = ET.parse(self.source)
        mesh = next(x for x in tree.iter('Item') if x.get('class') == 'MeshPart')
        prop = next(x for x in mesh.findall('./Properties/Content') if x.get('name') == 'MeshContent')
        prop.find('uri').text = 'https://www.roblox.com/asset/?id=700'
        tree.write(self.source, encoding='utf-8', xml_declaration=True)
        self.assertEqual(self.builder.inspect(self.rows)['eligible'], 2)

    def test_compiled_runtime_marker_is_exact_and_can_be_read_by_client(self):
        inspected=self.builder.inspect(self.rows)
        result=self.builder.prepare(self.rows,expected_sha=inspected['sourceSha256'],snapshot_id=133,catalog_digest='digest')
        tree=ET.parse(result['runtimePath'])
        marker=next(node for node in tree.iter('Item') if node.get('class')=='StringValue')
        self.assertTrue(any(node.text == 'Game1LocationRuntimeManifest'
                            for node in marker.findall('./Properties/string')))
        value=next(node.text for node in marker.findall('./Properties/string')
                   if node.get('name')=='Value')
        payload=json.loads(value)
        self.assertEqual(payload['kind'],'game1-location-visual-stream-v1')
        self.assertFalse(payload['publishAllowed'])
        self.assertEqual(payload['targets'],['stone_fence_02','stone_pillar_03'])
        self.assertEqual(len(payload['placements']),2)
        self.assertEqual(payload['placements'][0]['pivot'],sample_cframe(1))
        self.assertEqual(payload['placements'][1]['size'],[4,5,6])
        self.assertNotIn('hierarchy',payload['placements'][0])

    def test_missing_model_pivot_or_reused_runtime_marker_refuses_preflight(self):
        import copy
        changed=copy.deepcopy(self.rows)
        del changed[0]['pivotEvidence']
        with self.assertRaisesRegex(ValueError,'no verified Model pivot'):
            self.builder.inspect(changed)
        root=ET.parse(self.source)
        rs=next(node for node in root.iter('Item') if node.get('class')=='ReplicatedStorage')
        marker=ET.SubElement(rs,'Item',{'class':'StringValue','referent':'RBX_MARKER'})
        ET.SubElement(ET.SubElement(marker,'Properties'),'string',name='Name').text='Game1LocationRuntimeManifest'
        root.write(self.source,encoding='utf-8',xml_declaration=True)
        with self.assertRaisesRegex(ValueError,'already contains a Runtime marker'):
            self.builder.inspect(self.rows)

    def test_changed_source_invalidates_approved_preflight_and_preserves_original(self):
        sha=self.builder.inspect(self.rows)['sourceSha256']
        self.source.write_bytes(self.source.read_bytes().replace(b'RBX_MESH_0',b'RBX_MESH_x'))
        with self.assertRaisesRegex(ValueError,'changed since Preflight'):
            self.builder.prepare(self.rows,expected_sha=sha,snapshot_id=133,catalog_digest='digest')
        self.assertFalse(self.builder.destination.exists())

    def test_missing_or_changed_placement_fails_closed(self):
        for mutate in (lambda rows: rows[0].update(path='Workspace.Fences.NotThere'),
                       lambda rows: rows[0].update(meshId='111'),
                       lambda rows: rows[0].update(placementId=''),
                       lambda rows: rows[0]['hierarchy'][1].update(size=[9,9,9])):
            import copy
            changed=copy.deepcopy(self.rows)
            mutate(changed)
            with self.assertRaises(ValueError):
                self.builder.inspect(changed)

    def test_owned_primary_part_to_visual_is_cleared_only_in_runtime(self):
        tree = ET.parse(self.source)
        models = [node for node in tree.iter('Item') if node.get('class') == 'Model'
                  and any(child.get('class') == 'MeshPart' for child in node if child.tag == 'Item')]
        self.assertEqual(len(models), 2)
        ET.SubElement(models[0].find('Properties'), 'Ref', name='PrimaryPart').text = 'RBX_MESH_0'
        # A valid PrimaryPart pointing at a RETAINED collision stays untouched.
        ET.SubElement(models[1].find('Properties'), 'Ref', name='PrimaryPart').text = 'RBX_COLL_1'
        tree.write(self.source, encoding='utf-8', xml_declaration=True)
        before = self.source.read_bytes()
        inspected = self.builder.inspect(self.rows)
        self.assertEqual(inspected['eligible'], 2)
        # Preflight is read-only, and the builder never modifies its input.
        self.assertEqual(self.source.read_bytes(), before)
        result = self.builder.prepare(self.rows, expected_sha=inspected['sourceSha256'],
                                      snapshot_id=133, catalog_digest='digest')
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(Path(result['backupPath']).read_bytes(), before)
        runtime = ET.parse(result['runtimePath'])
        runtime_models = [node for node in runtime.iter('Item') if node.get('class') == 'Model'
                          and node.get('referent') in ('RBX_MODEL_0', 'RBX_MODEL_1')]
        self.assertEqual(len(runtime_models), 2)
        actual = {node.get('referent'): node.find('./Properties/Ref[@name="PrimaryPart"]').text
                  for node in runtime_models}
        self.assertEqual(actual, {'RBX_MODEL_0': 'null', 'RBX_MODEL_1': 'RBX_COLL_1'})
        self.assertEqual(len([n for n in runtime.iter('Item') if n.get('class') == 'Part']), 2)
        self.assertEqual(len([n for n in runtime.iter('Item') if n.get('class') == 'MeshPart']), 0)
        manifest = json.loads(Path(result['manifestPath']).read_text(encoding='utf-8'))
        self.assertEqual(manifest['placements'][0]['pivotEvidence']['modelPivot'], sample_cframe(1))

    def test_other_model_primary_part_cannot_reference_removed_visual(self):
        tree = ET.parse(self.source)
        foreign = next(x for x in tree.iter('Item')
                       if any(e.text == 'UnmanagedPackage' for e in x.findall('./Properties/string')))
        ET.SubElement(foreign.find('Properties'), 'Ref', name='PrimaryPart').text = 'RBX_MESH_0'
        tree.write(self.source, encoding='utf-8', xml_declaration=True)
        with self.assertRaisesRegex(ValueError, r'external reference from Model UnmanagedPackage.PrimaryPart'):
            self.builder.inspect(self.rows)

    def test_cross_placement_primary_part_is_not_silently_cleared(self):
        tree = ET.parse(self.source)
        first = next(n for n in tree.iter('Item') if n.get('referent') == 'RBX_MODEL_0')
        ET.SubElement(first.find('Properties'), 'Ref', name='PrimaryPart').text = 'RBX_MESH_1'
        tree.write(self.source, encoding='utf-8', xml_declaration=True)
        with self.assertRaisesRegex(ValueError, 'external reference from Model'):
            self.builder.inspect(self.rows)

    def test_unrelated_ref_on_selected_model_must_still_block(self):
        tree = ET.parse(self.source)
        first = next(n for n in tree.iter('Item') if n.get('referent') == 'RBX_MODEL_0')
        ET.SubElement(first.find('Properties'), 'Ref', name='SomeGameplayLink').text = 'RBX_MESH_0'
        tree.write(self.source, encoding='utf-8', xml_declaration=True)
        with self.assertRaisesRegex(ValueError, 'external reference from Model'):
            self.builder.inspect(self.rows)

    def test_external_reference_to_visual_blocks_removal(self):
        tree=ET.parse(self.source)
        foreign=next(x for x in tree.iter('Item') if any(e.text=='UnmanagedPackage' for e in x.findall('./Properties/string')))
        ET.SubElement(foreign.find('Properties'),'Ref',name='Target').text='RBX_MESH_0'
        tree.write(self.source,encoding='utf-8',xml_declaration=True)
        with self.assertRaisesRegex(ValueError,'external reference'):
            self.builder.inspect(self.rows)

    def test_xml_source_only_no_in_place_mutation_or_symlink(self):
        self.source.unlink()
        try:
            self.source.symlink_to(self.root/'not_a_place.rbxlx')
        except (OSError, NotImplementedError):
            self.skipTest('Creating symlinks requires Developer Mode or administrator privileges on Windows')
        with self.assertRaises((ValueError,FileNotFoundError)):
            self.builder.inspect(self.rows)


if __name__=='__main__': unittest.main()

class RuntimeBuildRouteTests(unittest.TestCase):
    def setUp(self):
        import unittest.mock
        from services.location_lod_manager import LocationLodManager
        from services.place_registry.revisions import PlaceRevisionStore
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source,self.rows=fixture(self.root)
        self.revisions=PlaceRevisionStore(self.root)
        report={'schemaVersion':1,'placeId':0,'placements':self.rows,'protected':[], 'warnings':[]}
        self.revisions.add(report,'test-digest')
        class Assets:
            def snapshot(self):
                return {'items':[{'slug':s,'category':'fence','status':'PUBLISHED','model_asset_id':str(i),
                        'lod1':{'status':'PUBLISHED','modelAssetId':str(i+100)}}
                        for i,s in enumerate(('stone_fence_02','stone_pillar_03'),1)]}
        class Registry:
            def __init__(self,revisions):
                self.revisions=revisions
                self.studio_mutation_counter=0
        self.registry=Registry(self.revisions)
        self.manager=LocationLodManager(Assets(),self.registry)
        self.catalog=unittest.mock.patch('services.location_lod_manager.build_catalog',
                     return_value={'digest':'test-digest','items':[{'slug':'stone_fence_02'},{'slug':'stone_pillar_03'}]})
        self.catalog.start()
        self.addCleanup(self.catalog.stop)

    def test_200_preflight_and_single_use_prepare_from_same_session(self):
        from api.write_world import route
        import time
        self.manager._verified=(1,time.time(),0)
        status,plan=route('/api/lod-manager/preflight',lambda:{},{'lod_manager':self.manager})
        self.assertEqual(status,200,plan)
        self.assertEqual(plan['eligible'],2)
        status,result=route('/api/lod-manager/prepare',lambda:{'token':plan['token']},
                            {'lod_manager':self.manager})
        self.assertEqual(status,200,result)
        self.assertTrue(Path(result['runtimePath']).exists())
        self.assertFalse(result['publishAllowed'])
        status,detail=route('/api/lod-manager/prepare',lambda:{'token':plan['token']},
                            {'lod_manager':self.manager})
        self.assertEqual(status,400)
        self.assertIn('expired',detail['error'])

    def test_missing_live_scan_and_invalid_token_payload_block_build(self):
        from api.write_world import route
        status,detail=route('/api/lod-manager/preflight',lambda:{},{'lod_manager':self.manager})
        self.assertEqual(status,400)
        self.assertIn('Scan Place again',detail['error'])
        self.manager._verified=(1,1.0,0)
        plan=self.manager.preflight({})
        with self.assertRaisesRegex(ValueError,'requires a preflight token'):
            self.manager.prepare({'token':plan['token'],'confirmation':'yes'})
        with self.assertRaisesRegex(ValueError,'requires a preflight token'):
            self.manager.prepare({})
        with self.assertRaisesRegex(ValueError,'Preflight expired'):
            self.manager.prepare({'token':'stale-token'})
        self.assertFalse(self.manager.builder.destination.exists())
