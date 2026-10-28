"""M136: installed Studio Bridge audit detects missing modules, tools, stale bundles."""
import importlib.util
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / 'system' / 'studio-plugin'
spec = importlib.util.spec_from_file_location('game1_studio_plugin_audit', PLUGIN / 'audit.py')
audit_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_mod)


def bundle(path, modules, main):
    root = ET.Element('roblox', {'version': '4'})
    for name in modules:
        item = ET.SubElement(root, 'Item', {'class': 'ModuleScript'})
        props = ET.SubElement(item, 'Properties')
        ET.SubElement(props, 'string', {'name': 'Name'}).text = name
        ET.SubElement(props, 'ProtectedString', {'name': 'Source'}).text = 'return {}'
    item = ET.SubElement(root, 'Item', {'class': 'Script'})
    props = ET.SubElement(item, 'Properties')
    ET.SubElement(props, 'string', {'name': 'Name'}).text = 'Main'
    ET.SubElement(props, 'ProtectedString', {'name': 'Source'}).text = main
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


class StudioBridgeAuditM136(unittest.TestCase):
    def test_current_source_contract_is_complete(self):
        report = audit_mod.audit(ROOT, None, None)
        self.assertEqual(report['status'], 'ok')
        relevant = {c['name']: c['status'] for c in report['checks']}
        for name in ['Toolbar: Plots', 'Toolbar: Markers', 'Toolbar: DecoManager',
                     'Command: Real Estate model sync', 'Command: Timeline editor']:
            self.assertEqual(relevant[name], 'OK')

    def test_installed_real_inventory_and_checksums(self):
        import json
        manifest = json.loads((PLUGIN / 'plugin.project.json').read_text(encoding='utf-8'))
        module_names = [name for name in manifest['tree']['modules'] if name != '$className']
        main = (PLUGIN / 'Game1Bridge.server.luau').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            plugins = folder / 'Plugins'
            plugins.mkdir()
            generated = folder / 'generated'
            generated.mkdir()
            installed = plugins / 'Game1Bridge.rbxmx'
            generated_bundle = generated / 'Game1Bridge.rbxmx'
            bundle(generated_bundle, module_names, main)
            shutil.copyfile(generated_bundle, installed)
            parsed = audit_mod.inspect_bundle(installed)
            self.assertEqual(parsed['status'], 'ok')
            self.assertTrue(parsed['main'])
            self.assertTrue(parsed['plots_button'])
            self.assertEqual(len(parsed['modules']), len(module_names))
            self.assertTrue(parsed['studio_entrypoint'])
            # Run the actual audit against source and a simulated installed bundle.
            report = audit_mod.audit(ROOT, installed, plugins,
                                     generated_override=generated_bundle)
            self.assertEqual(report['status'], 'ok')
            checks = {c['name']: c for c in report['checks']}
            self.assertEqual(checks['Installed module inventory']['status'], 'OK')
            self.assertEqual(checks['Generated / installed SHA256']['status'], 'OK')

            # Same module inventory, but changed bytes: checksum must fail.
            bundle(installed, module_names, main + '\n-- modified install')
            report = audit_mod.audit(ROOT, installed, plugins,
                                     generated_override=generated_bundle)
            checks = {c['name']: c for c in report['checks']}
            self.assertEqual(report['status'], 'failed')
            self.assertEqual(checks['Installed module inventory']['status'], 'OK')
            self.assertEqual(checks['Generated / installed SHA256']['status'], 'FAIL')

            # Missing module must fail independently of the checksum.
            bundle(installed, [n for n in module_names if n != 'StudioPlotsVisibility'], main)
            report = audit_mod.audit(ROOT, installed, plugins,
                                     generated_override=generated_bundle)
            self.assertEqual(report['status'], 'failed')
            self.assertIn('StudioPlotsVisibility', next(c for c in report['checks'] if c['name'] == 'Installed module inventory')['detail'])

    def test_source_missing_manifest_file_is_error(self):
        from shutil import copytree
        import json
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dst = root / 'system' / 'studio-plugin'
            dst.mkdir(parents=True)
            (dst / 'modules').mkdir()
            project = {'tree': {'Main': {'$path': 'Main.luau'},
                                'modules': {'$className': 'Folder',
                                            'StudioPlotsVisibility': {'$path': 'modules/StudioPlotsVisibility.luau'}}}}
            (dst / 'plugin.project.json').write_text(json.dumps(project), encoding='utf8')
            (dst / 'Main.luau').write_text('local toolbar = plugin:CreateToolbar("game1")', encoding='utf8')
            report = audit_mod.audit(root, None, None)
            self.assertEqual(report['status'], 'failed')
            self.assertIn('StudioPlotsVisibility', next(c for c in report['checks'] if c['name'] == 'Rojo source inventory')['detail'])

    def test_installer_checks_all_modules_and_plots_marker(self):
        install = (PLUGIN / 'install.ps1').read_text(encoding='utf-8')
        self.assertIn('Get-Content (Join-Path $PSScriptRoot', install)
        self.assertIn('$DeclaredNames', install)
        self.assertIn('notin $DeclaredNames', install)
        self.assertIn("'Game1Plots'", install)
        self.assertIn('SelectNodes(', install)
        self.assertIn('$PackagedNames', install)
        preview = (PLUGIN / 'modules' / 'StudioPlotsVisibility.luau').read_text(encoding='utf-8')
        self.assertIn('[game1][plots] toolbar ready', preview)


if __name__ == '__main__':
    unittest.main()
