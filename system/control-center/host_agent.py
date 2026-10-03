from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote
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
from studio_bridge import run_model_load_bridge

control_agent_build = "game1-m4-canonical-character-root-001"
port = int(os.environ.get("CONTROL_AGENT_PORT", "43821"))
token = os.environ.get("CONTROL_TOKEN", "Game1LocalControlV1")
store = CharacterStore(ROOT)


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
        "description": description or "game1 character model",
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
    result = run_model_load_bridge(
        asset_id,
        destination,
        wrapper_name=str(row.get("id") or ""),
    )
    stats = result.get("rigStats") or {}
    if int(stats.get("baseParts") or 0) <= 0 or int(stats.get("bones") or 0) + int(stats.get("motor6Ds") or 0) <= 0:
        raise ValueError("Studio loaded a character asset without articulated BasePart geometry")
    return {"character": row, "studio": result}


def choose_character_fbx() -> str:
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        raise RuntimeError("powershell was not found for the native file picker")
    script = r'''
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
    completed = subprocess.run(
        [powershell, "-NoProfile", "-STA", "-Command", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "file picker failed").strip())
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


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

    def do_GET(self):
        if not self.auth():
            return self.out(401, {"error": "unauthorized"})
        if self.path == "/api/agent/info":
            return self.out(
                200,
                {
                    "build": control_agent_build,
                    "project": "game1",
                    "projectRoot": str(ROOT),
                    "db": str(store.db),
                    "publication": publication_config(),
                },
            )
        if self.path == "/api/characters":
            snapshot = store.snapshot()
            snapshot["publication"] = publication_config()
            return self.out(200, snapshot)
        prefix = "/api/characters/"
        suffix = "/publications"
        if self.path.startswith(prefix) and self.path.endswith(suffix):
            character_id = unquote(self.path[len(prefix) : -len(suffix)].strip("/"))
            return self.out(200, {"items": store.publications(character_id)})
        return self.out(404, {"error": "not found"})

    def do_POST(self):
        if not self.auth():
            return self.out(401, {"error": "unauthorized"})
        if self.path == "/api/files/choose-character-model":
            try:
                return self.out(200, {"path": choose_character_fbx()})
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if self.path == "/api/characters":
            try:
                return self.out(200, store.register(self.body()))
            except Exception as error:
                return self.out(400, {"error": str(error)})

        prefix = "/api/characters/"
        activate_suffix = "/activate"
        publish_suffix = "/publish"
        if self.path.startswith(prefix) and self.path.endswith(activate_suffix):
            character_id = unquote(self.path[len(prefix) : -len(activate_suffix)].strip("/"))
            try:
                return self.out(200, store.set_active(character_id))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if self.path.startswith(prefix) and self.path.endswith(publish_suffix):
            character_id = unquote(self.path[len(prefix) : -len(publish_suffix)].strip("/"))
            try:
                payload = self.body()
                credentials = publication_credentials(str(payload.get("description") or ""))
                row = store.publish(character_id, credentials)
                return self.out(200, sync_character_to_studio(str(row["id"])))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        sync_suffix = "/sync"
        if self.path.startswith(prefix) and self.path.endswith(sync_suffix):
            character_id = unquote(self.path[len(prefix) : -len(sync_suffix)].strip("/"))
            try:
                return self.out(200, sync_character_to_studio(character_id))
            except Exception as error:
                return self.out(400, {"error": str(error)})
        if self.path == "/api/characters/active/clear":
            return self.out(200, store.clear_active())
        return self.out(404, {"error": "not found"})

    def do_DELETE(self):
        if not self.auth():
            return self.out(401, {"error": "unauthorized"})
        prefix = "/api/characters/"
        if self.path.startswith(prefix):
            store.delete(unquote(self.path[len(prefix) :]))
            return self.out(200, {"ok": True})
        return self.out(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        print("[host-agent]", fmt % args)


if __name__ == "__main__":
    print(f"[game1] control agent http://127.0.0.1:{port} · {ROOT}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
