"""M275: normalized skinned FBX must reach the registration confirmation UI."""
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('node'), 'Node.js required for browser approval flow')
class CharacterInspectApprovalM275(unittest.TestCase):
    def test_normalized_skin_weights_still_open_confirmation_and_register(self):
        result = subprocess.run(
            [
                shutil.which('node'),
                str(ROOT / 'system/verify/character_add_new_without_replace_m197.js'),
                str(ROOT / 'system/control-center/static/character-components.js'),
                str(ROOT / 'system/control-center/static/character-atlas-presentation.js'),
                '--normalized',
            ],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('selection and register passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
