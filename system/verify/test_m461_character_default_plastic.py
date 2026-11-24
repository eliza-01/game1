"""M461: default Plastic applies to every visible Character Assembly slot.

An absent material override is a backwards-compatible preference, not a
reason to inherit a potentially inconsistent material from the published FBX.
"""
import ast
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from character_core.assemblies import CharacterAssemblies, DEFAULT_MATERIAL, MATERIALS, MATERIAL_SLOTS

ROOT = Path(__file__).resolve().parents[2]
ALL_SLOTS = ('upper', 'lower', 'gloves', 'boots', 'head', 'eye_l', 'eye_r',
             'eyebrow_l', 'eyebrow_r', 'hair')


class CharacterDefaultPlasticM461(unittest.TestCase):
    def resolver(self):
        """Exercise the real recipe resolver with stubbed external catalogs, no SQLite."""
        instance = object.__new__(CharacterAssemblies)
        instance.components = object()
        instance.armor = SimpleNamespace(resolve=lambda set_id, gender, rig_id: (
            {slot: ({'id': 'mesh_' + slot}, {'id': 'atlas_' + slot}, None)
             for slot in ALL_SLOTS[:4]}, []))
        instance._part = lambda slot, key, rig_id, gender, appearance_id=None: (
            dict(id=key, attachment='', attachment_mode='', used_bones=[], extras=[]), None)
        rig = dict(id='human', model_asset_id='12345', published_revision=1,
                   metadata_json=json.dumps({'bones': [{'name': 'root'}]}))
        return instance, rig

    @staticmethod
    def recipe(gender='male', materials=None):
        recipe = dict(schema_version=2, rig_id='human', gender=gender,
                      armor_set_id='starter', face_parts={
                          slot: {'meshPartId': 'mesh_' + slot}
                          for slot in ALL_SLOTS[4:]})
        if materials is not None:
            recipe['part_materials'] = materials
        return recipe

    def resolve(self, gender='male', materials=None):
        instance, rig = self.resolver()
        with patch('character_core.assemblies.published_rig', return_value=rig):
            return instance.resolve(self.recipe(gender, materials))

    def test_missing_overrides_default_to_plastic_for_all_slots_and_genders(self):
        for gender in ('male', 'female'):
            with self.subTest(gender=gender):
                result = self.resolve(gender)
                self.assertTrue(result['ready'], result['missing'])
                self.assertEqual(set(result['parts']), set(ALL_SLOTS))
                self.assertEqual({p['material'] for p in result['parts'].values()}, {'Plastic'})
                # Explicitly empty legacy v2 overrides behave identically.
                self.assertEqual(self.resolve(gender, {})['parts'], result['parts'])

    def test_existing_overrides_stay_authoritative_and_mixed_default_works(self):
        result = self.resolve('female', {'head': 'Metal', 'upper': 'SmoothPlastic',
                                         'hair': 'Glass'})
        self.assertTrue(result['ready'], result['missing'])
        self.assertEqual(result['parts']['head']['material'], 'Metal')
        self.assertEqual(result['parts']['upper']['material'], 'SmoothPlastic')
        self.assertEqual(result['parts']['hair']['material'], 'Glass')
        for slot in set(ALL_SLOTS) - {'head', 'upper', 'hair'}:
            self.assertEqual(result['parts'][slot]['material'], DEFAULT_MATERIAL)

    def test_plastic_allowed_and_unknown_material_fails_closed(self):
        self.assertIn('Plastic', MATERIALS)
        valid = self.resolve(materials={'head': 'Plastic'})
        self.assertTrue(valid['ready'])
        invalid = self.resolve(materials={'head': 'Unobtainium'})
        self.assertFalse(invalid['ready'])
        self.assertIn('invalid part material override', invalid['missing'])

    def test_ui_and_server_share_material_choices_and_default(self):
        source = (ROOT / 'system/control-center/static/character-assemblies.js').read_text(encoding='utf-8')
        match = re.search(r'const materials=(\[[^;]+\]);', source)
        self.assertIsNotNone(match)
        choices = ast.literal_eval(match.group(1))
        self.assertEqual(choices[0], DEFAULT_MATERIAL)
        self.assertEqual(set(choices), MATERIALS)
        self.assertEqual(len(choices), len(set(choices)))
        self.assertIn("const defaultMaterial='Plastic';", source)
        self.assertIn("byId('material-'+slot).value=saved?.[slot]||defaultMaterial;", source)
        self.assertEqual(set(MATERIAL_SLOTS), {
            'upper', 'lower', 'gloves', 'boots', 'head', 'eye_l', 'eye_r',
            'eyebrow_l', 'eyebrow_r', 'hair'})
        self.assertIn('character-assemblies.js?v=461',
                      (ROOT / 'system/control-center/static/index.html').read_text(encoding='utf-8'))

    def test_runtime_applies_resolved_material_to_mesh_and_hair_extras(self):
        source = (ROOT / 'src/server/character/CharacterAssemblyBuilder.luau').read_text(encoding='utf-8')
        self.assertIn('mesh.Material = selected', source)
        self.assertIn('visual.Material = selected', source)
        self.assertNotIn('mesh.PivotOffset =', source)


if __name__ == '__main__':
    unittest.main()
