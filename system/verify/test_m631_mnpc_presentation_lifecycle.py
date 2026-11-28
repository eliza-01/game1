"""M631 presentation resource ownership; engine pose/physics still NOT_RUN."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT/path).read_text(encoding='utf-8')

class MnpcPresentationM631(unittest.TestCase):
    def test_equipment_context_without_rig_and_effective_mount_fallback(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua unavailable')
        source = read('src/server/npc/NpcEquipmentService.luau')
        source = re.sub(r': (?:Model|string|any)(?=[,)\n])', '', source)
        source = source.replace('if hand == "right" then "EquippedWeaponRight" else "EquippedWeaponLeft"',
                                '(hand == "right" and "EquippedWeaponRight" or "EquippedWeaponLeft")')
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp)/'equipment.lua'
            script.write_text(source, encoding='utf-8')
            subprocess.run([lua, str(ROOT/'system/verify/mnpc_equipment_context_m631.lua'), str(script)], check=True, timeout=15)

    def test_both_spawners_own_exact_rig_and_teardown_in_order(self):
        for path, unbind, entity in (
            ('monster/MonsterSpawnerService', 'MonsterAgentLifecycle.Unbind(model)', 'model'),
            ('npc/NpcSpawnerService', 'NpcCombatAIService.Unbind(entity)', 'entity'),
        ):
            source = read('src/server/'+path+'.luau')
            self.assertIn('visual, rigLease = MnpcLifecycle.AttachRig(', source)
            release = source.split('local function release',1)[1].split('\nlocal ',1)[0]
            normal = release.index(f'EntityHitboxService.Detach({entity})', release.index(unbind))
            self.assertLess(normal, release.index('entry.rigLease:Release()'))
            self.assertLess(release.index('entry.rigLease:Release()'), release.index(f'{entity}:Destroy()'))
            self.assertIn('externallyDestroying', release)
        rig = read('src/server/actor/MnpcVisualRig.luau')
        self.assertIn('table.insert(owned, child)', rig)
        self.assertIn('return visual, lease', rig)
        lease = read('src/server/actor/MnpcPresentationLifecycle.luau')
        self.assertLess(lease.index('collider.CanQuery = false'), lease.index('weld:Destroy()'))
        self.assertNotIn('GetDescendants(', lease)
        self.assertNotIn('Heartbeat', lease)

    def test_npc_context_precedes_clone_but_mount_validation_precedes_ai(self):
        spawn = read('src/server/npc/NpcSpawnerService.luau')
        parts = ['NpcEquipmentService.Resolve(slug)', 'MnpcLifecycle.AttachRig(',
                 'NpcEquipmentService.Equip(entity, slug, equipmentContext, rigLease)',
                 'NpcAnimationRigBinding.Align(', 'NpcCombatAIService.Bind(entity', 'pcall(NpcAnimationService.Create']
        positions = [spawn.index(token) for token in parts]
        self.assertEqual(positions, sorted(positions))
        equip = read('src/server/weapon/WeaponEquipService.luau')
        resolve = equip.split('function WeaponEquipService.ResolveVisual', 1)[1].split('function WeaponEquipService.EquipVisual', 1)[0]
        self.assertNotIn(':Clone(', resolve)
        self.assertNotIn('findCharacterBone(', resolve)
        self.assertIn('WeaponEquipService.ResolveVisual(slug)', equip.split('function WeaponEquipService.EquipVisual', 1)[1])

if __name__ == '__main__':
    unittest.main()
