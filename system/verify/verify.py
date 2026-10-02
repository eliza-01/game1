from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
errors = []


def err(message: str) -> None:
    errors.append(message)


if "robloxlineage" in str(ROOT).lower():
    err("game1 root is inside/a descendant of a robloxlineage path")

project = json.loads((ROOT / "default.project.json").read_text(encoding="utf-8"))
if project.get("name") != "game1":
    err("default.project.json project name must be game1")

tree = project.get("tree", {})
try:
    if "Game1Shared" not in tree["ReplicatedStorage"]:
        err("Game1Shared namespace missing")
    if "Game1Server" not in tree["ServerScriptService"]:
        err("Game1Server namespace missing")
    if "Game1Client" not in tree["StarterPlayer"]["StarterPlayerScripts"]:
        err("Game1Client namespace missing")
except (KeyError, TypeError):
    err("default.project.json namespace tree is malformed")

manifest = json.loads((ROOT / "assets/manifests/character-archetypes.json").read_text(encoding="utf-8"))
if manifest.get("project") != "game1":
    err("character manifest identity must be game1")
if manifest.get("schemaVersion") != 2:
    err("character manifest schema must be 2")

archetypes = manifest.get("archetypes", [])
if not isinstance(archetypes, list):
    err("character archetypes must be a list")
    archetypes = []

ids = {str(row.get("id", "")) for row in archetypes if isinstance(row, dict)}
active_id = manifest.get("activeArchetypeId")
if active_id is not None and active_id not in ids:
    err("active character archetype must exist in the manifest")

for row in archetypes:
    if not isinstance(row, dict):
        err("character archetype row must be an object")
        continue
    if not isinstance(row.get("model"), dict):
        err(f"character archetype {row.get('id')} must have one model object")

if (ROOT / "place/current.rbxl").exists():
    err("place/current.rbxl is forbidden in game1; canonical file is place/game1.rbxl")

scan = [ROOT / "src", ROOT / "assets/manifests", ROOT / "system/control-center", ROOT / "config"]
for base in scan:
    for path in base.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".luau", ".lua", ".py", ".json", ".yaml", ".yml"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in [
                "RobloxLineageShared",
                "RobloxLineageServer",
                "RobloxLineageClient",
                "NewPlaceShared",
                "NewPlaceServer",
                "NewPlaceClient",
                "Interlude",
                "CombatV2",
            ]:
                if token in text:
                    err(f"{path.relative_to(ROOT)} contains forbidden token {token}")

for path in (ROOT / "src").rglob("*.luau"):
    text = path.read_text(encoding="utf-8", errors="ignore")
    if "human/fighter/female" in text:
        err(f"{path.relative_to(ROOT)} contains old archetype path")

cfg = json.loads((ROOT / "config/project.json").read_text(encoding="utf-8"))
if cfg.get("name") != "game1" or cfg.get("slug") != "game1":
    err("config/project.json identity must be game1")

expected_namespaces = {
    "shared": "Game1Shared",
    "server": "Game1Server",
    "client": "Game1Client",
    "remotes": "Game1Remotes",
}
if cfg.get("namespaces") != expected_namespaces:
    err("config/project.json namespaces do not match game1 contract")

ports = cfg.get("ports", {})
old = {43720, 43721, 34872, 43127}
if old & set(ports.values()):
    err("port collision with robloxlineage baseline")
if ports.get("rojo") != 34882:
    err("game1 rojo port must be 34882")

damage_text = (ROOT / "src/server/DamageService.luau").read_text(encoding="utf-8")
if "math.max(0, math.floor(normalizedRawDamage - defense))" not in damage_text:
    err("damage formula contract missing")

attack_text = (ROOT / "src/server/AttackService.luau").read_text(encoding="utf-8")
dummy_text = (ROOT / "src/server/TrainingDummyService.luau").read_text(encoding="utf-8")
if "[game1][ATTACK] HIT" not in attack_text or "[game1][ATTACK] MISS" not in attack_text:
    err("attack smoke-test logging contract missing")
if "BillboardGui" not in dummy_text or "HP %d/%d" not in dummy_text:
    err("training dummy visible hp contract missing")

registry_text = (ROOT / "src/shared/CharacterRegistry.luau").read_text(encoding="utf-8")
if "activeArchetypeId" not in registry_text:
    err("generated character registry has no active archetype field")
if archetypes and "model = table.freeze" not in registry_text:
    err("generated character registry does not expose the m2 model contract")

schema_text = (ROOT / "system/control-center/schema.sql").read_text(encoding="utf-8")
if "project_settings" not in schema_text:
    err("control center settings table missing")

if errors:
    print("verify failed")
    for item in errors:
        print(" -", item)
    sys.exit(1)

print("verify ok · game1 m2 character contracts passed")
print("registered character archetypes:", len(archetypes))
print("active character archetype:", active_id or "none")
print("canonical place:", "place/game1.rbxl")
