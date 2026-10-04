from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs
import json
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
from character_core.identity import CharacterIdentityService
from studio_bridge import run_model_load_bridge

control_agent_build = "game1-m5-2-archetype-edit-001"
port = int(os.environ.get("CONTROL_AGENT_PORT", "43821"))
token = os.environ.get("CONTROL_TOKEN", "Game1LocalControlV1")
store = CharacterStore(ROOT)
animations = AnimationStore(ROOT)
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
    return {"character": row, "studio": result}


def _powershell_picker(script: str) -> str:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        raise RuntimeError("powershell was not found for the native picker")
    completed = subprocess.run(
        [powershell, "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        timeout=120,
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


def choose_animation_folder() -> str:
    return _powershell_picker(
        r'''
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'game1 · choose folder containing exported character animations (.rbxm/.rbxmx)'
$dialog.ShowNewFolderButton = $false
if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    Write-Output $dialog.SelectedPath
}
'''
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
        if path == "/api/files/choose-character-model":
            try:
                return self.out(200, {"path": choose_character_fbx()})
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/files/choose-animation-folder":
            try:
                return self.out(200, {"path": choose_animation_folder()})
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if path == "/api/characters":
            try:
                return self.out(200, store.register(self.body()))
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
        activate_suffix = "/activate"
        publish_suffix = "/publish"
        sync_suffix = "/sync"
        if path.startswith(prefix) and path.endswith(identity_suffix):
            character_id = unquote(path[len(prefix):-len(identity_suffix)].strip("/"))
            try:
                return self.out(200, character_identity.update(character_id, self.body()))
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
