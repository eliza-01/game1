from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from types import MappingProxyType
from urllib.parse import unquote, urlparse
import base64
import json
import re
import os
import shutil
import subprocess
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


def npc_place_spawn(payload: dict):
    # The Studio authoring preview needs the same published rig/textures that the
    # runtime will clone. Synchronize it before starting the viewport gesture.
    slug = str(payload.get("monsterSlug") or "").strip().lower()
    if not npc_spawns.readiness(slug)["ready"]:
        return npc_spawns.place(payload)  # Preserve the store's readiness error.
    sync_monster_to_studio(slug, kind="npc")
    return npc_spawns.place(payload)


def npc_register_spawn(payload: dict):
    slug = str(payload.get("monsterSlug") or "").strip().lower()
    sync_monster_to_studio(slug, kind="npc")
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


def sync_character_to_studio(character_id: str):
    row = store.get(character_id)
    if not row:
        raise ValueError(f"unknown character archetype: {character_id}")
    asset_id = str(row.get("model_asset_id") or "").strip()
    if not asset_id:
        raise ValueError("publish the character model before syncing it to Studio")
    destination = [
        "characters",
        str(row.get("race") or ""),
        str(row.get("gender") or ""),
        str(row.get("id") or ""),
        "model",
    ]
    result = run_model_load_bridge(asset_id, destination, wrapper_name=str(row.get("id") or ""))
    stats = result.get("rigStats") or {}
    if int(stats.get("baseParts") or 0) <= 0 or int(stats.get("bones") or 0) + int(stats.get("motor6Ds") or 0) <= 0:
        raise ValueError("Studio loaded a character asset without articulated BasePart geometry")

    try:
        expected_analysis = json.loads(str(row.get("skeleton_json") or "{}"))
    except Exception:
        expected_analysis = {}
    expected_names = {
        str(item.get("name") or "")
        for item in (expected_analysis.get("bones") or [])
        if str(item.get("name") or "")
    }
    actual_names = {str(name) for name in (stats.get("boneNames") or []) if str(name)}
    if expected_names and actual_names:
        missing = sorted(expected_names - actual_names, key=str.casefold)
        if missing:
            preview = ", ".join(missing[:20])
            suffix = " …" if len(missing) > 20 else ""
            raise ValueError(
                f"Roblox publication stripped {len(missing)} of {len(expected_names)} registered bones: {preview}{suffix}"
            )
    elif expected_names and int(stats.get("bones") or 0) < len(expected_names):
        raise ValueError(
            f"Roblox publication returned only {int(stats.get('bones') or 0)} of {len(expected_names)} registered bones"
        )
    return {"character": row, "studio": result}



def sync_weapon_to_studio(slug: str):
    row = weapons.get(slug)
    if not row:
        raise ValueError(f"unknown weapon: {slug}")
    asset_id = str(row.get("model_asset_id") or "").strip()
    if not asset_id:
        raise ValueError("publish the weapon model before syncing it to Studio")
    texture_assets = [
        {"slot": str(item.get("slot") or ""), "assetId": str(item.get("asset_id") or "")}
        for item in (row.get("textures") or [])
        if str(item.get("asset_id") or "").isdigit()
    ]
    destination = ["weapons", str(row.get("storage_type") or row.get("weapon_type") or ""), str(row.get("slug") or ""), "model"]
    result = run_model_load_bridge(
        asset_id,
        destination,
        wrapper_name=str(row.get("slug") or ""),
        placement_mode="weapon-pivot",
        metadata={
            "weaponSlug": str(row.get("slug") or ""),
            "weaponType": str(row.get("weapon_type") or ""),
            "rarity": str(row.get("rarity") or ""),
            "textures": texture_assets,
        },
    )
    return {"weapon": row, "studio": result}


def sync_monster_to_studio(slug: str, kind: str = "monster"):
    actor_store = npcs if kind == "npc" else monsters
    row = actor_store.get(slug)
    if not row:
        raise ValueError(f"unknown {kind}: {slug}")
    asset_id = str(row.get("model_asset_id") or "").strip()
    if not asset_id:
        raise ValueError(f"publish the {kind} model before syncing it to Studio")
    texture_assets = [
        {"slot": str(item.get("slot") or ""), "assetId": str(item.get("asset_id") or "")}
        for item in (row.get("textures") or [])
        if str(item.get("asset_id") or "").isdigit()
    ]
    destination = [f"{kind}s", str(row.get("slug") or ""), "model"]
    result = run_model_load_bridge(
        asset_id,
        destination,
        wrapper_name=str(row.get("slug") or ""),
        placement_mode="monster-rig",
        metadata={
            "monsterSlug": str(row.get("slug") or ""),
            "entityKind": kind,
            "expectedBones": [
                str(item.get("name"))
                for item in json.loads(str(row.get("skeleton_json") or "{}" )).get("bones", [])
                if str(item.get("name") or "")
            ],
            "textures": texture_assets,
        },
    )
    stats = result.get("rigStats") or {}
    if int(stats.get("baseParts") or 0) <= 0 or int(stats.get("bones") or 0) + int(stats.get("motor6Ds") or 0) <= 0:
        raise ValueError("Studio loaded a monster asset without an articulated rig")

    try:
        expected_analysis = json.loads(str(row.get("skeleton_json") or "{}"))
    except Exception:
        expected_analysis = {}
    expected_names = {
        str(item.get("name") or "")
        for item in (expected_analysis.get("bones") or [])
        if str(item.get("name") or "")
    }
    actual_names = {str(name) for name in (stats.get("boneNames") or []) if str(name)}
    if expected_names and actual_names:
        missing = sorted(expected_names - actual_names, key=str.casefold)
        if missing:
            preview = ", ".join(missing[:20])
            suffix = " …" if len(missing) > 20 else ""
            raise ValueError(
                f"Roblox monster publication stripped {len(missing)} of {len(expected_names)} registered bones: {preview}{suffix}"
            )
    elif expected_names and int(stats.get("bones") or 0) < len(expected_names):
        raise ValueError(
            f"Roblox monster publication returned only {int(stats.get('bones') or 0)} of {len(expected_names)} registered bones"
        )

    texture_stats = ((result.get("monsterStats") or {}).get("textures") or {})
    if texture_assets and int(texture_stats.get("applied") or 0) <= 0:
        raise ValueError("Studio loaded the monster rig but did not apply any published monster textures")
    return {"monster": row, "studio": result}

def _powershell_picker(script: str, extra_env: dict | None = None) -> str:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        raise RuntimeError("powershell was not found for the native picker")
    picker_env = os.environ.copy()
    if extra_env:
        picker_env.update({str(key): str(value) for key, value in extra_env.items()})
    completed = subprocess.run(
        [powershell, "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        timeout=120,
        env=picker_env,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "picker failed").strip())
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def choose_character_fbx() -> str:
    return _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose character fbx'
$dialog.Filter = 'fbx character model (*.fbx)|*.fbx'
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.FileName
}
'''
    )



def choose_weapon_fbx() -> str:
    return _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose weapon fbx'
$dialog.Filter = 'fbx weapon model (*.fbx)|*.fbx'
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.FileName
}
'''
    )


def choose_location_asset_fbx() -> str:
    return _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose location asset fbx'
$dialog.Filter = 'fbx location asset model (*.fbx)|*.fbx'
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.FileName
}
'''
    )


def choose_location_asset_texture() -> str:
    return _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose location asset texture'
$dialog.Filter = 'texture (*.png;*.jpg;*.jpeg)|*.png;*.jpg;*.jpeg|png texture (*.png)|*.png|jpeg texture (*.jpg;*.jpeg)|*.jpg;*.jpeg'
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.FileName
}
'''
    )


def choose_monster_fbx() -> str:
    return _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose monster fbx'
$dialog.Filter = 'fbx monster model (*.fbx)|*.fbx'
$dialog.Multiselect = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.FileName
}
'''
    )


def choose_monster_textures() -> list[str]:
    raw = _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose monster textures'
$dialog.Filter = 'monster textures (*.png;*.jpg;*.jpeg;*.webp)|*.png;*.jpg;*.jpeg;*.webp'
$dialog.Multiselect = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output ($dialog.FileNames -join [char]31)
}
'''
    )
    return [item for item in raw.split(chr(31)) if item]


def choose_weapon_textures() -> list[str]:
    raw = _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Title = 'game1 · choose weapon textures'
$dialog.Filter = 'weapon textures (*.png;*.jpg;*.jpeg;*.webp)|*.png;*.jpg;*.jpeg;*.webp'
$dialog.Multiselect = $true
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output ($dialog.FileNames -join [char]31)
}
'''
    )
    return [item for item in raw.split(chr(31)) if item]

def write_animation_export(payload: dict):
    output_dir = str(payload.get("outputDir") or "").strip()
    clip_name = str(payload.get("name") or "").strip()
    encoded = str(payload.get("rbxmBase64") or "").strip()

    if not output_dir:
        raise ValueError("animation export outputDir is required")
    if not clip_name:
        raise ValueError("animation export name is required")
    if not encoded:
        raise ValueError("animation export rbxmBase64 is required")

    directory = Path(output_dir).expanduser()
    if not directory.is_absolute():
        raise ValueError("animation export directory must be an absolute path")

    # Keep Unicode animation names, but remove characters Windows cannot use
    # in a filename and normalize trailing dots/spaces.
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', clip_name).strip().rstrip('. ')
    if not safe_name:
        safe_name = "animation"
    if not safe_name.lower().endswith(".rbxm"):
        safe_name += ".rbxm"

    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as error:
        raise ValueError(f"invalid animation rbxmBase64: {error}") from error
    if not raw:
        raise ValueError("serialized animation is empty")
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError("serialized animation exceeds 64 MiB")

    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / safe_name
    overwrote = destination.exists()
    temp = destination.with_suffix(destination.suffix + ".tmp")
    temp.write_bytes(raw)
    temp.replace(destination)
    return {
        "ok": True,
        "path": str(destination),
        "filename": destination.name,
        "overwrote": overwrote,
        "bytes": len(raw),
    }


def choose_animation_folder(initial_path: str = "") -> str:
    initial_path = str(initial_path or "").strip().strip('"')
    return _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'game1 · choose folder containing exported animations (.rbxm/.rbxmx)'
$dialog.ShowNewFolderButton = $false
$initialPath = $env:GAME1_ANIMATION_PICKER_INITIAL_PATH
if ($initialPath -and [System.IO.Directory]::Exists($initialPath)) {
    $dialog.SelectedPath = $initialPath
}
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.SelectedPath
}
'''
        , {"GAME1_ANIMATION_PICKER_INITIAL_PATH": initial_path}
    )


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
    "sync_character_to_studio": sync_character_to_studio,
    "sync_monster_to_studio": sync_monster_to_studio,
    "sync_weapon_to_studio": sync_weapon_to_studio,
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
