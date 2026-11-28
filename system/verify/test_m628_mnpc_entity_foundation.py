"""Shared entity-first construction: real module code on a minimal Lua oracle.

Native joints, Humanoid physics and AnimationTrack behavior still require Studio.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ACTOR = ROOT / 'src/server/actor'


def read(path):
    return (ROOT / path).read_text(encoding='utf-8')


def lua_source(name):
    source = (ACTOR / (name + '.luau')).read_text(encoding='utf-8')
    # Only the explicitly used Luau type annotations and if expressions differ
    # from Lua. Execute the implementation, not a second shell/rig algorithm.
    source = re.sub(r'(?<!:): (?:"Monster" \| "NPC"|Model|BasePart|Humanoid|Folder|Vector3|CFrame|string|number|boolean\?|boolean|any\?)(?=[,)])', '', source)
    source = re.sub(r'\): (?:\([^\n]+\)|Model\?|CFrame)\n', ')\n', source)
    source = source.replace('return visual :: Model, if visualRoot and visualRoot:IsA("BasePart") then visualRoot else nil',
                            'return visual, (visualRoot and visualRoot:IsA("BasePart")) and visualRoot or nil')
    return source


class MnpcEntityFoundationM628(unittest.TestCase):
    def test_shared_shell_and_attachment_oracle(self):
        lua = shutil.which('texlua') or shutil.which('lua')
        if not lua:
            self.skipTest('Standalone Lua unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            files = []
            for name in ('MnpcNavigationShell', 'MnpcVisualRig', 'MnpcEntityLifecycle', 'MnpcRigGeometry', 'MnpcPresentationLifecycle'):
                path = Path(tmp) / (name + '.lua')
                path.write_text(lua_source(name), encoding='utf-8')
                files.append(str(path))
            subprocess.run([lua, str(ROOT/'system/verify/mnpc_entity_foundation_m628.lua'), *files], check=True, timeout=20)

    def test_both_production_spawners_use_shared_contract(self):
        for name, entity, root, kind in (
            ('monster/MonsterSpawnerService', 'model', 'navigationRoot', 'Monster'),
            ('npc/NpcSpawnerService', 'entity', 'root', 'NPC'),
        ):
            text = read('src/server/' + name + '.luau')
            self.assertIn('WaitForChild("MnpcEntityLifecycle")', text)
            self.assertNotIn('template:Clone()', text)
            calls = ['MnpcLifecycle.Create(', f'MnpcLifecycle.CopyTemplateMetadata({entity}, template)',
                     f'MnpcLifecycle.PrepareShell({entity}, {root}, template, surface, yaw, "{kind}")',
                     f'MnpcLifecycle.AttachRig({entity}, {root}, template, surface, yaw, "{kind}", prepared)',
                     f'MnpcLifecycle.Publish({entity}, {root},', f'EntityHitboxService.Attach({entity}, visual)',
                     f'MnpcLifecycle.MarkRigReady({entity})']
            positions = list(map(text.index, calls))
            self.assertEqual(positions, sorted(positions))
            self.assertIn('EntityHitboxService.Detach', text)
        self.assertFalse((ROOT/'src/server/npc/NpcRigFactory.luau').exists())

    def test_no_implicit_combat_or_animation_changes(self):
        shell = read('src/server/actor/MnpcNavigationShell.luau')
        lifecycle = read('src/server/actor/MnpcEntityLifecycle.luau')
        attach = read('src/server/actor/MnpcVisualRig.luau')
        create = lifecycle.split('function Lifecycle.Create', 1)[1].split('function Lifecycle.CopyTemplateMetadata', 1)[0]
        for token in ('template', 'Clone(', 'Animator', 'AnimationTrack', 'RootCollider'):
            self.assertNotIn(token, create)
        for text in (shell, attach, lifecycle):
            for token in ('LoadAnimation(', 'Heartbeat:Connect', 'RemoteEvent', 'EntityHitboxService'):
                self.assertNotIn(token, text)
        self.assertIn('collider.CanCollide = false', shell)
        self.assertIn('collider.CanQuery = false', shell)
        self.assertIn('collider.CanQuery = true', attach)
        self.assertIn('visualWeld.Part1 = visualRoot', attach)
        self.assertIn('castWeld.C0 = collider.CFrame:ToObjectSpace(visualRoot.CFrame)', attach)
        self.assertIn('if kind == "NPC" then', shell)
        self.assertIn('humanoid:SetStateEnabled(Enum.HumanoidStateType.FallingDown, false)', shell)
        self.assertNotIn('Instance.new("Bone")', attach)

    def test_monster_pose_binding_waits_for_real_rig_and_releases_pending(self):
        text = read('src/server/monster/MonsterAgentLifecycle.luau')
        self.assertIn('GetAttributeChangedSignal("Game1MnpcRigReady"):Connect(ready)', text)
        self.assertIn('model.Destroying:Connect(function()', text)
        self.assertIn('if not model:IsDescendantOf(Workspace) then releaseAgent(agent) end', text)
        self.assertIn('model:GetAttribute("Game1MnpcRigReady") ~= true then return end', text)
        self.assertIn('if not animator then', text)  # real native pose remains required for actions
        self.assertIn('agent.poseBinding:Close()', text)
        self.assertNotIn('task.wait(0.03)', text)


if __name__ == '__main__':
    unittest.main()
