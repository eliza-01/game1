from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding='utf-8')

class CombatSpatialIndex(unittest.TestCase):
    def test_reference_and_lifecycle(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Lua CLI unavailable')
        subprocess.run([lua, 'system/verify/spatial_index_m614.lua'], cwd=ROOT, check=True, timeout=15)

    def test_all_queries_use_index_and_retain_narrow_phase(self):
        src = read('src/server/combat/EntityHitboxService.luau')
        for token in ('index:QueryBox(boxCFrame, boxSize)', 'index:QueryRadius(origin, reach)',
                      'index:QueryRay(rayOrigin, direction, distanceLimit)',
                      'index:Register(entity, root, definition.broadRadius, binding)', 'index:Remove(entity)',
                      'HitboxSpatialQueries.BoxContact(', 'HitboxSpatialQueries.AimContact(',
                      'delta:Dot(delta) <= broadReach * broadReach', 'geometry.Contact(',
                      'hit.distance < bestDistance', 'entity:GetAttribute("Damageable") == true'):
            self.assertIn(token, src)
        self.assertNotIn('pairs(bindings)', src)
        self.assertEqual(src.count('RunService.Heartbeat:Connect'), 1)

    def test_producers_and_native_contract(self):
        for paths in (('character/CharacterRigService',), ('actor/MnpcNavigationShell', 'actor/MnpcVisualRig')):
            src = '\n'.join(read('src/server/' + path + '.luau') for path in paths)
            self.assertIn('CanQuery = true', src)
            self.assertIn('"RootCollider"', src)
        src = read('src/shared/world/NativePartSpatialIndex.luau')
        self.assertIn('GetPartBoundsInBox', src)
        self.assertIn('params.MaxParts = 0', src)
        self.assertNotIn('Instance.new', src)
        self.assertNotIn('Heartbeat', src)
