"""M556 source contracts; actual rendering/input require Studio."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
def read(p): return (ROOT / p).read_text(encoding='utf8')
class GpUiRefresh(unittest.TestCase):
    def test_purchase_replaces_entry(self):
        s=read('src/server/combat/SkillEffects.luau')
        for x in ('refreshPurchasedBuff == true and source == target','Buffs.ByEffect[effect] == skill','if state[effect] and not canRefresh then return false end','expiresAt=Workspace:GetServerTimeNow()+skill.duration','active[target] ~= state or state[effect] ~= entry'):
            self.assertIn(x,s)
        service=read('src/server/dev/GameplayTestService.luau')
        self.assertIn('Effects.Apply(character,character,definition,0,true)',service)
        self.assertNotIn('Already active',service)
        self.assertIn('item.button.Active=not busy and gold>=Config.Price',read('src/client/dev/GameplayBufferController.luau'))
    def test_receipt_layer_and_renewal(self):
        s=read('src/client/combat/BuffHud.luau')
        for x in ('receiptGui.DisplayOrder=61','receipts:SetAttribute("WorldInputPassthrough", true)','if slot.untilTime~=untilTime then','if slot.toast then slot.toast:Destroy() end','slot.toast==toast and slot.icon.Parent','icon(receipts,row,48,5)'):
            self.assertIn(x,s)
        self.assertIn('pixel.ZIndex=frame.ZIndex+1',read('src/client/combat/BuffIconView.luau'))
    def test_hub_and_spawn(self):
        ui=read('src/client/dev/GameplayTestController.luau')
        self.assertLess(ui.index('contentButton(navigation, "Hub"'),ui.index('local first = row'))
        self.assertIn('invoke("hub")',ui)
        self.assertIn('contentButton(group, "Spawn", 30)',ui)
        s=read('src/server/dev/GameplayTestService.luau')
        hub=s.split('if action == "hub" then',1)[1].split('local monster =',1)[0]
        for x in ('clearGroup(s)','Arena.Warp(character, s.layout.hub,true)','updateHubSpeed(s)'): self.assertIn(x,hub)
        self.assertNotIn('Loadout.Set',hub)
        self.assertNotIn('action == "visit"',s)
    def test_overhead(self):
        s=read('src/client/combat/HealthBarView.luau')
        self.assertIn('gui:SetAttribute("WorldInputPassthrough", true)',s)
        self.assertIn('model:GetAttribute("GameplayTestKind") == "group"',s)
        self.assertIn('local hasPortrait = usesPortrait()',s)
        self.assertIn('sameZone or (group and inRange)',read('src/client/combat/OverheadHealthController.luau'))
        self.assertIn('record.testKind ~= "group" and (not record.testZone or record.testZone > 6)',read('src/server/monster/MonsterSpawnerService.luau'))
    def test_regeneration_tick(self):
        self.assertIn('RegenerationHPPerSecond = 1',read('src/shared/character/CharacterStatsConfig.luau'))
        s=read('src/server/character/CharacterRegenerationService.luau')
        for x in ('local STEP = 1','math.floor(accumulator / STEP) * STEP','accumulator -= elapsed','if guided then 0 else','Healing.Restore(character, rate * elapsed)'): self.assertIn(x,s)
