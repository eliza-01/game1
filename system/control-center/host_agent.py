from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from types import MappingProxyType
from urllib.parse import unquote, urlparse
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[2]


def load_local_env(path: Path):
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env(ROOT / ".env.local")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from character_store import CharacterStore
from animation_store import AnimationStore
from weapon_store import WeaponStore
from monster_store import MonsterStore
from monster_animation_store import MonsterAnimationStore
from npc_equipment_store import NpcEquipmentStore
from monster_spawn_store import MonsterSpawnStore
from animation_speed_scaling_store import AnimationSpeedScalingStore
from options_store import OptionsStore
from timeline_store import TimelineStore
from location_store import LocationStore
from location_asset_store import LocationAssetStore
from deco_layout_store import DecoLayoutStore
from studio_save import request_active_studio_save
from character_core.identity import CharacterIdentityService
from studio_bridge import run_model_load_bridge, run_monster_spawn_bridge, run_timeline_editor_bridge, run_location_authoring_bridge
from services.studio_asset_sync import StudioAssetSyncService
from services.animation_export import write_animation_export
from services.native_pickers import (
    choose_animation_folder, choose_character_fbx, choose_location_asset_fbx,
    choose_location_asset_texture, choose_monster_fbx, choose_monster_textures,
    choose_weapon_fbx, choose_weapon_textures,
)
from api.read_dispatch import dispatch as dispatch_read_request
from api.write_dispatch import dispatch_post as dispatch_write_request, dispatch_delete as dispatch_delete_request
from source_only_assets import migrate_source_only_assets

migrate_source_only_assets(ROOT, ROOT / ".control-center" / "game1.db")

control_agent_build = "game1-m50-environment-weapon-bounce-001"
port = int(os.environ.get("CONTROL_AGENT_PORT", "43821"))
token = os.environ.get("CONTROL_TOKEN", "Game1LocalControlV1")
store = CharacterStore(ROOT)
animations = AnimationStore(ROOT)
weapons = WeaponStore(ROOT)
monsters = MonsterStore(ROOT)
monster_animations = MonsterAnimationStore(ROOT)
monster_spawns = MonsterSpawnStore(ROOT, monsters, monster_animations, run_monster_spawn_bridge)
# NPC data uses the same proven asset pipelines, with its own SQLite DB and runtime registries.
npcs = MonsterStore(ROOT, kind="npc")
npc_animations = MonsterAnimationStore(ROOT, kind="npc")
npc_equipment = NpcEquipmentStore(ROOT, npcs, weapons)
def run_npc_spawn_bridge(action, **kwargs):
    return run_monster_spawn_bridge(action, entity_kind="npc", **kwargs)
npc_spawns = MonsterSpawnStore(ROOT, npcs, npc_animations, run_npc_spawn_bridge, kind="npc")
animation_speed_scaling = AnimationSpeedScalingStore(ROOT)
options_store = OptionsStore(ROOT)
timelines = TimelineStore(ROOT, store, animations, monsters, monster_animations)
locations = LocationStore(ROOT, run_location_authoring_bridge)
location_assets = LocationAssetStore(ROOT)
deco_layouts = DecoLayoutStore(ROOT)
character_identity = CharacterIdentityService(ROOT, store, animations)
studio_asset_sync = StudioAssetSyncService(
    characters=store, weapons=weapons, monsters=monsters, npcs=npcs,
    load_model=run_model_load_bridge,
)


def npc_place_spawn(payload: dict):
    # The Studio authoring preview needs the same published rig/textures that the
    # runtime will clone. Synchronize it before starting the viewport gesture.
    slug = str(payload.get("monsterSlug") or "").strip().lower()
    if not npc_spawns.readiness(slug)["ready"]:
        return npc_spawns.place(payload)  # Preserve the store's readiness error.
    studio_asset_sync.sync_monster_to_studio(slug, kind="npc")
    return npc_spawns.place(payload)


def npc_register_spawn(payload: dict):
    slug = str(payload.get("monsterSlug") or "").strip().lower()
    studio_asset_sync.sync_monster_to_studio(slug, kind="npc")
    return npc_spawns.register(payload)


def publication_config():
    creator_type = str(os.environ.get("roblox_creator_type") or os.environ.get("ROBLOX_CREATOR_TYPE") or "").strip().lower()
    creator_id = str(os.environ.get("roblox_creator_id") or os.environ.get("ROBLOX_CREATOR_ID") or "").strip()
    api_key = str(os.environ.get("roblox_open_cloud_api_key") or os.environ.get("ROBLOX_OPEN_CLOUD_API_KEY") or "").strip()
    return {
        "configured": bool(api_key and creator_type in {"user", "group"} and creator_id.isdigit()),
        "creatorType": creator_type,
        "creatorId": creator_id,
        "apiKeyConfigured": bool(api_key),
    }


def publication_credentials(description: str = ""):
    config = publication_config()
    if not config["configured"]:
        raise ValueError(
            "open cloud publication is not configured. set roblox_open_cloud_api_key, roblox_creator_type and roblox_creator_id in .env.local"
        )
    return {
        "apiKey": str(os.environ.get("roblox_open_cloud_api_key") or os.environ.get("ROBLOX_OPEN_CLOUD_API_KEY") or "").strip(),
        "creatorType": config["creatorType"],
        "creatorId": config["creatorId"],
        "description": description,
    }


# Application composition root for read-only HTTP adapters. Built once, not per request.
READ_SOURCES = MappingProxyType({
    "characters": store, "animations": animations,
    "weapons": weapons, "monsters": monsters, "monster_animations": monster_animations,
    "npcs": npcs, "npc_animations": npc_animations, "npc_equipment": npc_equipment,
    "location_assets": location_assets, "npc_spawns": npc_spawns,
    "monster_spawns": monster_spawns, "animation_speed_scaling": animation_speed_scaling,
    "options": options_store, "timelines": timelines, "locations": locations,
    "publication_config": publication_config,
})


# Explicit application dependencies for write-side domain routes. Routes do not
# import host_agent or instantiate production stores, so unit tests can replace
# these with in-memory fakes without touching SQLite, Roblox, or the filesystem.
WRITE_SOURCES = MappingProxyType({
    "animation_speed_scaling": animation_speed_scaling,
    "animations": animations,
    "character_identity": character_identity,
    "choose_animation_folder": choose_animation_folder,
    "choose_character_fbx": choose_character_fbx,
    "choose_location_asset_fbx": choose_location_asset_fbx,
    "choose_location_asset_texture": choose_location_asset_texture,
    "choose_monster_fbx": choose_monster_fbx,
    "choose_monster_textures": choose_monster_textures,
    "choose_weapon_fbx": choose_weapon_fbx,
    "choose_weapon_textures": choose_weapon_textures,
    "deco_layouts": deco_layouts,
    "location_assets": location_assets,
    "locations": locations,
    "monster_animations": monster_animations,
    "monster_spawns": monster_spawns,
    "monsters": monsters,
    "npc_animations": npc_animations,
    "npc_equipment": npc_equipment,
    "npc_place_spawn": npc_place_spawn,
    "npc_register_spawn": npc_register_spawn,
    "npc_spawns": npc_spawns,
    "npcs": npcs,
    "options_store": options_store,
    "publication_credentials": publication_credentials,
    "request_active_studio_save": request_active_studio_save,
    "run_timeline_editor_bridge": run_timeline_editor_bridge,
    "store": store,
    "sync_character_to_studio": studio_asset_sync.sync_character_to_studio,
    "sync_monster_to_studio": studio_asset_sync.sync_monster_to_studio,
    "sync_weapon_to_studio": studio_asset_sync.sync_weapon_to_studio,
    "timelines": timelines,
    "weapons": weapons,
    "write_animation_export": write_animation_export,
})


def read_host_info():
    return {
        "build": control_agent_build, "project": "game1", "projectRoot": str(ROOT),
        "db": str(store.db), "publication": publication_config(),
    }


class Handler(BaseHTTPRequestHandler):
    def out(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def auth(self):
        return self.headers.get("X-Control-Token") == token

    def body(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def parsed(self):
        return urlparse(self.path)

    def do_GET(self):
        if not self.auth():
            return self.out(401, {"error": "unauthorized"})
        status, payload = dispatch_read_request(self.parsed(), READ_SOURCES, read_host_info)
        return self.out(status, payload)

    def do_POST(self):
        if not self.auth():
            return self.out(401, {"error": "unauthorized"})
        status, payload = dispatch_write_request(self.parsed().path, self.body, WRITE_SOURCES)
        return self.out(status, payload)

    def do_DELETE(self):
        if not self.auth():
            return self.out(401, {"error": "unauthorized"})
        status, payload = dispatch_delete_request(self.parsed().path, self.body, WRITE_SOURCES)
        return self.out(status, payload)

    def log_message(self, fmt, *args):
        print("[host-agent]", fmt % args)


if __name__ == "__main__":
    print(f"[game1] control agent http://127.0.0.1:{port} · {ROOT}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
