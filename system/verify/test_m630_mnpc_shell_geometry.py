"""M630 production boundary checks; moving shell oracle is shared with M628.
Native joints, humanoid motion, and exact Studio bounds still require smoke.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

def read(file):
    return (ROOT / file).read_text(encoding='utf-8')

class MnpcShellGeometry(unittest.TestCase):
    def test_shell_metadata_does_not_clone_or_evaluate_pose(self):
        geometry = read('src/server/actor/MnpcRigGeometry.luau')
        lifecycle = read('src/server/actor/MnpcEntityLifecycle.luau')
        for forbidden in ('Clone(', 'Instance.new(', 'LoadAnimation(', 'Heartbeat', 'RemoteEvent'):
            self.assertNotIn(forbidden, geometry)
        self.assertIn('local cached = cache[template]', geometry)
        self.assertIn('Geometry.IsCurrent(plan)', geometry)
        self.assertIn('function Geometry.Invalidate(template)', geometry)
        prepare = lifecycle.split('function Lifecycle.PrepareShell', 1)[1].split('Lifecycle.AttachRig', 1)[0]
        self.assertIn('Geometry.Plan(template', prepare)
        self.assertIn('Shell.CreateQueryCollider(', prepare)
        self.assertNotIn('Clone(', prepare)

    def test_both_spawners_use_prepared_shell_and_fail_closed(self):
        for file, model, root, kind in (
            ('monster/MonsterSpawnerService', 'model', 'navigationRoot', 'Monster'),
            ('npc/NpcSpawnerService', 'entity', 'root', 'NPC'),
        ):
            src = read('src/server/' + file + '.luau')
            ordered = (
                f'{model}:SetAttribute("Damageable", false)',
                f'MnpcLifecycle.PrepareShell({model}, {root}, template, surface, yaw, "{kind}")',
                f'MnpcLifecycle.AttachRig({model}, {root}, template, surface, yaw, "{kind}", prepared)',
                'if not visual then', f'{model}:Destroy()',
                f'MnpcLifecycle.Publish({model}', f'EntityHitboxService.Attach({model}, visual)',
            )
            # Restrict to the construction block, not release/death functions.
            start = src.index('local prepared = MnpcLifecycle.PrepareShell')
            start = src.rfind(f'{model}:SetAttribute("Damageable", false)', 0, start)
            self.assertGreaterEqual(start, 0)
            block = src[start:]
            positions = list(map(block.index, ordered))
            self.assertEqual(positions, sorted(positions))

    def test_prepared_collider_is_stable_and_inactive_until_attach(self):
        shell = read('src/server/actor/MnpcNavigationShell.luau')
        visual = read('src/server/actor/MnpcVisualRig.luau')
        self.assertIn('collider.CanQuery = false', shell)
        self.assertIn('prepared.collider == collider', visual)
        self.assertIn('Geometry.IsCurrent(prepared.geometry)', visual)
        self.assertIn('staged:PivotTo(navigationRoot.CFrame * prepared.geometry.pivotOffset)', visual)
        self.assertLess(visual.index('    local weld = bindVisual(navigationRoot, collider'), visual.index('    collider.CanQuery = true'))
        self.assertNotIn('navigationRoot.CFrame =', visual)
        self.assertNotIn('model:PivotTo(', visual)
        self.assertIn('groundAlign(staged, visual, surface, yaw, kind)', visual)

if __name__ == '__main__':
    unittest.main()
