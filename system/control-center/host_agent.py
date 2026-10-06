from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs
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
from monster_spawn_store import MonsterSpawnStore
from animation_speed_scaling_store import AnimationSpeedScalingStore
from character_core.identity import CharacterIdentityService
from studio_bridge import run_model_load_bridge, run_monster_spawn_bridge

control_agent_build = "game1-m7-animation-folder-explorer-005"
port = int(os.environ.get("CONTROL_AGENT_PORT", "43821"))
token = os.environ.get("CONTROL_TOKEN", "Game1LocalControlV1")
store = CharacterStore(ROOT)
animations = AnimationStore(ROOT)
weapons = WeaponStore(ROOT)
monsters = MonsterStore(ROOT)
monster_animations = MonsterAnimationStore(ROOT)
monster_spawns = MonsterSpawnStore(ROOT, monsters, monster_animations, run_monster_spawn_bridge)
animation_speed_scaling = AnimationSpeedScalingStore(ROOT)
character_identity = CharacterIdentityService(ROOT, store, animations)


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
    destination = ["weapons", str(row.get("weapon_type") or ""), str(row.get("slug") or ""), "model"]
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


def sync_monster_to_studio(slug: str):
    row = monsters.get(slug)
    if not row:
        raise ValueError(f"unknown monster: {slug}")
    asset_id = str(row.get("model_asset_id") or "").strip()
    if not asset_id:
        raise ValueError("publish the monster model before syncing it to Studio")
    texture_assets = [
        {"slot": str(item.get("slot") or ""), "assetId": str(item.get("asset_id") or "")}
        for item in (row.get("textures") or [])
        if str(item.get("asset_id") or "").isdigit()
    ]
    destination = ["monsters", str(row.get("slug") or ""), "model"]
    result = run_model_load_bridge(
        asset_id,
        destination,
        wrapper_name=str(row.get("slug") or ""),
        placement_mode="monster-rig",
        metadata={
            "monsterSlug": str(row.get("slug") or ""),
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
        parsed = self.parsed()
        path = parsed.path
        if path == "/api/agent/info":
            return self.out(200, {
                "build": control_agent_build,
                "project": "game1",
                "projectRoot": str(ROOT),
                "db": str(store.db),
                "publication": publication_config(),
            })
        if path == "/api/characters":
            snapshot = store.snapshot()
            snapshot["publication"] = publication_config()
            return self.out(200, snapshot)
        if path == "/api/animations":
            character_id = str((parse_qs(parsed.query).get("character") or [""])[0]).strip().lower()
            snapshot = animations.snapshot(character_id or store.active_id())
            snapshot["publication"] = publication_config()
            return self.out(200, snapshot)
        if path == "/api/weapons":
            snapshot = weapons.snapshot()
            snapshot["publication"] = publication_config()
            return self.out(200, snapshot)
        if path == "/api/monsters":
            snapshot = monsters.snapshot()
            snapshot["publication"] = publication_config()
            return self.out(200, snapshot)
        if path == "/api/monster-animations":
            slug = str((parse_qs(parsed.query).get("monster") or [""])[0]).strip().lower()
            snapshot = monster_animations.snapshot(slug)
            snapshot["publication"] = publication_config()
            return self.out(200, snapshot)
        if path == "/api/monster-spawns":
            try:
                return self.out(200, monster_spawns.snapshot())
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/animation-speed-scaling":
            try:
                return self.out(200, animation_speed_scaling.snapshot())
            except Exception as error:
                return self.out(400, {"error": str(error)})
        monster_prefix = "/api/monsters/"
        publications_suffix = "/publications"
        if path.startswith(monster_prefix) and path.endswith(publications_suffix):
            slug = unquote(path[len(monster_prefix):-len(publications_suffix)].strip("/"))
            return self.out(200, {"items": monsters.publications(slug)})
        weapon_prefix = "/api/weapons/"
        if path.startswith(weapon_prefix) and path.endswith(publications_suffix):
            slug = unquote(path[len(weapon_prefix):-len(publications_suffix)].strip("/"))
            return self.out(200, {"items": weapons.publications(slug)})
        prefix = "/api/characters/"
        suffix = "/publications"
        if path.startswith(prefix) and path.endswith(suffix):
            character_id = unquote(path[len(prefix):-len(suffix)].strip("/"))
            return self.out(200, {"items": store.publications(character_id)})
        return self.out(404, {"error": "not found"})

    def do_POST(self):
        if not self.auth():
            return self.out(401, {"error": "unauthorized"})
        path = self.parsed().path
        if path == "/api/animation-export/write":
            try:
                return self.out(200, write_animation_export(self.body()))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/files/choose-character-model":
            try:
                return self.out(200, {"path": choose_character_fbx()})
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/files/choose-animation-folder":
            try:
                payload = self.body()
                return self.out(200, {"path": choose_animation_folder(str(payload.get("initialPath") or ""))})
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/files/choose-monster-model":
            try:
                return self.out(200, {"path": choose_monster_fbx()})
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/files/choose-monster-textures":
            try:
                return self.out(200, {"paths": choose_monster_textures()})
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/files/choose-weapon-model":
            try:
                return self.out(200, {"path": choose_weapon_fbx()})
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/files/choose-weapon-textures":
            try:
                return self.out(200, {"paths": choose_weapon_textures()})
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/characters":
            try:
                return self.out(200, store.register(self.body()))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/weapons":
            try:
                return self.out(200, weapons.register(self.body()))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/monsters":
            try:
                return self.out(200, monsters.register(self.body()))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/monster-spawns/place":
            try:
                return self.out(200, monster_spawns.place(self.body()))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/monster-spawns/register":
            try:
                payload = self.body()
                slug = str(payload.get("monsterSlug") or "").strip().lower()
                sync_monster_to_studio(slug)
                return self.out(200, monster_spawns.register(payload))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/monster-spawns/select":
            try:
                return self.out(200, monster_spawns.select(self.body()))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/monster-spawns/delete":
            try:
                return self.out(200, monster_spawns.delete(self.body()))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/monster-spawns/restore":
            try:
                return self.out(200, monster_spawns.restore())
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/monster-spawns/validate":
            try:
                return self.out(200, monster_spawns.validate())
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/animation-speed-scaling":
            try:
                return self.out(200, animation_speed_scaling.update(self.body()))
            except Exception as error:
                return self.out(400, {"error": str(error)})

        if path == "/api/monster-animations/scan":
            try:
                payload = self.body()
                return self.out(200, monster_animations.scan_folder(str(payload.get("monsterSlug") or ""), str(payload.get("rootPath") or "")))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/monster-animations/assign":
            try:
                payload = self.body()
                return self.out(200, monster_animations.assign_file(
                    str(payload.get("monsterSlug") or ""), str(payload.get("sourcePath") or ""),
                    str(payload.get("slot") or ""), int(payload.get("variant") or 0),
                ))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/animations/scan":
            try:
                payload = self.body()
                return self.out(200, animations.scan_folder(str(payload.get("characterId") or ""), str(payload.get("rootPath") or "")))
            except Exception as error:
                return self.out(400, {"error": str(error)})

        if path == "/api/animations/assign":
            try:
                payload = self.body()
                return self.out(200, animations.assign_file(
                    str(payload.get("characterId") or ""),
                    str(payload.get("sourcePath") or ""),
                    str(payload.get("scope") or ""),
                    str(payload.get("weaponSet") or ""),
                    str(payload.get("slot") or ""),
                    int(payload.get("variant") or 0),
                ))
            except Exception as error:
                return self.out(400, {"error": str(error)})

        prefix = "/api/characters/"
        identity_suffix = "/identity"
        replace_model_suffix = "/replace-model"
        model_suffix = "/model"
        activate_suffix = "/activate"
        publish_suffix = "/publish"
        sync_suffix = "/sync"
        if path.startswith(prefix) and path.endswith(identity_suffix):
            character_id = unquote(path[len(prefix):-len(identity_suffix)].strip("/"))
            try:
                return self.out(200, character_identity.update(character_id, self.body()))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path.startswith(prefix) and path.endswith(replace_model_suffix):
            character_id = unquote(path[len(prefix):-len(replace_model_suffix)].strip("/"))
            try:
                payload = self.body()
                source_path = str(payload.get("sourcePath") or "").strip()
                if not source_path:
                    raise ValueError("choose a replacement FBX first")
                before = store.get(character_id)
                if not before:
                    raise ValueError(f"unknown character archetype: {character_id}")
                previous_asset_id = str(before.get("model_asset_id") or "").strip()

                # Stage/analyze the new canonical FBX while the old Roblox asset
                # remains assigned. publish() creates a NEW asset for changed
                # character content and switches the archetype id only on success.
                store.register({
                    "existingId": character_id,
                    "id": character_id,
                    "displayName": before.get("display_name") or "",
                    "race": before.get("race") or "",
                    "gender": before.get("gender") or "",
                    "sourcePath": source_path,
                    # Replace is explicit user intent. Never collapse it into the
                    # unchanged-content no-op used by ordinary Publish.
                    "forceReplacement": True,
                })
                credentials = publication_credentials(str(payload.get("description") or "game1 character model"))
                published = store.publish(character_id, credentials)
                result = {"character": published, "studio": None, "studioError": ""}
                try:
                    synced = sync_character_to_studio(character_id)
                    result["studio"] = synced.get("studio")
                except Exception as studio_error:
                    # Publication already succeeded and the new asset id is now
                    # canonical. Do not report the whole replacement as failed
                    # merely because Studio refresh needs a retry.
                    result["studioError"] = str(studio_error)
                result["previousAssetId"] = previous_asset_id
                result["newAssetId"] = str(published.get("model_asset_id") or "")
                result["assetReplaced"] = bool(
                    result["newAssetId"] and result["newAssetId"] != previous_asset_id
                )
                if previous_asset_id and not result["assetReplaced"]:
                    raise RuntimeError(
                        "replace model did not create a new Roblox asset id; old asset remains assigned"
                    )
                return self.out(200, result)
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path.startswith(prefix) and path.endswith(model_suffix):
            character_id = unquote(path[len(prefix):-len(model_suffix)].strip("/"))
            try:
                payload = self.body()
                source_character_id = str(payload.get("sourceCharacterId") or "").strip().lower()
                return self.out(200, store.assign_model(character_id, source_character_id))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path.startswith(prefix) and path.endswith(activate_suffix):
            character_id = unquote(path[len(prefix):-len(activate_suffix)].strip("/"))
            try:
                return self.out(200, store.set_active(character_id))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path.startswith(prefix) and path.endswith(publish_suffix):
            character_id = unquote(path[len(prefix):-len(publish_suffix)].strip("/"))
            try:
                payload = self.body()
                credentials = publication_credentials(str(payload.get("description") or ""))
                row = store.publish(character_id, credentials)
                return self.out(200, sync_character_to_studio(str(row["id"])))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path.startswith(prefix) and path.endswith(sync_suffix):
            character_id = unquote(path[len(prefix):-len(sync_suffix)].strip("/"))
            try:
                return self.out(200, sync_character_to_studio(character_id))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/characters/active/clear":
            return self.out(200, store.clear_active())

        monster_prefix = "/api/monsters/"
        monster_publish_suffix = "/publish"
        monster_sync_suffix = "/sync"
        if path.startswith(monster_prefix) and path.endswith(monster_publish_suffix):
            slug = unquote(path[len(monster_prefix):-len(monster_publish_suffix)].strip("/"))
            try:
                payload = self.body()
                credentials = publication_credentials(str(payload.get("description") or "game1 monster"))
                return self.out(200, monsters.publish(slug, credentials))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path.startswith(monster_prefix) and path.endswith(monster_sync_suffix):
            slug = unquote(path[len(monster_prefix):-len(monster_sync_suffix)].strip("/"))
            try:
                return self.out(200, sync_monster_to_studio(slug))
            except Exception as error:
                return self.out(400, {"error": str(error)})

        monster_animation_prefix = "/api/monster-animations/"
        monster_publish_missing_suffix = "/publish-missing"
        monster_publish_animation_suffix = "/publish"
        if path.startswith(monster_animation_prefix) and path.endswith(monster_publish_missing_suffix):
            slug = unquote(path[len(monster_animation_prefix):-len(monster_publish_missing_suffix)].strip("/"))
            try:
                payload = self.body()
                credentials = publication_credentials(str(payload.get("description") or "game1 monster animation"))
                return self.out(200, monster_animations.publish_missing(slug, credentials))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path.startswith(monster_animation_prefix) and path.endswith(monster_publish_animation_suffix):
            clip_id = unquote(path[len(monster_animation_prefix):-len(monster_publish_animation_suffix)].strip("/"))
            try:
                payload = self.body()
                credentials = publication_credentials(str(payload.get("description") or "game1 monster animation"))
                return self.out(200, monster_animations.publish_clip(clip_id, credentials))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        monster_binding_prefix = "/api/monster-animation-bindings/"
        if path.startswith(monster_binding_prefix) and path.endswith("/weight"):
            binding_id = unquote(path[len(monster_binding_prefix):-len("/weight")].strip("/"))
            try:
                payload = self.body()
                return self.out(200, monster_animations.set_weight(binding_id, int(payload.get("weight") or 100)))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        weapon_prefix = "/api/weapons/"
        weapon_publish_suffix = "/publish"
        weapon_sync_suffix = "/sync"
        weapon_activate_suffix = "/activate"
        if path.startswith(weapon_prefix) and path.endswith(weapon_publish_suffix):
            slug = unquote(path[len(weapon_prefix):-len(weapon_publish_suffix)].strip("/"))
            try:
                payload = self.body()
                credentials = publication_credentials(str(payload.get("description") or "game1 weapon"))
                return self.out(200, weapons.publish(slug, credentials))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path.startswith(weapon_prefix) and path.endswith(weapon_sync_suffix):
            slug = unquote(path[len(weapon_prefix):-len(weapon_sync_suffix)].strip("/"))
            try:
                return self.out(200, sync_weapon_to_studio(slug))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path.startswith(weapon_prefix) and path.endswith(weapon_activate_suffix):
            slug = unquote(path[len(weapon_prefix):-len(weapon_activate_suffix)].strip("/"))
            try:
                return self.out(200, weapons.set_active(slug))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/weapons/active/clear":
            return self.out(200, weapons.clear_active())
        animation_prefix = "/api/animations/"
        publish_missing_suffix = "/publish-missing"
        publish_animation_suffix = "/publish"
        if path.startswith(animation_prefix) and path.endswith(publish_missing_suffix):
            character_id = unquote(path[len(animation_prefix):-len(publish_missing_suffix)].strip("/"))
            try:
                payload = self.body()
                credentials = publication_credentials(str(payload.get("description") or "game1 character animation"))
                return self.out(200, animations.publish_missing(character_id, credentials))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path.startswith(animation_prefix) and path.endswith(publish_animation_suffix):
            clip_id = unquote(path[len(animation_prefix):-len(publish_animation_suffix)].strip("/"))
            try:
                payload = self.body()
                credentials = publication_credentials(str(payload.get("description") or "game1 character animation"))
                return self.out(200, animations.publish_clip(clip_id, credentials))
            except Exception as error:
                return self.out(400, {"error": str(error)})

        binding_prefix = "/api/animation-bindings/"
        weight_suffix = "/weight"
        if path.startswith(binding_prefix) and path.endswith(weight_suffix):
            binding_id = unquote(path[len(binding_prefix):-len(weight_suffix)].strip("/"))
            try:
                payload = self.body()
                return self.out(200, animations.set_weight(binding_id, int(payload.get("weight") or 100)))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        return self.out(404, {"error": "not found"})

    def do_DELETE(self):
        if not self.auth():
            return self.out(401, {"error": "unauthorized"})
        path = self.parsed().path
        binding_prefix = "/api/animation-bindings/"
        if path.startswith(binding_prefix):
            try:
                return self.out(200, animations.delete_binding(unquote(path[len(binding_prefix):])))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        monster_binding_prefix = "/api/monster-animation-bindings/"
        if path.startswith(monster_binding_prefix):
            try:
                return self.out(200, monster_animations.delete_binding(unquote(path[len(monster_binding_prefix):])))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        monster_prefix = "/api/monsters/"
        if path.startswith(monster_prefix):
            slug = unquote(path[len(monster_prefix):])
            try:
                spawn_ids = monster_spawns.monster_usage(slug)
                if spawn_ids:
                    raise ValueError("delete monster spawns first: " + ", ".join(spawn_ids[:8]))
                monster_animations.delete_profile(slug)
                monsters.delete(slug)
                return self.out(200, {"ok": True})
            except Exception as error:
                return self.out(400, {"error": str(error)})
        weapon_prefix = "/api/weapons/"
        if path.startswith(weapon_prefix):
            slug = unquote(path[len(weapon_prefix):])
            try:
                weapons.delete(slug)
                return self.out(200, {"ok": True})
            except Exception as error:
                return self.out(400, {"error": str(error)})
        prefix = "/api/characters/"
        if path.startswith(prefix):
            character_id = unquote(path[len(prefix):])
            try:
                usage = animations.character_usage(character_id)
                if usage["clips"] or usage["bindings"]:
                    raise ValueError(
                        f"delete the character animation profile first: {usage['clips']} clip(s), {usage['bindings']} binding(s)"
                    )
                store.delete(character_id)
                animations.delete_empty_profile(character_id)
                return self.out(200, {"ok": True})
            except Exception as error:
                return self.out(400, {"error": str(error)})
        return self.out(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        print("[host-agent]", fmt % args)


if __name__ == "__main__":
    print(f"[game1] control agent http://127.0.0.1:{port} · {ROOT}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
