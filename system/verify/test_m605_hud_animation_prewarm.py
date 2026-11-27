from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET
import struct
ROOT = Path(__file__).resolve().parents[2]
def read(p): return (ROOT/p).read_text(encoding='utf8')
class M605(unittest.TestCase):
    def test_world_entry_reuses_existing_cache_and_waits_before_curtain(self):
        ui=read('src/client/character/CharacterCreationController.luau').split('local function sync()')[1]
        self.assertLess(ui.index('MeshPreloader.PreloadModel, model, current'),ui.index('AnimationController.WaitForPrewarm(model, current, deadline)'))
        self.assertLess(ui.index('WorldAnimations.Wait(current, deadline'),ui.index('cover(false)'))
        self.assertIn('local deadline = os.clock() + 12',ui)
        self.assertIn('player.Character == model and leaving',ui)
        ctrl=read('src/client/character/animation/CharacterAnimationController.luau')
        self.assertEqual(ctrl.count('AnimationTrackCache.new(animator)'),1)
        self.assertIn('if character ~= newCharacter or cache ~= boundCache then return end\n            warmResult = result',ctrl)
        self.assertIn('while current() and os.clock() < deadline',ctrl)
    def test_world_content_is_batched_and_session_cached(self):
        source=read('src/client/character/animation/WorldAnimationPreloader.luau')
        for name in ('MonsterAnimationRegistry','NpcAnimationRegistry','profile.slots','ids[id] = true','local BATCH = 16','if started then return end','Instance.new("Animation")','ContentProvider:PreloadAsync(requests','Enum.AssetFetchStatus.Success','animation:Destroy()','not done and os.clock() < deadline'):
            self.assertIn(name,source)
        self.assertNotIn('LoadAnimation(',source)
        self.assertNotIn('Instance.new("Animator")',source)
        self.assertIn('WorldAnimationPreloader")).Start()',read('src/client/init.client.luau'))
    def test_death_has_exclusive_pose_owner(self):
        source=read('src/server/monster/MonsterDeathLifecycle.luau').split('local function beginDeath')[1]
        self.assertLess(source.index('DeathAnimationPolicy.Start(track,'),source.index('stopWanderMovement(entry)'))
        source=read('src/server/npc/NpcAnimationService.luau').split('local function beginDeath()')[1]
        self.assertLess(source.index('DeathAnimationPolicy.Start(death,'),source.index('idle:Stop()'))
        for filename,gate in [('monster/MonsterAttackLocomotionController.luau','if not alive then'),('actor/NpcAttackLocomotionController.luau','if entry.model:GetAttribute("LifeState") ~= "Alive" then')]:
            step=read('src/client/'+filename).split('local function step(')[1]
            self.assertLess(step.index(gate),step.index('targetBone.Transform ='))
            self.assertIn('entry.weight = 0',step)
    def test_svg_raster_payload_and_png_dimensions(self):
        data=read('src/client/character/mobile/MobileActionIconData.luau')
        for name in ('Attack','Jump','Aim'):
            self.assertEqual(ET.parse(ROOT/f'assets/ui/mobile-actions/{name}.svg').getroot().tag,'{http://www.w3.org/2000/svg}svg')
            raw=re.search(rf'{name} = "([0-9a-f]+)"',data)[1]
            payload=b''.join(bytes.fromhex(raw[i+4:i+12])*int(raw[i:i+4],16) for i in range(0,len(raw),12))
            png=(ROOT/f'assets/ui/mobile-actions/{name}.png').read_bytes()
            self.assertEqual(png[:8],b'\x89PNG\r\n\x1a\n')
            self.assertEqual(struct.unpack('>II',png[16:24]),(48,48))
            self.assertEqual(len(payload),48*48*4)
        self.assertIn('Icons.Apply(button, name)',read('src/client/character/mobile/MobileControlsView.luau'))
    def test_alignment_theme_and_lock_order(self):
        layout=read('src/client/character/mobile/MobileLayout.luau')
        self.assertIn('local attackRight = 2',layout); self.assertIn('local weaponMargin = 2',layout)
        self.assertIn('if i == 4 then x = attackRight end',layout); self.assertIn('x = skills[1].x',layout)
        self.assertIn('gui.ScreenInsets = Enum.ScreenInsets.DeviceSafeInsets',read('src/client/character/mobile/MobileControlsView.luau'))
        for path in ('character/mobile/MobileControlsView','weapon/MobileWeaponSlots','combat/WalletHud','localization/LanguageMenuController','dev/StudioDebugDock'):
            self.assertIn('Theme.Apply(',read('src/client/'+path+'.luau'))
        prompt=read('src/client/world/HouseSocketPromptController.luau')
        self.assertIn('actions[1], actions[2] = actions[2], actions[1]',prompt)
if __name__ == '__main__': unittest.main()
