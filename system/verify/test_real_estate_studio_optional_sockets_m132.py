"""M132 Studio-side contract guardrails for published Real Estate model assets.

These inspect source structure; full Roblox AssetService behavior still requires
Studio testing, because Python cannot execute Luau or fetch private Model assets.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGINS = ROOT / 'system/studio-plugin/modules'


class StudioRealEstateOptionalSocketsM132(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = (PLUGINS / 'StudioRealEstateRigValidation.luau').read_text(encoding='utf-8')
        cls.assembler = (PLUGINS / 'StudioRealEstateModel.luau').read_text(encoding='utf-8')
        cls.loader = (PLUGINS / 'StudioModelLoadCommands.luau').read_text(encoding='utf-8')

    def test_new_module_is_bundled_into_studio_plugin(self):
        import json
        project = json.loads((ROOT / 'system/studio-plugin/plugin.project.json').read_text(encoding='utf-8'))
        self.assertEqual(project['tree']['modules']['StudioRealEstateRigValidation']['$path'],
                         'modules/StudioRealEstateRigValidation.luau')
        installer = (ROOT / 'system/studio-plugin/install.ps1').read_text(encoding='utf-8')
        self.assertIn("'StudioRealEstateRigValidation',", installer)

    def test_validation_is_separate_from_template_assembly(self):
        self.assertIn('StudioRealEstateRigValidation.Verify(rig, part, manifests[part])', self.assembler)
        self.assertNotIn('authored socket ', self.assembler)
        self.assertIn('function Validation.FindMesh(', self.validator)

    def test_any_missing_authored_bone_blocks_sync(self):
        self.assertIn('if #missing > 0 then', self.validator)
        self.assertIn('published Model Asset lost authored Bones', self.validator)
        self.assertIn('socket.Parent ~= hinge', self.validator)
        self.assertNotIn('instance:IsA("Attachment")', self.validator)

    def test_no_synthetic_socket_or_bone_animation(self):
        self.assertNotIn('Instance.new("Attachment")', self.validator)
        self.assertNotIn('Instance.new("Bone")', self.validator)
        self.assertNotIn('hinge.Transform =', self.assembler)
        self.assertIn('assembly.WorldPivot = hinge.TransformedWorldCFrame', self.assembler)

    def test_sync_exposes_missing_socket_diagnostics(self):
        self.assertIn('Game1RealEstateSocketContractComplete', self.assembler)
        self.assertIn('Game1MissingRealEstateSockets', self.assembler)
        self.assertIn('socketContractComplete = #missingSockets == 0', self.assembler)
        self.assertIn('missingSockets = missingSockets, rigWarnings = rigWarnings', self.assembler)
        ui = (ROOT / 'system/control-center/static/real-estate.js').read_text(encoding='utf-8')
        self.assertIn('const missing=stats.missingSockets||[];', ui)
        self.assertIn('sockets missing', ui)

    def test_failed_sync_only_removes_new_empty_destination_folders(self):
        self.assertIn('local createdFolders: {Folder} = {}', self.loader)
        self.assertIn('table.insert(created, child)', self.loader)
        self.assertIn('if folder.Parent ~= nil and #folder:GetChildren() == 0 then', self.loader)
        self.assertIn('if not ok then', self.loader)
        self.assertIn('if importedSession and importedSession.Parent == nil then', self.loader)


if __name__ == '__main__':
    unittest.main()
