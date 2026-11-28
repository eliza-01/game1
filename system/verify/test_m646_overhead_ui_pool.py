from pathlib import Path
import shutil
import subprocess
import unittest
ROOT = Path(__file__).resolve().parents[2]

class OverheadPoolM646(unittest.TestCase):
    def test_real_policy_pool_registry_oracle(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua unavailable')
        subprocess.run([lua, str(ROOT/'system/verify/overhead_pool_m646.lua'), str(ROOT)], check=True, timeout=20)

    def test_live_wiring_and_view_lease_contract(self):
        def read(name): return (ROOT/'src/client/combat'/name).read_text()
        controller = read('MnpcOverheadController.luau')
        view = read('HealthBarView.luau')
        registry = read('MnpcOverheadRegistry.luau')
        self.assertEqual(controller.count('Heartbeat:Connect'), 1)
        self.assertIn('registry.ready[model]', controller)
        self.assertIn('pool:Acquire(record.model', controller)
        self.assertIn('if not (name or hp or icon) then', controller)
        self.assertNotIn('HealthBarView', registry)
        for token in ('generation == token', 'generation += 1', 'tween:Cancel()', 'portrait:Destroy()',
                      'gui.Adornee = nil', 'gui.Parent = nil', 'model, anchor, currentStyle = nil, nil, nil',
                      'ratio == lastRatio and goal.BackgroundColor3 == lastColor', 'maxDistanceOverride'):
            self.assertIn(token, view)
        init = (ROOT/'src/client/init.client.luau').read_text()
        self.assertEqual(init.count('MnpcOverheadController.Start()'),1)
        self.assertFalse((ROOT/'src/client/combat/NpcOverheadController.luau').exists())
        self.assertFalse((ROOT/'src/client/combat/OverheadHealthController.luau').exists())
        self.assertIn('Game1ManualLocale', (ROOT/'src/client/localization/LanguageState.luau').read_text())

    def test_real_view_rebind_with_roblox_doubles(self):
        import re
        import tempfile
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua unavailable')
        s = (ROOT/'src/client/combat/HealthBarView.luau').read_text()
        # Adapt only Luau syntax; keep actual view behavior and callbacks intact.
        s = s.replace(': {[string]: string}', '').replace(': {[string]: any}', '')
        s = re.sub(r': (?:Instance|UICorner|Model|BasePart|PlayerGui|Tween|Frame|UIStroke|Color3|number|string|boolean|any)(?:\?)?(?=[,)=\s]|$)', '', s)
        s = s.replace(': {RBXScriptConnection}', '').replace('generation += 1', 'generation = generation + 1')
        conversions = {
            'return if Language.Current() == "ru-ru" and type(russian) == "string" and russian ~= "" then russian else english': 'return (Language.Current() == "ru-ru" and type(russian) == "string" and russian ~= "") and russian or english',
            'local text = if monster then tostring': 'local text = monster and tostring',
            'else tostring(model:GetAttribute("CharacterDisplayName") or model.Name)': 'or tostring(model:GetAttribute("CharacterDisplayName") or model.Name)',
            'if maxHP > 0 then hp / maxHP else 0': '(maxHP > 0 and hp / maxHP or 0)',
            'if hasPortrait then 1 else 0': 'hasPortrait and 1 or 0',
            'if monster then tonumber(model:GetAttribute("Level")) else nil': 'monster and tonumber(model:GetAttribute("Level")) or nil',
            'if number.Visible then (if Language.Current() == "ru-ru" then "Ур." else "Lv.") .. tostring(math.floor(level or 0)) else ""': 'number.Visible and ((Language.Current() == "ru-ru" and "Ур." or "Lv.") .. tostring(math.floor(level or 0))) or ""',
            'if star.Visible then measure("*", titleSize) else 0': 'star.Visible and measure("*", titleSize) or 0',
            'if number.Visible then measure(number.Text, levelSize) + 5 else 0': 'number.Visible and (measure(number.Text, levelSize) + 5) or 0',
            'if hasPortrait then 17 else 0': 'hasPortrait and 17 or 0',
            'if model:GetAttribute("GameplayTestVisualPlaceholder") then " · proxy" else ""': 'model:GetAttribute("GameplayTestVisualPlaceholder") and " · proxy" or ""',
            'if hasPortrait then 800 else math.max': 'hasPortrait and 800 or math.max',
            'if monster then "monster" else "self"': 'monster and "monster" or "self"',
            'if hasPortrait then 46 else 0': 'hasPortrait and 46 or 0',
        }
        for old,new in conversions.items():
            self.assertIn(old,s)
            s=s.replace(old,new)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'view.lua';path.write_text(s, encoding='utf-8')
            subprocess.run([lua,str(ROOT/'system/verify/overhead_view_m646.lua'),str(path)],check=True,timeout=20)
