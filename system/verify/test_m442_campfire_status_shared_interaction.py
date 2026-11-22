"""M442 structural contracts. Play Test must validate Studio replication and effects."""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]

def read(path):
    return (ROOT / path).read_text(encoding='utf-8')

class CampfireAndFireplaceM442(unittest.TestCase):
    def test_source_bones_are_authored_and_location_registry_scoped(self):
        manifest = json.loads(read('assets/manifests/location-assets-fbx/campfire_01.json'))
        bones = set()
        def collect(value):
            if isinstance(value, dict):
                if value.get('name') in ('fire_socket', 'cooking_pot_01_socket'):
                    bones.add(value['name'])
                for child in value.values(): collect(child)
            elif isinstance(value, list):
                for child in value: collect(child)
        collect(manifest)
        self.assertEqual(bones, {'fire_socket', 'cooking_pot_01_socket'})
        service = read('src/server/world/LocationCampfireService.luau')
        self.assertIn('definition.slug ~= "campfire_01"', service)
        self.assertIn('fireCount ~= 1 or cookingCount ~= 1', service)
        self.assertIn('Fireplace.RegisterCampfire(model, fire, cooking)', service)
        self.assertIn('Environment.Observe(observe)', service)
        self.assertNotIn('Workspace:GetDescendants()', service)
        self.assertIn('model.AncestryChanged:Connect', service)

    def test_placement_observer_is_generic_and_startup_ordered(self):
        environment = read('src/server/world/EnvironmentAssetService.luau')
        catalog = read('src/server/bootstrap/ServiceCatalog.luau')
        self.assertIn('function EnvironmentAssetService.Observe(callback:', environment)
        self.assertIn('emit(model, nil)', environment)
        self.assertIn('emit(model, definition)', environment)
        self.assertIn('LocationCampfireService', catalog)
        self.assertIn('dependsOn = {"EnvironmentAssetService", "HouseSocketService"}', catalog)
        self.assertLess(catalog.index('name = "HouseSocketService"'),
                        catalog.index('name = "LocationCampfireService"'))

    def test_shared_state_has_distinct_fuel_transitions(self):
        engine = read('src/server/world/HouseFireplaceService.luau')
        self.assertIn('if state.kind == "campfire" then\n        transitionToEmpty(state, revision)', engine)
        self.assertIn('if state.kind == "house" and not replaceFuel(state, "firewood_01")', engine)
        self.assertIn('if state.kind == "campfire" then "fire" else "firewood"', engine)
        self.assertIn('replaceFuel(state, "embers_01")', engine)
        self.assertIn('state.potMountSocket, ownerHeading)', engine)
        self.assertIn('Config.CookingSecondsOnEmbers', engine)
        self.assertIn('Config.CookingSecondsOnFire', engine)
        self.assertIn('if state.potInstance and state.potState == "idle"', engine)
        self.assertIn('notify(state.cookOwner, {kind = "toast"', engine)
        self.assertIn('Config.ResourceSpend.Wood.amount', engine)

    def test_house_chimney_is_controlled_by_fuel_in_same_state(self):
        house = read('src/server/world/HouseSocketService.luau')
        engine = read('src/server/world/HouseFireplaceService.luau')
        self.assertIn('chimneySmoke.Enabled = false', house)
        self.assertIn('Fireplace.BindChimney(house, chimneySmoke)', house)
        self.assertIn('if state.chimney then state.chimney.Enabled = state.fuelStage ~= "empty" end', engine)
        self.assertIn('emitter.Enabled = false', engine)

    def test_authored_effects_are_reused_and_preset_switching_does_not_block_camera(self):
        engine = read('src/server/world/HouseFireplaceService.luau')
        prompt = read('src/client/world/HouseSocketPromptController.luau')
        self.assertIn('state.fireAuthored = true', engine)
        self.assertIn('state.lightAuthored = true', engine)
        self.assertIn('fire.Enabled = enabled', engine)
        self.assertIn('light.Enabled = enabled and lightPreset.Enabled', engine)
        self.assertIn('local referenceMode = state.kind == "campfire" and state.potInstance == nil', engine)
        self.assertIn('Config.CampfireFire else Config.Fire', engine)
        self.assertIn('Config.CampfireLight else Config.Light', engine)
        self.assertIn('gui = Instance.new("ScreenGui")', prompt)
        self.assertIn('background.Position = UDim2.new(1, -22 + cfg.offsetXPx, 0.5, cfg.offsetYPx)', prompt)
        self.assertIn('MobileLayout.Context(gui.AbsoluteSize.X, gui.AbsoluteSize.Y, panelHeight)', prompt)
        self.assertNotIn('Instance.new("BillboardGui")', prompt)
        self.assertIn('remoteName = if prompt:GetAttribute("Game1SocketDomain") == "campfire"', prompt)
        self.assertIn('remote:FireServer(socket, key)', prompt)
        self.assertIn('if not selected or selected.Parent ~= socket then return end', prompt)

    def test_status_is_one_closable_bottom_panel_with_retained_radius(self):
        client = read('src/client/world/HouseFireplaceController.luau')
        self.assertIn('panel.Position = UDim2.new(0.5, 0, 1, -24)', client)
        self.assertIn('close.Activated:Connect', client)
        self.assertIn('dismissed[selected] = true', client)
        self.assertIn('dismissed[socket] = nil', client)
        self.assertIn('if distance > radius then', client)
        self.assertIn('active(socket) and not dismissed[socket]', client)
        self.assertIn('if fuel == "firewood" or fuel == "fire" or fuel == "embers"', client)
        self.assertNotIn('BillboardGui', client)

    def test_campfire_socket_head_alignment_handles_vertical_cooking_bone(self):
        mount = read('src/server/world/HouseSocketAssetMount.luau')
        engine = read('src/server/world/HouseFireplaceService.luau')
        self.assertIn('SpawnOrientation.Upright(socketFrame, fromBone, 0)', mount)
        self.assertIn('if not targetFrame and ownerHeading then', mount)
        self.assertIn('CFrame.lookAlong(socketFrame.Position, flat.Unit, Vector3.yAxis)', mount)
        self.assertIn('BoneModelMount.Place(model, grip, targetFrame)', mount)
        self.assertIn('state.house:GetPivot().LookVector', engine)
        self.assertNotIn('GetBoundingBox', mount)
        self.assertNotIn('Instance.new("Part")', mount)

    def test_server_rechecks_all_input(self):
        service = read('src/server/world/LocationCampfireService.luau')
        self.assertIn('bySocket[socket]', service)
        self.assertIn('entry.socket ~= socket', service)
        self.assertIn('not prompt.Enabled', service)
        self.assertIn('root.Position - socketFrame(socket).Position', service)
        self.assertIn('moment - (cooldown[player] or 0) < 0.45', service)
        self.assertIn('typeof(socket) ~= "Instance"', service)
        self.assertIn('Fireplace.Interact(model, player, key)', service)
        self.assertIn('CampfireSocketInteract', service)

    def test_mechanics_catalog_has_real_script_refs_and_no_house_socket_pollution(self):
        from sys import path
        path.insert(0, str(ROOT / 'system/control-center'))
        from mechanics.catalog import permitted_source, snapshot
        cards = snapshot()['domains'][0]['items']
        self.assertEqual(len(cards), 10)
        card = next(c for c in cards if c['id'] == 'fireplace')
        sources = {s['id'] for s in card['sources']}
        self.assertTrue({'campfire-service', 'fireplace-config', 'fireplace-status'}.issubset(sources))
        for key in sources:
            path, _ = permitted_source('fireplace', key)
            self.assertTrue((ROOT / path).is_file(), path)
        self.assertNotIn('fire_socket', card['sockets'])
        self.assertNotIn('cooking_pot_01_socket', card['sockets'])

if __name__ == '__main__':
    unittest.main()
