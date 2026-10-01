from pathlib import Path
import json, sys

ROOT = Path(__file__).resolve().parents[2]
errors = []

def err(message: str) -> None:
    errors.append(message)

if 'robloxlineage' in str(ROOT).lower():
    err("game1 root is inside/a descendant of a RobloxLineage path")

project = json.loads((ROOT / 'default.project.json').read_text(encoding='utf-8'))
if project.get('name') != 'game1':
    err('default.project.json project name must be game1')

tree = project.get('tree', {})
try:
    if 'Game1Shared' not in tree['ReplicatedStorage']:
        err('Game1Shared namespace missing')
    if 'Game1Server' not in tree['ServerScriptService']:
        err('Game1Server namespace missing')
    if 'Game1Client' not in tree['StarterPlayer']['StarterPlayerScripts']:
        err('Game1Client namespace missing')
except (KeyError, TypeError):
    err('default.project.json namespace tree is malformed')

manifest = json.loads((ROOT / 'assets/manifests/character-archetypes.json').read_text(encoding='utf-8'))
if manifest.get('project') != 'game1':
    err('character manifest identity must be game1')

# current.rbxl is intentionally forbidden: game1 uses a clearly named Place file.
if (ROOT / 'place/current.rbxl').exists():
    err('place/current.rbxl is forbidden in game1; canonical file is place/game1.rbxl')

# Forbidden runtime/data dependencies. Documentation may mention the origin project by design.
scan = [ROOT / 'src', ROOT / 'assets/manifests', ROOT / 'system/control-center', ROOT / 'config']
for base in scan:
    for p in base.rglob('*'):
        if p.is_file() and p.suffix.lower() in {'.luau', '.lua', '.py', '.json', '.yaml', '.yml'}:
            text = p.read_text(encoding='utf-8', errors='ignore')
            for token in [
                'RobloxLineageShared', 'RobloxLineageServer', 'RobloxLineageClient',
                'NewPlaceShared', 'NewPlaceServer', 'NewPlaceClient',
                'Interlude', 'CombatV2'
            ]:
                if token in text:
                    err(f'{p.relative_to(ROOT)} contains forbidden token {token}')

# FFighter is allowed only as a temporary bootstrap asset, not as an old archetype path.
for p in (ROOT / 'src').rglob('*.luau'):
    text = p.read_text(encoding='utf-8', errors='ignore')
    if 'human/fighter/female' in text:
        err(f'{p.relative_to(ROOT)} contains old archetype path')

cfg = json.loads((ROOT / 'config/project.json').read_text(encoding='utf-8'))
if cfg.get('name') != 'game1' or cfg.get('slug') != 'game1':
    err('config/project.json identity must be game1')
expected_namespaces = {
    'shared': 'Game1Shared', 'server': 'Game1Server',
    'client': 'Game1Client', 'remotes': 'Game1Remotes'
}
if cfg.get('namespaces') != expected_namespaces:
    err('config/project.json namespaces do not match game1 contract')

ports = cfg.get('ports', {})
old = {43720, 43721, 34872, 43127}
if old & set(ports.values()):
    err('port collision with RobloxLineage baseline')
if ports.get('rojo') != 34882:
    err('game1 Rojo port must be 34882 for M1')

if 'max(0, math.floor((tonumber(rawDamage) or 0) - defense))' not in (ROOT / 'src/server/DamageService.luau').read_text(encoding='utf-8'):
    err('damage formula contract missing')

if errors:
    print('VERIFY FAILED')
    for item in errors:
        print(' -', item)
    sys.exit(1)

print('VERIFY OK · game1 M1 static contracts passed')
print('registered characters:', len(manifest.get('archetypes', [])))
print('canonical place:', 'place/game1.rbxl')
