"""M191: Character Shared Atlas dropdowns must recover after refresh and queue updates."""
from pathlib import Path
import shutil
import subprocess
from unittest import TestCase, skipUnless

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'system/control-center/static'


@skipUnless(shutil.which('node'), 'Node.js required for browser-side state-transition test')
class CharacterSharedAtlasUnlockM191(TestCase):
    def test_atlas_rebinding_unblocks_current_rows_without_page_reload(self):
        runner = ROOT / 'system/verify/character_atlas_unlock_m191.js'
        script = STATIC / 'character-components.js'
        result = subprocess.run(
            [shutil.which('node'), str(runner), str(script), str(STATIC / 'character-atlas-presentation.js')],
            text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('transitions passed', result.stdout)

    def test_browser_cache_buster_and_script_syntax(self):
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        self.assertIn('character-components.js?v=12', html)
        result = subprocess.run(
            [shutil.which('node'), '--check', str(STATIC / 'character-components.js')],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
