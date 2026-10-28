"""M85 catalog contract tests. Studio is still required to execute the Luau engine code."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'src/server/bootstrap/ServiceCatalog.luau'
BOOTSTRAP = ROOT / 'src/server/bootstrap/ServiceBootstrap.luau'


class ServerBootstrapContractsM85(unittest.TestCase):
    @staticmethod
    def entries():
        content = CATALOG.read_text(encoding='utf-8')
        found = re.findall(r'\{name = "([^"]+)", critical = (true|false)(?:, dependsOn = \{([^}]*)\})?, start = function\(', content)
        return [(name, critical == 'true', re.findall(r'"([^"]+)"', deps)) for name, critical, deps in found]

    def test_all_services_unique_and_dependencies_precede_consumers(self):
        entries = self.entries()
        names = [name for name, _, _ in entries]
        self.assertGreaterEqual(len(entries), 15)
        self.assertIn("HouseSocketService", names)
        self.assertIn("HouseSocketDebugService", names)
        self.assertEqual(len(set(names)), len(names))
        ready = set()
        for name, _, deps in entries:
            self.assertTrue(set(deps).issubset(ready), (name, deps, ready))
            ready.add(name)

    def test_gameplay_and_debug_are_isolated(self):
        entries = {name: (critical, deps) for name, critical, deps in self.entries()}
        for name in ('EnvironmentAssetService', 'EntityHitboxService', 'AttackService', 'CharacterService'):
            self.assertTrue(entries[name][0], name)
        self.assertEqual(entries['MonsterAIService'][1], ['MonsterSpawnerService'])
        self.assertIn('CharacterService', entries['NpcSpawnerService'][1])
        self.assertFalse(entries['NpcSpawnerService'][0])
        self.assertFalse(entries['MonsterSpawnerService'][0])
        for name in ('MonsterDebugService', 'CustomScalingDebugService', 'MovementDebugService'):
            self.assertFalse(entries[name][0])
            self.assertEqual(entries[name][1], [], name)

    def test_bootstrap_catches_optional_fault_and_skips_dependents(self):
        content = BOOTSTRAP.read_text(encoding='utf-8')
        self.assertIn('pcall(entry.start)', content)
        self.assertIn('snapshot[prerequisite].status ~= "ready"', content)
        self.assertIn('status = "blocked"', content)
        self.assertIn('status = "failed"', content)
        self.assertIn('status = "ready"', content)
        self.assertIn('function ServiceBootstrap.GetSnapshot()', content)
        init = (ROOT / 'src/server/init.server.luau').read_text(encoding='utf-8')
        self.assertIn('ServiceBootstrap.StartAll(ServiceCatalog.Build(script)', init)
        self.assertIn('script:SetAttribute("CoreServicesReady", coreHealthy)', init)


if __name__ == '__main__':
    unittest.main()
