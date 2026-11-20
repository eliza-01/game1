"""M388b: authored house pivot, explicit opt-in, and honest Runtime coverage."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'system/control-center'))
from services.location_runtime_build import RuntimePlaceBuilder
from services.house_runtime_compilation import inspect, payload, transform
from test_m388_house_runtime_integration import build_source, selected, item, FRAME


class HouseRuntimeScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=build_source(self.root/'place/game1_runtime_source.rbxlx')

    def test_real_model_world_pivot_is_not_rig_carrier_cframe(self):
        tree=ET.parse(self.source)
        house=next(n for n in tree.iter('Item') if n.get('class')=='Model' and
            n.find('./Properties/string[@name="Name"]') is not None and
            n.find('./Properties/string[@name="Name"]').text=='house_level5_01')
        frame=house.find('./Properties/OptionalCoordinateFrame[@name="WorldPivotData"]/CFrame')
        self.assertIsNotNone(frame)
        carrier=next(n for n in house.iter('Item') if n.find('./Properties/string[@name="Name"]') is not None and
            n.find('./Properties/string[@name="Name"]').text=='rig_carrier')
        cframe=carrier.find('./Properties/CoordinateFrame[@name="CFrame"]')
        cframe.find('X').text='12.75'
        cframe.find('Y').text='33.5'
        cframe.find('R01').text='-1'
        cframe.find('R10').text='1'
        cframe.find('R00').text='0'
        cframe.find('R11').text='0'
        inputs=selected()
        matches=inspect(tree, inputs)
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]['plotIndex'],1)
        self.assertEqual(matches[0]['pivot'],FRAME)
        self.assertEqual(len(matches[0]['parts']),2)
        frame.find('X').text='900'
        # The authored Model pivot, not a historical Plot registration,
        # determines where an already-placed Runtime house is rendered.
        moved=inspect(tree,inputs)
        self.assertEqual(moved[0]['pivot'][0],900.0)
        frame.find('X').text='10'
        self.assertEqual(transform(matches,inputs),2)
        self.assertEqual(carrier.get('class'),'MeshPart')
        self.assertEqual(next(n for n in house.iter('Item') if n.get('referent')=='RBX_GLASS').get('class'),'Part')

    def test_location_runtime_exposes_unselected_houses(self):
        from test_location_runtime_build import fixture
        other=self.root/'location_fixture'
        other.mkdir()
        source, rows = fixture(other)
        tree=ET.parse(source)
        workspace=next(n for n in tree.getroot() if n.get('class')=='Workspace')
        plots=item(workspace,'Plots','Folder','RBX_OTHER_PLOTS')
        plot=item(plots,'01','Folder','RBX_OTHER_PLOT')
        houses=item(plot,'Houses','Folder','RBX_OTHER_HOUSES')
        item(houses,'house_level5_01','Model','RBX_UNSELECTED_HOUSE')
        tree.write(source,encoding='utf-8',xml_declaration=True)
        builder=RuntimePlaceBuilder(other)
        plan=builder.inspect(rows)
        self.assertEqual(plan['untouchedHouseModels'],1)
        self.assertEqual(plan['untouchedHouseCounts'],{'house_level5_01':1})
        output=builder.prepare(rows,expected_sha=plan['sourceSha256'],snapshot_id=7,catalog_digest='test')
        report=json.loads(Path(output['reportPath']).read_text(encoding='utf-8'))
        self.assertEqual(report['untouchedHouseCounts'],{'house_level5_01':1})
        self.assertEqual(output['untouchedHouseCounts'],{'house_level5_01':1})

    def test_ui_houses_share_existing_real_estate_profile_endpoint(self):
        ui=(ROOT/'system/control-center/static/lod-manager.js').read_text(encoding='utf-8')
        manager=(ROOT/'system/control-center/services/location_lod_manager.py').read_text(encoding='utf-8')
        self.assertIn('lm-house-stream-mode',ui)
        self.assertIn('/runtime-profile',ui)
        self.assertIn('expectedRevision:old.revision',ui)
        self.assertIn('untouchedHouseCounts',ui)
        self.assertIn("'untouchedLocations':",manager)
        self.assertIn("'profile': {k:runtime.get(k)",manager)


if __name__=='__main__':unittest.main()
