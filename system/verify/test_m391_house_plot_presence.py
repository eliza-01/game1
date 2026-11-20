"""M391: Plot pivot registrations are spawn slots, not currently placed houses."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system' / 'control-center'))
from services.house_runtime_compilation import build_inputs, inspect, payload
from services.location_runtime_build import RuntimePlaceBuilder
from test_m388_house_runtime_integration import build_source, selected, FRAME

AXES = ('X', 'Y', 'Z', 'R00', 'R01', 'R02', 'R10', 'R11', 'R12', 'R20', 'R21', 'R22')


def source_with_model_pivot(path, *, scale=1.0):
    build_source(path)
    tree = ET.parse(path)
    house = next(n for n in tree.iter('Item')
                 if n.get('class') == 'Model'
                 and n.findtext('./Properties/string[@name="Name"]') == 'house_level5_01')
    props = house.find('Properties')
    pivot = props.find('./OptionalCoordinateFrame[@name="WorldPivotData"]')
    if pivot is None:
        pivot = ET.SubElement(props, 'OptionalCoordinateFrame', name='WorldPivotData')
    frame = pivot.find('CFrame')
    if frame is None:
        frame = ET.SubElement(pivot, 'CFrame')
    for key, number in zip(AXES, FRAME):
        existing = frame.find(key)
        (existing if existing is not None else ET.SubElement(frame, key)).text = str(number)
    model_scale = props.find('./float[@name="ScaleFactor"]')
    (model_scale if model_scale is not None else ET.SubElement(props, 'float', name='ScaleFactor')).text = str(scale)
    tree.write(path, encoding='utf-8', xml_declaration=True)
    return tree


def plot(slug, index):
    return {'houseSlug': slug, 'plotIndex': index,
            'worldCFrame': FRAME[:], 'scale': 1.0}


def selection(*, count_level5=0, count_level1=40):
    base = selected()['house_level5_01']
    empty = copy.deepcopy(base)
    empty['house']['slug'] = 'house_level1_01'
    empty['house']['status'] = 'NOT_PUBLISHED'  # Not in saved XML: no blocker.
    empty['house']['lod1'] = {'status': 'NOT_PUBLISHED', 'modelAssetId': ''}
    empty['profile'] = {'mode': 'full', 'lod1': 150, 'hide': 400, 'hysteresis': 10}
    empty['placements'] = [plot('house_level1_01', n) for n in range(1, count_level1 + 1)]
    base['placements'] = [plot('house_level5_01', n) for n in range(1, count_level5 + 1)]
    return {'house_level1_01': empty, 'house_level5_01': base}


class Store:
    def __init__(self, rows): self.rows = rows
    def list(self): return [{**value['house'], 'runtimeProfile': value['profile']} for value in self.rows.values()]


class Bindings:
    def __init__(self, rows): self.rows = rows
    def snapshot(self):
        return {'items': [p for value in self.rows.values() for p in value['placements']]}


class OptionalPlotHouseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'place' / 'game1_runtime_source.rbxlx'
        self.source.parent.mkdir(parents=True, exist_ok=True)
        source_with_model_pivot(self.source)

    def test_40_level1_slots_with_zero_level1_models_are_valid(self):
        rows = selection(count_level5=1, count_level1=40)
        selected_inputs = build_inputs(Store(rows), Bindings(rows))
        found = inspect(ET.parse(self.source), selected_inputs)
        self.assertEqual([(item['slug'], item['plotIndex']) for item in found], [('house_level5_01', 1)])
        manifest = payload(found, selected_inputs)
        self.assertEqual(set(manifest['types']), {'house_level5_01'})
        self.assertEqual(len(manifest['placements']), 1)
        compiler = RuntimePlaceBuilder(self.root)
        check = compiler.inspect([], house_inputs=selected_inputs)
        self.assertEqual(check['houseCount'], 1)
        self.assertEqual(check['houseMeshParts'], 2)
        built = compiler.prepare([], expected_sha=check['sourceSha256'],
            snapshot_id=391, catalog_digest='test', house_inputs=selected_inputs)
        self.assertEqual(built['housePlacements'], 1)
        marker = next(n for n in ET.parse(built['runtimePath']).iter('Item')
            if n.get('class') == 'StringValue' and n.findtext('./Properties/string[@name="Name"]')
                == 'Game1LocationRuntimeManifest')
        packaged = json.loads(marker.findtext('./Properties/string[@name="Value"]'))
        self.assertEqual(len(packaged['houses']['placements']), 1)

    def test_house_does_not_need_a_type_specific_plot_binding(self):
        rows = selection(count_level5=0, count_level1=40)
        found = inspect(ET.parse(self.source), build_inputs(Store(rows), Bindings(rows)))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['pivot'], FRAME)
        self.assertEqual(found[0]['scale'], 1.0)

    def test_saved_model_scale_is_authoritative(self):
        source_with_model_pivot(self.source, scale=1.25)
        rows = selection(count_level5=20, count_level1=40)
        found = inspect(ET.parse(self.source), build_inputs(Store(rows), Bindings(rows)))
        self.assertEqual(found[0]['scale'], 1.25)

    def test_pivot_invalidity_and_duplicate_model_still_block(self):
        tree = ET.parse(self.source)
        rows = selection(count_level5=39)
        inputs = build_inputs(Store(rows), Bindings(rows))
        house = next(n for n in tree.iter('Item') if n.get('class') == 'Model'
            and n.findtext('./Properties/string[@name="Name"]') == 'house_level5_01')
        duplicate = copy.deepcopy(house)
        for n in tree.iter('Item'):
            if n.get('class') == 'Folder' and n.findtext('./Properties/string[@name="Name"]') == 'Houses':
                n.append(duplicate)
                break
        with self.assertRaisesRegex(ValueError, 'duplicate authored Model'):
            inspect(tree, inputs)
        clean_tree = ET.parse(self.source)
        clean_house = next(n for n in clean_tree.iter('Item') if n.get('referent') == 'RBX_HOUSE')
        frame = clean_house.find('./Properties/OptionalCoordinateFrame[@name="WorldPivotData"]/CFrame')
        frame.find('X').text = 'not-a-number'
        with self.assertRaisesRegex(ValueError, 'invalid serialized house WorldPivotData'):
            inspect(clean_tree, inputs)

    def test_many_registered_future_slots_do_not_exhaust_visual_instance_budget(self):
        rows = {}
        for level in range(1, 13):
            item = copy.deepcopy(selection(count_level5=0, count_level1=0)['house_level1_01'])
            slug = f'house_level{level}_01'
            item['house']['slug'] = slug
            if level == 5: item['house']['status'] = 'PUBLISHED'
            item['profile'] = {'mode':'full', 'lod1':150, 'hide':400, 'hysteresis':10}
            item['placements'] = [plot(slug, index) for index in range(1, 51)]
            rows[slug] = item
        inputs = build_inputs(Store(rows), Bindings(rows))
        self.assertEqual(sum(len(v['placements']) for v in inputs.values()), 600)
        # Only the one actual model counts against MAX_HOUSES, not the 600
        # saved candidate spawn pivots.
        self.assertEqual(len(inspect(ET.parse(self.source), inputs)), 1)

    def test_unplaced_house_types_are_optional_and_no_runtime_geometry_is_invented(self):
        rows = selection(count_level5=0, count_level1=40)
        selected_inputs = build_inputs(Store(rows), Bindings(rows))
        tree = ET.parse(self.source)
        house = next(n for n in tree.iter('Item') if n.get('class') == 'Model'
            and n.findtext('./Properties/string[@name="Name"]') == 'house_level5_01')
        for node in tree.iter('Item'):
            if house in list(node):
                node.remove(house)
                break
        found = inspect(tree, selected_inputs)
        self.assertEqual(found, [])
        self.assertEqual(payload(found, selected_inputs), {'types': {}, 'placements': []})


if __name__ == '__main__': unittest.main()
