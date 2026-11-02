"""M199 UI: safe default / deliberate cascading and shared module hookup."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]

class SharedAssetRetirementUiM199(unittest.TestCase):
    def test_single_shared_modal_loaded_before_both_sections(self):
        html=(ROOT/'system/control-center/static/index.html').read_text(encoding='utf-8')
        self.assertIn('shared-asset-retirement.css?v=2', html)
        self.assertLess(html.index('shared-asset-retirement.js?v=4'),html.index('deco-assets.js?v=8'))
        self.assertLess(html.index('shared-asset-retirement.js?v=4'),html.index('real-estate.js?v=23'))
        for name,kind in [('deco-assets.js','location'),('real-estate.js','estate')]:
            code=(ROOT/'system/control-center/static'/name).read_text(encoding='utf-8')
            self.assertIn("game1AssetRetirement.open({kind:'"+kind+"'",code)
            self.assertNotIn('delete '+kind+' from the game1 registry?',code)

    @unittest.skipUnless(shutil.which('node'),'Node.js required for DOM simulation')
    def test_default_preserve_and_explicit_cascade(self):
        p=subprocess.run([shutil.which('node'),
            str(ROOT/'system/verify/shared_asset_retirement_ui_m199.js'),
            str(ROOT/'system/control-center/static/shared-asset-retirement.js'),
            str(ROOT/'system/control-center/static/atlas-identity.js')],
            capture_output=True,text=True,timeout=15)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
