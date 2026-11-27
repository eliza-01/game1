"""M486 contracts; actual render/asset/remote behavior requires Studio Play."""
import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def src(path):
    return (ROOT / path).read_text(encoding='utf8')

class CreationPadlockM486(unittest.TestCase):
    def test_camera_follows_open_category_only(self):
        c = src('src/client/character/CharacterCreationController.luau')
        p = src('src/client/character/CharacterCreationPanel.luau')
        self.assertNotIn('ToggleFace', c + p)
        self.assertIn('local face = activeTab ~= nil', c)
        self.assertIn('visible[category] = #entries > 0', c)
        self.assertIn('activeTab = if activeTab == category then nil else category', c)
        self.assertIn('if activeTab and not visible[activeTab] then activeTab = nil end', c)
        self.assertIn('if #entries > 1 then', src('src/client/character/CharacterCreationAppearanceView.luau'))

    def test_preview_keeps_old_rig_until_evaluated_replacement(self):
        p = src('src/client/character/CharacterCreationPreviewController.luau')
        self.assertLess(p.index('object.LocalTransparencyModifier = 1'), p.index('instance.Parent = self.folder'))
        self.assertLess(p.index('track.TimePosition ='), p.index('RunService.PreSimulation:Wait()'))
        self.assertLess(p.index('RunService.PreSimulation:Wait()'), p.index('previous:Destroy()'))
        self.assertLess(p.index('previous:Destroy()'), p.index('part.LocalTransparencyModifier = transparency'))
        self.assertIn('Mounts.UpdateCharacter(instance)', p)
        self.assertIn('if not current() then return discard() end', p)

    def test_single_submission_overlay_retry_and_authoritative_record(self):
        c = src('src/client/character/CharacterCreationController.luau')
        p = src('src/client/character/CharacterCreationPanel.luau')
        g = src('src/server/character/CharacterCreationGateway.luau')
        store = src('src/server/character/CharacterCreationProfileStore.luau')
        self.assertIn('CreationSubmittingOverlay', p)
        self.assertIn('views.overlay.Modal = busy', p)
        self.assertIn('if pending or leaving or (stage ~= "creation"', c)
        self.assertIn('for attempt = 1, attempts do', c)
        self.assertIn('character_save_failed = true', c)
        self.assertIn('if epoch ~= token or leaving then return end', c)
        self.assertIn('if stage == "selection" and existing then', g)
        self.assertIn('record.archetype, record.appearance', g)
        self.assertIn('previous.revision == candidate.revision', store)
        self.assertIn('if not Roster.Matches(previous, session.expected) then return nil end', store)
        self.assertIn('if replace then session.document = candidate else session.document.revision = candidate.revision end', store)
        self.assertLess(store.index('session.expected = Roster.Copy(candidate)'), store.index('if replace then session.document = candidate else'))

    def test_both_padlocks_share_one_state_and_use_published_grip(self):
        registry = json.loads(src('assets/manifests/location-assets.json'))
        row = next(x for x in registry['items'] if x['slug'] == 'padlock_02')
        self.assertEqual(row['model_asset_id'], '92574610508351')
        self.assertTrue(any(b['name'] == 'padlock_01_hole_socket' for mesh in row['fbxAnalysis']['meshes'] for b in mesh['bones']))
        v = src('src/server/world/HousePadlockVisuals.luau')
        m = src('src/server/world/HouseSocketAssetMount.luau')
        s = src('src/server/world/HouseSocketService.luau')
        contract = src('src/shared/world/HouseSocketContract.luau')
        self.assertIn('for _, name in Contract.PadlockSockets do', v)
        self.assertIn('mounted == expected', v)
        self.assertIn('if states[house] ~= state then folder:Destroy(); return end', v)
        self.assertIn('PadlockVisuals.SetAttached(house, entry.sockets, locked)', s)
        self.assertIn('PadlockVisuals.Clear(house)', s)
        self.assertNotIn('placeholder = "padlock"', contract)
        self.assertIn('AuthoredPropSocketMount.Align(model, sourceSocket, target)', m)
        mount = src('src/shared/rig/AuthoredPropSocketMount.luau')
        self.assertIn('BoneModelMount.Place(model, grip, targetFrame)', mount)
        self.assertIn('SocketFacing.FullFrame', mount)
        self.assertNotIn('Game1PadlockPlaceholder', src('src/server/world/HouseSocketEffects.luau'))

if __name__ == '__main__': unittest.main()
