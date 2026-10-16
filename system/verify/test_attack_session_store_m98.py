"""M98 source and ownership contracts. Actual Luau gameplay needs Studio Play tests."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

class AttackSessionStoreM98Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = read("src/server/combat/AttackSessionStore.luau")
        cls.attack = read("src/server/combat/AttackService.luau")
        cls.damage = read("src/server/combat/AttackDamageResolver.luau")
        cls.collision = read("src/server/combat/WeaponEnvironmentCollision.luau")

    def test_single_session_owner_without_side_effect_dependencies(self):
        self.assertIn('local byPlayer: { [Player]: Session } = {}', self.store)
        self.assertIn('byPlayer[player] = session', self.store)
        self.assertIn('byPlayer[player] = nil', self.store)
        self.assertIn('return table.freeze(AttackSessionStore)', self.store)
        for forbidden in ('game:GetService', 'OnServerEvent', 'task.delay', 'Workspace:', 'DamageService', 'SetAttribute'):
            self.assertNotIn(forbidden, self.store)
        for legacy in ('local activeUntil:', 'local activeSerial:', 'local weaponSweepStates:',
                       'local activeDamageWindows:', 'local activeHeadshotTarget:', 'local activeHitTargets:'):
            self.assertNotIn(legacy, self.attack)

    def test_start_sets_isolated_per_player_hit_and_headshot_state(self):
        for token in ('function AttackSessionStore.Begin(', 'hitTargets = {}', 'headshotTarget = nil',
                      'environmentBlocked = false', 'suppressedBounceLogged = false',
                      'sweepState = nil', 'damageWindow = damageWindow', 'untilTime = untilTime'):
            self.assertIn(token, self.store)
        self.assertIn('AttackSessionStore.IsCoolingDown(player, now)', self.attack)
        self.assertIn('AttackSessionStore.Begin(player, character, serial, clientAttackId, now + attackDuration, damageWindow)', self.attack)

    def test_finish_ignores_stale_callback_and_respawn_identity(self):
        for token in ('session.character == character', 'session.serial == serial',
                      'session.clientAttackId == clientAttackId',
                      'if not matches(session, character, serial, clientAttackId) then',
                      'byPlayer[player] = nil'):
            self.assertIn(token, self.store)
        self.assertIn('AttackSessionStore.Finish(player, character, serial, clientAttackId)', self.attack)
        self.assertIn('task.delay(durationSeconds, function()', self.attack)
        self.assertIn('Players.PlayerRemoving:Connect(AttackSessionStore.Forget)', self.attack)

    def test_bounce_invalidates_current_window_and_sweep_only(self):
        start = self.store.index('function AttackSessionStore.BlockForBounce(')
        end = self.store.index('function AttackSessionStore.Finish(', start)
        block = self.store[start:end]
        for token in ('AttackSessionStore.CanBounce(', 'session.environmentBlocked = true',
                      'session.damageWindow = nil', 'session.sweepState = nil', 'session.untilTime = untilTime'):
            self.assertIn(token, block)
        self.assertIn('AttackSessionStore.BlockForBounce(player, character, serial, clientAttackId, now + recoverySeconds)', self.attack)
        self.assertIn('if not session', self.attack)

    def test_pose_sample_state_committed_only_when_valid_and_not_bounced(self):
        for token in ('AttackSessionStore.EnsureSweep(session)',
                      'AttackSessionStore.CommitSweep(session, sweepState, elapsed, payload.boxCFrame, aimOrigin, aimDirection)',
                      'session.clientAttackId ~= clientAttackId', 'session.character ~= character',
                      'elapsed + 1e-4 < damageWindow.startTime',
                      'elapsed > damageWindow.endTime + 1e-4'):
            self.assertIn(token, self.attack)
        self.assertIn('if session.sweepState ~= sweep then', self.store)
        self.assertIn('sweep.lastElapsed = elapsed', self.store)

    def test_hit_dedup_and_one_headshot_remain_owned_by_resolver(self):
        self.assertIn('AttackSessionStore.HitTargets(player, character, serial, clientAttackId)', self.attack)
        self.assertIn('AttackSessionStore.SetHeadshotTarget(player, headshotTarget)', self.attack)
        self.assertIn('for _, target in ipairs(contacts) do', self.damage)
        self.assertIn('headshotTarget == nil', self.damage)
        self.assertIn('hitTargets[model] = true', self.damage)

    def test_collision_policy_remains_after_contact_before_damage(self):
        sweep=self.attack.split('local function applyAnimatedWeaponSweep(', 1)[1].split('local function clearAttackState(', 1)[0]
        markers = ('WeaponEnvironmentCollision.Query(previousVolume, volume)',
                   'HostilePursuitRegistry.Count(character)',
                   'triggerWeaponBounce(', 'hitCount += applyDamageInVolume(')
        for marker in markers:
            self.assertIn(marker, sweep)
        self.assertEqual(list(sorted(markers, key=sweep.index)), list(markers))
        self.assertIn('if Config.DebugLogs and AttackSessionStore.FirstBounceSuppression(player)', sweep)
        self.assertIn('Workspace:Blockcast(', self.collision)

if __name__ == '__main__':
    unittest.main()
