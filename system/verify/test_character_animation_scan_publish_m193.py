"""M193: Character Animations scan review must unlock explicit registration/publication."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'system/control-center/static'


@unittest.skipUnless(shutil.which('node'), 'Node.js required for Character Animation browser regression')
class CharacterAnimationScanPublishM193(unittest.TestCase):
    def test_scan_review_and_register_publish_transitions(self):
        result = subprocess.run(
            [shutil.which('node'), str(ROOT / 'system/verify/character_animation_scan_publish_m193.js'),
             str(STATIC / 'character-animation-ui.js')],
            capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + '\n' + result.stderr)
        self.assertIn('stale character, registration and publish passed', result.stdout)

    def test_script_syntax_and_cache_version(self):
        result = subprocess.run(
            [shutil.which('node'), '--check', str(STATIC / 'character-animation-ui.js')],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('character-animation-ui.js?v=309', (STATIC / 'index.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
