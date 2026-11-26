"""M554: server-priced purchase, transient wallet, one modal and shared icon view."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
def read(path): return (ROOT / path).read_text(encoding='utf8')

class BufferShop(unittest.TestCase):
    def test_wallet_and_transaction(self):
        config = read('src/shared/dev/GameplayBufferConfig.luau')
        self.assertIn('StartingGold=1000, Price=5', config)
        loadout = read('src/server/dev/GameplayTestLoadout.luau')
        self.assertIn('selection.gold = if previous then previous.gold else BufferConfig.StartingGold', loadout)
        purchase = loadout.split('function Loadout.PurchaseBuff', 1)[1].split('function Loadout.Reward', 1)[0]
        for token in ('RunService:IsStudio()', 'player.Character ~= character', 'Game1GameplayTestOwner', 'selection.gold < BufferConfig.Price', 'if not grant() then return false end', 'selection.gold -= BufferConfig.Price', 'character:SetAttribute("Gold", selection.gold)'):
            self.assertIn(token, purchase)
        self.assertLess(purchase.index('if not grant()'), purchase.index('selection.gold -='))
        self.assertNotIn('CharacterCreationProfileStore', purchase)
        self.assertIn('Loadout.Set(s.player, nil)', read('src/server/dev/GameplayTestService.luau'))

    def test_server_open_and_buy_guards(self):
        service = read('src/server/dev/GameplayTestService.luau')
        guard = service.split('local function bufferCharacter',1)[1].split('local function publishGuide',1)[0]
        for token in ('actor~=s.player','not allowed(actor)','not active(s)','s.guide','s.groupStarting','#s.group>0','Game1GameplayTestOwner','part:IsDescendantOf(s.folder)','BufferConfig.InteractionDistance'):
            self.assertIn(token,guard)
        buy = service.split('if action == "buyBuff"',1)[1].split('if action == "recovery"',1)[0]
        for token in ('bufferCharacter(s,player,fixture.root)','Effects.CanCast(character)','Buffs.ByEffect[request.effect]','selection.gold<BufferConfig.Price','Loadout.PurchaseBuff','Effects.Apply(character,character,definition,0,true)','fixture.lift()'):
            self.assertIn(token,buy)
        self.assertNotIn('request.price',buy)
        self.assertNotIn('request.gold',buy)
        self.assertNotIn('Effects.IsActive(character,definition.effect)',buy)
        self.assertLess(buy.index('Loadout.PurchaseBuff'),buy.index('fixture.lift()'))
        self.assertIn('if busy[player] then',service)
        dummy = read('src/server/dev/GameplayBufferDummy.luau')
        self.assertEqual(dummy.count('Instance.new("ProximityPrompt")'),1)
        self.assertIn('click.MouseClick:Connect',dummy)
        self.assertNotIn('Buffs.Rows',dummy)
        self.assertNotIn('onBuff',dummy)

    def test_single_modal_immediate_icon_purchase(self):
        ui=read('src/client/dev/GameplayBufferController.luau')
        for token in ('gui.Enabled=false','open.OnClientEvent:Connect','Buffs.Rows','Icons.Create(button,row,42)','button.Activated:Connect','remote:InvokeServer("buyBuff",{effect=row.effect})','response.ok then Coins.Play','not near(model) then close()','player.CharacterRemoving:Connect(close)','backdrop.Activated:Connect(close)'):
            self.assertIn(token,ui)
        self.assertNotIn('WorldInputPassthrough',ui)
        self.assertIn('BuffIconView',read('src/client/combat/BuffHud.luau'))
        self.assertIn('ipairs(row.iconMask)',read('src/client/combat/BuffIconView.luau'))
        self.assertIn('not UiInputGuard.IsPointerOnWorldInteraction()',read('src/client/combat/AttackController.luau'))
        self.assertIn('WorldInteractionDistance',read('src/client/UiInputGuard.luau'))

    def test_wallet_and_coin_presentation(self):
        wallet=read('src/client/combat/WalletHud.luau')
        for token in ('GetAttribute("Gold")','WorldInputPassthrough','AnchorPoint=Vector2.new(0,1)','bounds.stick','"Gold","LifeState"'):
            self.assertIn(token,wallet)
        self.assertNotIn('G %d',read('src/client/combat/PlayerHealthHudController.luau'))
        fx=read('src/client/dev/GameplayBufferCoins.luau')
        for token in ('for i=1,amount do','CanCollide=false','CanQuery=false','CanTouch=false','origin:Lerp(target,t)','folder:Destroy()','connection:Disconnect()','t>=1 then finish()'):
            self.assertIn(token,fx)
        init=read('src/client/init.client.luau')
        self.assertIn('WaitForChild("WalletHud")).Start()',init)
        self.assertIn('WaitForChild("GameplayBufferController")).Start()',init)

if __name__=='__main__': unittest.main()
