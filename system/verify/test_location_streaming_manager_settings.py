"""M355: configuration, Workspace XML, Wedge and visual-only Runtime safeguards."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import sys
import tempfile
from xml.etree import ElementTree as ET
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from services.location_streaming_config import LocationStreamingConfig, DEFAULT_SETTINGS
from services.location_runtime_build import RuntimePlaceBuilder, _runtime_payload, placement_shape_problem
from test_location_runtime_build import fixture


class StreamingManagerSettingsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source, self.rows = fixture(self.root)
        self.builder = RuntimePlaceBuilder(self.root)
        self.config = LocationStreamingConfig(self.root)

    def test_defaults_selected_only_pilot_until_user_changes(self):
        config = self.config.read()
        self.assertEqual(config['modes'], {'stone_fence_02':'lod1', 'stone_pillar_03':'lod1'})
        self.assertEqual(config['workspace']['targetRadius'], 1024)
        self.assertEqual(config['distances'], {'lod1':120,'lod2':260,'hide':400,'hysteresis':12})

    def test_persistent_modes_validate_and_atomic_update(self):
        self.config.save({'modes':{'stone_pillar_03':'full','stone_fence_02':'off'}}, ['stone_fence_02','stone_pillar_03'])
        self.assertEqual(self.config.read()['modes']['stone_pillar_03'], 'full')
        self.assertEqual(self.config.read()['modes']['stone_fence_02'], 'off')
        current=self.config.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            self.config.save({'modes':{'nonregistered':'lod2'}},['stone_fence_02'])
        with self.assertRaisesRegex(ValueError, 'hysteresis'):
            self.config.save({'distances':{'lod1':20,'lod2':21,'hide':22,'hysteresis':12}}, ['stone_fence_02'])
        self.assertEqual(self.config.path.read_bytes(), current)

    def test_workspace_is_changed_only_in_runtime_copy(self):
        settings=copy.deepcopy(DEFAULT_SETTINGS)
        settings['modes']['stone_fence_02']='off'
        settings['modes']['stone_pillar_03']='full'
        settings['workspace']['targetRadius']=700
        settings['distances']={'lod1':100,'lod2':240,'hide':480,'hysteresis':10}
        rows=self.rows[1:]
        before=self.source.read_bytes()
        inspected=self.builder.inspect(rows, settings)
        result=self.builder.prepare(rows, expected_sha=inspected['sourceSha256'], snapshot_id=146, catalog_digest='test', settings=settings)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(Path(result['backupPath']).read_bytes(), before)
        place=ET.parse(result['runtimePath'])
        workspace=next(node for node in place.iter('Item') if node.get('class')=='Workspace')
        props={c.get('name'):c for c in workspace.findall('./Properties/*')}
        self.assertEqual(props['StreamingTargetRadius'].text,'700')
        self.assertEqual(props['StreamingMinRadius'].text,'64')
        self.assertEqual(props['ModelStreamingBehavior'].text,'2')
        self.assertEqual(props['StreamingIntegrityMode'].text,'3')
        self.assertEqual(props['StreamOutBehavior'].text,'2')
        self.assertEqual(props['StreamingEnabled'].text,'true')
        marker=next(n for n in place.iter('Item') if n.get('class')=='StringValue')
        payload=json.loads(next(p.text for p in marker.findall('./Properties/string') if p.get('name')=='Value'))
        self.assertEqual(payload['schemaVersion'],2)
        self.assertEqual(payload['modes'],{'stone_pillar_03':'full'})
        self.assertEqual(payload['distances']['hide'],480)
        self.assertEqual(len(payload['placements']),1)
        self.assertEqual([n.get('class') for n in place.iter('Item')].count('MeshPart'),1)

    def test_three_selected_asset_types_no_hardcoded_pilot_filter(self):
        tree=ET.parse(self.source)
        original=next(n for n in tree.iter('Item') if n.get('referent')=='RBX_MODEL_0')
        folder=next(n for n in tree.iter('Item') if n.get('class')=='Folder')
        third=copy.deepcopy(original)
        third.set('referent','RBX_MODEL_THIRD')
        next(p for p in third.findall('./Properties/string') if p.get('name')=='Name').text='wooden_fence_03__fake'
        for child in third.iter('Item'):
            if child is not third:child.set('referent','RBX_Third_'+child.get('referent',''))
        folder.append(third)
        tree.write(self.source,encoding='utf-8',xml_declaration=True)
        row=copy.deepcopy(self.rows[0])
        row.update(slug='wooden_fence_03',path='Workspace.Fences.wooden_fence_03__fake',placementId='uuid-third')
        settings=copy.deepcopy(DEFAULT_SETTINGS)
        settings['modes']['wooden_fence_03']='full'
        rows=self.rows+[row]
        check=self.builder.inspect(rows,settings)
        self.assertEqual(check['eligible'],3)
        outcome=self.builder.prepare(rows,expected_sha=check['sourceSha256'],snapshot_id=146,catalog_digest='test',settings=settings)
        manifest=json.loads(Path(outcome['manifestPath']).read_text())
        self.assertEqual(set(manifest['targets']), {'stone_fence_02','stone_pillar_03','wooden_fence_03'})
        self.assertEqual(manifest['modes']['wooden_fence_03'],'full')
        self.assertEqual(manifest['removedVisualMeshParts'],3)

    def test_wedge_collision_is_retained(self):
        tree=ET.parse(self.source)
        collider=next(n for n in tree.iter('Item') if n.get('class')=='Part')
        collider.set('class','WedgePart')
        tree.write(self.source,encoding='utf-8',xml_declaration=True)
        self.rows[0]['hierarchy'][-1]['class']='WedgePart'
        inspect=self.builder.inspect(self.rows)
        result=self.builder.prepare(self.rows,expected_sha=inspect['sourceSha256'],snapshot_id=146,catalog_digest='test')
        runtime=ET.parse(result['runtimePath'])
        self.assertEqual([n.get('class') for n in runtime.iter('Item')].count('WedgePart'),1)
        self.assertEqual([n.get('class') for n in runtime.iter('Item')].count('Part'),1)

    def test_no_colliders_only_when_visual_has_no_physics(self):
        tree=ET.parse(self.source)
        model=next(node for node in tree.iter('Item') if node.get('class')=='Model' and node.get('referent')=='RBX_MODEL_0')
        collider=next(n for n in model if n.tag=='Item' and n.get('class')=='Part')
        model.remove(collider)
        mesh=next(n for n in model if n.tag=='Item' and n.get('class')=='MeshPart')
        props=mesh.find('Properties')
        ET.SubElement(props,'bool',name='CanCollide').text='false'
        ET.SubElement(props,'bool',name='CanQuery').text='false'
        tree.write(self.source,encoding='utf-8',xml_declaration=True)
        row=copy.deepcopy(self.rows[0])
        row['hierarchy']=[n for n in row['hierarchy'] if n.get('class')!='Part']
        visual=next(n for n in row['hierarchy'] if n.get('class')=='MeshPart')
        visual['canCollide']=False
        visual['canQuery']=False
        self.assertFalse(placement_shape_problem(row))
        inspect=self.builder.inspect([row])
        result=self.builder.prepare([row],expected_sha=inspect['sourceSha256'],snapshot_id=146,catalog_digest='test')
        runtime=ET.parse(result['runtimePath'])
        model=next(n for n in runtime.iter('Item') if n.get('referent')=='RBX_MODEL_0')
        self.assertEqual([n for n in model if n.tag=='Item'],[])
        row['hierarchy'][1]['canCollide']=True
        self.assertIn('collidable',placement_shape_problem(row))

    def test_surface_appearance_child_removed_with_visual(self):
        tree=ET.parse(self.source)
        mesh=next(node for node in tree.iter('Item') if node.get('class')=='MeshPart')
        appearance=ET.SubElement(mesh,'Item',{'class':'SurfaceAppearance','referent':'RBX_SURFACE'})
        ET.SubElement(ET.SubElement(appearance,'Properties'),'string',name='Name').text='SurfaceAppearance'
        tree.write(self.source,encoding='utf-8',xml_declaration=True)
        row=copy.deepcopy(self.rows[0]);row['hierarchy'].append({'class':'SurfaceAppearance','name':'SurfaceAppearance'})
        self.assertFalse(placement_shape_problem(row))
        inspection=self.builder.inspect([row])
        result=self.builder.prepare([row], expected_sha=inspection['sourceSha256'],snapshot_id=146,catalog_digest='test')
        tree=ET.parse(result['runtimePath'])
        self.assertFalse(any(n.get('referent')=='RBX_SURFACE' for n in tree.iter('Item')))

    def test_reject_rig_and_unsupported_attachment(self):
        row=copy.deepcopy(self.rows[0]);row['hierarchy'].append({'class':'Bone','name':'Socket'})
        self.assertIn('rig',placement_shape_problem(row))
        row['hierarchy'].append({'class':'MeshPart','name':'rig_carrier'})
        self.assertIn('exactly one',placement_shape_problem(row))

if __name__ == '__main__':unittest.main()
