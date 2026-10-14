"""M77: NPC equipment-context compatibility and unarmed melee; no per-NPC hacks."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'control-center'))
from monster_store import MonsterStore
from monster_animation_store import MonsterAnimationStore
from npc_animation_taxonomy import WEAPON_SETS, EQUIPMENT_SETS, parse

ROOT = Path(__file__).resolve().parents[2]

class M77CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='game1-m77-')
        self.root = Path(self.temp.name)
        self.npcs = MonsterStore(self.root, kind='npc')
        with self.npcs.connect() as db:
            db.execute("""INSERT INTO monsters(slug,name_en,model_source_path,model_asset_id,
                model_sha256,model_published_sha256,created_at,updated_at,skeleton_signature)
                VALUES ('generic','Generic','assets/source/npcs/generic/model/generic.fbx','123','sha','sha',0,0,'sig')""")
        self.anim = MonsterAnimationStore(self.root, kind='npc')
        inbox = self.root / 'inbox'
        inbox.mkdir()
        for name in ('generic_base_idle_special_01.rbxm','generic_1hs_idle_special_01.rbxm',
                     'generic_unarmed_attack_01.rbxm','generic_base_death.rbxm'):
            (inbox / name).write_bytes(name.encode())
        self.anim.scan_folder('generic', str(inbox))

    def tearDown(self):
        self.temp.cleanup()

    def find(self, set_name, slot):
        return next(r for r in self.anim.snapshot('generic')['items']
                    if r['weaponSet'] == set_name and r['slot'] == slot)

    def test_defaults_and_explicit_empty_are_distinct(self):
        base = self.find('base','idle_special')
        one = self.find('1hs','idle_special')
        self.assertEqual(set(base['compatibleWith']), set(EQUIPMENT_SETS))
        self.assertEqual(one['compatibleWith'], ['1hs'])
        self.anim.set_compatibility(base['binding_id'], ['unarmed','1hs'])
        self.assertEqual(self.find('base','idle_special')['compatibleWith'], ['unarmed','1hs'])
        self.anim.set_compatibility(base['binding_id'], [])
        self.assertEqual(self.find('base','idle_special')['compatibleWith'], [])
        self.anim = MonsterAnimationStore(self.root, kind='npc')
        self.assertEqual(self.find('base','idle_special')['compatibleWith'], [])

    def test_atomic_options_and_validation(self):
        row = self.find('base','idle_special')
        binding = row['binding_id']
        self.anim.set_animation_options(binding,['1hs','unarmed'],75,False)
        updated = self.find('base','idle_special')
        self.assertEqual(updated['compatibleWith'], ['unarmed','1hs'])
        self.assertEqual(updated['weight'],75)
        self.assertFalse(updated['disarm'])
        for bad in (['base'],['1hs','1hs']):
            with self.assertRaises(ValueError):
                self.anim.set_animation_options(binding,bad,42,True)
        with self.assertRaises(ValueError):
            self.anim.set_animation_options(binding,['bow'],-1,True)
        with self.assertRaises(ValueError):
            self.anim.set_animation_options(self.find('base','death')['binding_id'],['bow'],99,True)
        self.assertEqual(self.find('base','idle_special')['weight'],75)
        self.assertEqual(self.find('base','idle_special')['compatibleWith'], ['unarmed','1hs'])

    def test_invalid_input_fails_closed(self):
        binding = self.find('base','idle_special')['binding_id']
        for bad in ('all', ['base'], ['1hs','1hs'], ['unknown'], [123], None):
            with self.assertRaises(ValueError, msg=f'invalid {bad!r}'):
                self.anim.set_compatibility(binding,bad)
        self.assertEqual(set(self.find('base','idle_special')['compatibleWith']), set(EQUIPMENT_SETS))

    def test_export_keeps_published_ids_weight_and_disarm(self):
        row = self.find('base','idle_special')
        with self.anim.connect() as db:
            db.execute("UPDATE monster_animation_clips SET asset_id='123456',published_sha256=sha256 WHERE id=?",(row['clip_id'],))
        self.anim.set_weight(row['binding_id'],75)
        self.anim.set_disarm(row['binding_id'],False)
        self.anim.set_compatibility(row['binding_id'],['1hs','unarmed'])
        published = self.find('base','idle_special')
        self.assertEqual(published['asset_id'],'123456')
        self.assertEqual(published['weight'],75)
        self.assertFalse(published['disarm'])
        self.assertEqual(published['compatibleWith'],['unarmed','1hs'])
        generated = (self.root/'src/shared/npc/NpcAnimationRegistry.luau').read_text()
        self.assertIn('compatibleWith = table.freeze({"unarmed", "1hs"})',generated)
        self.assertIn('weight = 75',generated)
        self.assertIn('rbxassetid://123456',generated)

    def test_unarmed_is_own_animation_set_with_melee_damage(self):
        self.assertIn('unarmed',WEAPON_SETS)
        self.assertEqual(parse('generic_unarmed_attack_01.rbxm','generic')['weaponSet'],'unarmed')
        self.assertEqual(self.find('unarmed','attack')['compatibleWith'],['unarmed'])
        equipment = (ROOT/'src/server/npc/NpcEquipmentService.luau').read_text()
        self.assertIn('WeaponAttackMovement.AnimationSetForType("hands")',equipment)
        movement = (ROOT/'src/shared/weapon/WeaponAttackMovement.luau').read_text()
        self.assertIn('animationSet = "unarmed"',movement)
        combat = (ROOT/'src/server/npc/NpcCombatAIService.luau').read_text()
        self.assertIn('DamageService.Apply(agent.model, target',combat)
        self.assertNotIn('local weaponSet = tostring(model:GetAttribute("NpcWeaponSet") or "1hs")',combat)

    def test_repeated_scan_retains_custom_compatibility(self):
        row = self.find('base','idle_special')
        self.anim.set_compatibility(row['binding_id'],['unarmed','bow'])
        self.anim.scan_folder('generic',str(self.root/'inbox'))
        self.assertEqual(self.find('base','idle_special')['compatibleWith'],['unarmed','bow'])

    def test_compatibility_resolver_is_shared_and_runtime_consumed(self):
        resolver=(ROOT/'src/shared/animation/AnimationCompatibility.luau').read_text()
        adapter=(ROOT/'src/server/npc/NpcAnimationTracks.luau').read_text()
        self.assertIn('function AnimationCompatibility.Allowed',resolver)
        self.assertIn('Compatibility.Allowed(row, activeSet)',adapter)
        self.assertNotIn('if set == activeSet',adapter)

if __name__=='__main__': unittest.main(verbosity=2)
