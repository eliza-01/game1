"""Browser-side review of mixed new and already-published character FBX parts."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('node'), 'Node.js required for component modal flow')
class CharacterAddNewUiM197(unittest.TestCase):
    def test_inspection_modal_selects_new_hair_without_existing_replacements(self):
        result=subprocess.run([shutil.which('node'),
            str(ROOT/'system/verify/character_add_new_without_replace_m197.js'),
            str(ROOT/'system/control-center/static/character-components.js'),
            str(ROOT/'system/control-center/static/character-atlas-presentation.js')],
            capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('5 untouched replacements',result.stdout)
