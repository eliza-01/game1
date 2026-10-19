"""M88: writable API contracts without importing production Host Agent/databases.

The tests execute real domain dispatchers with instrumented repositories. M85
covers their integration with the live loopback HTTP server and auth boundary.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/control-center"))
from api.write_dispatch import dispatch_post, dispatch_delete


class FakeStore:
    def __init__(self, name, calls):
        self.name = name
        self.calls = calls
        self.in_use = []
        self.failure = None
        self.usage = {"clips": 0, "bindings": 0}

    def monster_usage(self, slug):
        self.calls.append((self.name, "monster_usage", (slug,)))
        return list(self.in_use)

    def users_of_weapon(self, slug):
        self.calls.append((self.name, "users_of_weapon", (slug,)))
        return list(self.in_use)

    def character_usage(self, slug):
        self.calls.append((self.name, "character_usage", (slug,)))
        return self.usage

    def __getattr__(self, method):
        def call(*args, **kwargs):
            self.calls.append((self.name, method, args))
            if method == self.failure:
                raise ValueError("simulated store failure")
            if method == "get":
                return {"id": args[0], "model_asset_id": "1"}
            if method == "snapshot":
                return {"loadout": {"right": "", "left": ""}}
            if method == "publish":
                return {"id": args[0], "model_asset_id": "2"}
            return {"method": method, "args": list(args)}
        return call


class WriteRoutingM88(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.services = {}
        self.deps = defaultdict(self.fake_service)
        for name in (
            "store", "animations", "weapons", "monsters", "monster_animations",
            "npcs", "npc_animations", "npc_equipment", "npc_spawns",
            "monster_spawns", "animation_speed_scaling", "options_store",
            "locations", "location_assets", "deco_layouts", "timelines",
            "character_identity",
        ):
            self.deps[name] = FakeStore(name, self.calls)
        self.deps.update({
            "publication_credentials": lambda description="": {"description": description},
            "sync_character_to_studio": lambda slug: {"character": slug},
            "sync_monster_to_studio": lambda slug, kind="monster": {"monster": slug, "kind": kind},
            "sync_weapon_to_studio": lambda slug: {"weapon": slug},
            "npc_place_spawn": lambda payload: {"placement": payload},
            "npc_register_spawn": lambda payload: {"registration": payload},
            "request_active_studio_save": lambda: {"requested": True},
            "run_timeline_editor_bridge": lambda *args: {"duration": 0},
        })

    def fake_service(self):
        return lambda *args, **kwargs: "C:/fixtures/file.rbxm"

    def post(self, path, payload=None):
        return dispatch_post(path, lambda: payload if payload is not None else {}, self.deps)

    def delete(self, path):
        return dispatch_delete(path, lambda: {}, self.deps)

    def test_register_and_world_mutations_preserve_requests(self):
        for path, name in (
            ("/api/characters", "store"), ("/api/npcs", "npcs"),
            ("/api/monsters", "monsters"), ("/api/weapons", "weapons"),
            ("/api/location-assets", "location_assets"),
            ("/api/locations/register", "locations"),
            ("/api/options", "options_store"),
        ):
            with self.subTest(path=path):
                self.calls.clear()
                self.assertEqual(self.post(path, {"marker": 88})[0], 200)
                self.assertEqual(self.calls[-1][0], name)
                self.assertEqual(self.calls[-1][2], ({"marker": 88},))
        self.assertEqual(self.post("/api/location-assets/layout", {"x": 1})[1]["studioSave"], {"requested": True})

    def test_animation_binding_weight_zero_and_scan(self):
        status, result = self.post("/api/npc-animation-bindings/b%20one/weight", {"weight": 0})
        self.assertEqual(status, 200)
        self.assertEqual(self.calls[-1], ("npc_animations", "set_weight", ("b one", 0)))
        self.assertEqual(result["method"], "set_weight")
        self.assertEqual(self.post("/api/monster-animation-bindings/a/weight", {"weight": 0})[0], 200)
        # Legacy monster zero maps to 100; this stage must not change existing policy.
        self.assertEqual(self.calls[-1], ("monster_animations", "set_weight", ("a", 100)))
        self.post("/api/npc-animations/scan", {"npcSlug": "warsmith", "rootPath": "C:/npc"})
        self.assertEqual(self.calls[-1], ("npc_animations", "scan_folder", ("warsmith", "C:/npc")))

    def test_publish_missing_all_actor_types_and_error_result(self):
        for route, name in (
            ("/api/animations/hero/publish-missing", "animations"),
            ("/api/monster-animations/wolf/publish-missing", "monster_animations"),
            ("/api/npc-animations/warsmith/publish-missing", "npc_animations"),
        ):
            with self.subTest(route=route):
                self.assertEqual(self.post(route)[0], 200)
                self.assertEqual(self.calls[-1][0:2], (name, "publish_missing"))
        self.deps["npc_animations"].failure = "publish_clip"
        status, result = self.post("/api/npc-animations/sample/publish", {"description": "clip"})
        self.assertEqual((status, result), (400, {"error": "simulated store failure"}))

    def test_delete_binding_only_archives_once_by_store_contract(self):
        # The repository performs archival: routes must call it exactly once.
        for prefix, name in (
            ("/api/animation-bindings/", "animations"),
            ("/api/npc-animation-bindings/", "npc_animations"),
            ("/api/monster-animation-bindings/", "monster_animations"),
        ):
            with self.subTest(prefix=prefix):
                self.calls.clear()
                self.assertEqual(self.delete(prefix + "clip%2Fvariant")[0], 200)
                self.assertEqual(self.calls, [(name, "delete_binding", ("clip/variant",))])

    def test_delete_refuses_referenced_npc_monster_weapon_and_character(self):
        for path, guard_store, operation in (
            ("/api/npcs/warsmith", "npc_spawns", "delete_profile"),
            ("/api/monsters/guard", "monster_spawns", "delete_profile"),
            ("/api/weapons/sword", "npc_equipment", "delete"),
        ):
            with self.subTest(path=path):
                self.calls.clear()
                self.deps[guard_store].in_use = ["spawn-1"]
                status, result = self.delete(path)
                self.assertEqual(status, 400)
                self.assertIn("spawn", str(result).lower()) if guard_store != "npc_equipment" else self.assertIn("equipped", str(result))
                self.assertFalse(any(call[1] == operation for call in self.calls))
                self.deps[guard_store].in_use = []
        self.deps["animations"].usage = {"clips": 1, "bindings": 1}
        self.calls.clear()
        status, result = self.delete("/api/characters/hero")
        self.assertEqual(status, 400)
        self.assertFalse(any(call[1] == "delete" for call in self.calls))

    def test_unreferenced_deletion_and_failure_do_not_cross_domains(self):
        self.assertEqual(self.delete("/api/npcs/warsmith"), (200, {"ok": True}))
        self.assertEqual([c[:2] for c in self.calls], [
            ("npc_spawns", "monster_usage"),
            ("npc_animations", "delete_profile"),
            ("npcs", "delete"),
            ("npc_equipment", "delete"),
        ])
        self.calls.clear()
        self.deps["npc_animations"].failure = "delete_profile"
        status, result = self.delete("/api/npcs/warsmith")
        self.assertEqual(status, 400)
        self.assertFalse(any(c[0] == "npcs" and c[1] == "delete" for c in self.calls))

    def test_unknown_routes_do_not_parse_body_or_mutate_anything(self):
        def should_not_read():
            raise AssertionError("body read for non-matching route")
        self.assertEqual(dispatch_post("/api/undefined", should_not_read, self.deps), (404, {"error": "not found"}))
        self.assertEqual(dispatch_delete("/api/undefined", should_not_read, self.deps), (404, {"error": "not found"}))
        self.assertEqual(self.calls, [])

    def test_post_route_inventory_remains_registered(self):
        # Every write route present before extraction is still reachable. Input
        # validation errors are allowed; 404 means the route disappeared.
        paths = (
            "/api/animation-export/write", "/api/files/choose-character-model",
            "/api/files/choose-animation-folder", "/api/files/choose-npc-model",
            "/api/files/choose-npc-textures", "/api/files/choose-monster-model",
            "/api/files/choose-monster-textures", "/api/files/choose-weapon-model",
            "/api/files/choose-weapon-textures", "/api/files/choose-location-asset-model",
            "/api/files/choose-location-asset-texture", "/api/characters", "/api/weapons",
            "/api/location-assets", "/api/location-assets/layout", "/api/weapons/attack-movement",
            "/api/npcs", "/api/npc-spawns/place", "/api/npc-spawns/register",
            "/api/npc-spawns/select", "/api/npc-spawns/delete", "/api/npc-spawns/restore",
            "/api/npc-spawns/validate", "/api/monsters", "/api/monster-spawns/place",
            "/api/monster-spawns/register", "/api/monster-spawns/select",
            "/api/monster-spawns/delete", "/api/monster-spawns/restore",
            "/api/monster-spawns/validate", "/api/animation-speed-scaling/custom",
            "/api/animation-speed-scaling", "/api/options", "/api/locations/draw",
            "/api/locations/register", "/api/locations/select", "/api/locations/restore",
            "/api/locations/delete", "/api/locations/validate", "/api/timelines/open",
            "/api/timelines/editor-event", "/api/timelines/save",
            "/api/animations/check-roblox-assets", "/api/monster-animations/scan",
            "/api/monster-animations/assign", "/api/npc-equipment", "/api/npc-equipment/sync",
            "/api/npc-animations/scan", "/api/npc-animations/assign", "/api/animations/scan",
            "/api/animations/assign", "/api/characters/hero/stats",
            "/api/characters/hero/identity", "/api/characters/hero/replace-model",
            "/api/characters/hero/model", "/api/characters/hero/activate",
            "/api/characters/hero/publish", "/api/characters/hero/sync",
            "/api/characters/active/clear", "/api/npcs/hero/publish",
            "/api/npcs/hero/sync", "/api/npc-animations/clip/rename",
            "/api/npc-animations/clip/publish-missing", "/api/npc-animations/clip/publish",
            "/api/npc-animation-bindings/id/options", "/api/npc-animation-bindings/id/compatibility",
            "/api/npc-animation-bindings/id/disarm", "/api/npc-animation-bindings/id/weight",
            "/api/monsters/hero/publish", "/api/monsters/hero/sync",
            "/api/monster-animations/hero/publish-missing",
            "/api/monster-animations/hero/publish", "/api/monster-animation-bindings/id/weight",
            "/api/location-assets/hero/publish", "/api/weapons/hero/publish",
            "/api/weapons/hero/sync", "/api/weapons/hero/activate",
            "/api/weapons/active/clear", "/api/animations/hero/publish-missing",
            "/api/animations/hero/publish", "/api/animation-bindings/id/weight",
        )
        for path in paths:
            with self.subTest(path=path):
                status, _ = self.post(path)
                self.assertNotEqual(status, 404)

    def test_composition_root_supplies_every_injected_dependency(self):
        import ast
        code = (ROOT / "system/control-center/host_agent.py").read_text(encoding="utf-8")
        host = ast.parse(code)
        definition = next(node for node in host.body if isinstance(node, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "WRITE_SOURCES" for t in node.targets))
        provided = {key.value for key in definition.value.args[0].keys}
        requested = set()
        for module in ("write_files", "write_actors", "write_world", "write_animations", "delete_entities", "real_estate"):
            source = ast.parse((ROOT / f"system/control-center/api/{module}.py").read_text(encoding="utf-8"))
            for node in ast.walk(source):
                if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                    and node.value.id == "deps" and isinstance(node.slice, ast.Constant)):
                    requested.add(node.slice.value)
        self.assertEqual(requested, provided)

    def test_local_picker_stays_isolated_from_store_mutations(self):
        status, result = self.post("/api/files/choose-character-model")
        self.assertEqual(status, 200)
        self.assertEqual(result["path"], "C:/fixtures/file.rbxm")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
