"""Export the exact HUD masks and colors from BuffDefinitions for Asset Manager.
Run after changing a buff icon: python system/tools/build_buff_icon_catalog.py.
--check verifies the checked-in preview without modifying files.
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'src/shared/combat/BuffDefinitions.luau'
OUTPUT = ROOT / 'system/control-center/static/buff-icons/catalog.json'


def build():
    source = SOURCE.read_text(encoding='utf-8')
    rows = []
    for line in source.splitlines():
        if 'table.freeze({effect=' not in line:
            continue
        identity = re.search(r'effect="(\w+)", name="([^"]+)", grade="([^"]+)"', line)
        color = re.search(r'color=Color3\.fromRGB\((\d+),(\d+),(\d+)\)', line)
        mask = re.search(r'iconMask=table\.freeze\((\{[^}]+\})\)', line)
        if not (identity and color and mask):
            raise ValueError(f'Invalid buff icon definition: {line}')
        effect, name, grade = identity.groups()
        rgb = tuple(map(int, color.groups()))
        pixels = json.loads('[' + mask[1][1:-1] + ']')
        if len(pixels) != 9 or any(not re.fullmatch(r'[.#]{9}', row) for row in pixels):
            raise ValueError(f'Invalid mask: {effect}')
        if any(not 0 <= n <= 255 for n in rgb):
            raise ValueError(f'Invalid color: {effect}')
        rows.append(dict(effect=effect, name=name, grade=grade, color='#%02x%02x%02x' % rgb, mask=pixels))
    if not rows or len({row['effect'] for row in rows}) != len(rows):
        raise ValueError('Missing or duplicate buff icons')
    return json.dumps({'tileSize': 9, 'tiles': rows}, indent=2, ensure_ascii=False) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = build()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding='utf-8') != result:
            raise SystemExit('Buff icon catalog is stale; run build_buff_icon_catalog.py')
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(result, encoding='utf-8')
