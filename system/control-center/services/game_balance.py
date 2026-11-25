"""Canonical game balance authoring. Visual registries are independent.
JSON is the editable source; the immutable Luau registry is its projection.
"""
from __future__ import annotations
from copy import deepcopy
from services import skill_balance
import hashlib
import json
import math
from pathlib import Path
from threading import RLock
from tempfile import NamedTemporaryFile
import os

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'config/balance/gameplay.json'
OUTPUT = ROOT / 'src/shared/balance/BalanceRegistry.luau'
LOCK = RLock()
TYPES = ('dagger', 'sword', 'bigsword', 'bow', 'dualswords')
RARITIES = ('common', 'uncommon', 'rare', 'mythical', 'legendary', 'immortal')
FIELDS = {
    'levels': {'hp': (1, 1000000), 'xpNext': (0, 100000000)},
    'weapons': {'level': (1, 35), 'damage': (0, 1000000), 'price': (0, 100000000),
                'attackSpeedDelta': (-100, 200), 'critChance': (0, 50), 'radius': (1, 420), 'arc': (1, 360),
                'upgradePrice': (0, 100000000)},
    'armor': {'level': (1, 35), 'hp': (0, 1000000), 'price': (0, 100000000)},
    'monsters': {'level': (1, 35), 'hp': (1, 1000000), 'damage': (0, 1000000),
                 'xp': (0, 100000000), 'gold': (0, 100000000), 'critChance': (0, 50), 'attackRange': (1, 100), 'attackSpeed': (1, 400)},
}
RULES = {'baseDamage': (0, 100000), 'baseAttackSpeed': (25, 400), 'critChance': (0, 50), 'maxCritChance': (1, 50), 'upgradePercent': (0, 100),
         'maxUpgrade': (0, 20), 'headshotMultiplier': (1, 5), 'critMultiplier': (1, 5)}


def number(v, lo, hi, label, integral=True):
    if type(v) not in (int, float) or not math.isfinite(v) or not lo <= v <= hi or (integral and int(v) != v):
        raise ValueError(f'{label}: expected {"integer" if integral else "number"} in {lo}..{hi}')
    return int(v) if integral else v


def validate(data):
    if not isinstance(data, dict) or set(data) != {'schemaVersion','rules','levels','weapons','armor','monsters','weaponBindings','monsterBindings','test','skills','skilledMonsters'} or data['schemaVersion'] != 4:
        raise ValueError('Invalid balance schema')
    if not isinstance(data['rules'], dict) or set(data['rules']) != set(RULES):
        raise ValueError('Invalid rules')
    for field, (lo, hi) in RULES.items():
        number(data['rules'][field], lo, hi, field, field not in ('upgradePercent','headshotMultiplier','critMultiplier','critChance','maxCritChance'))
    if not isinstance(data['test'], dict) or set(data['test']) != {'x','y','z','yaw','maxGroup','skilledEnabled'}:
        raise ValueError('Invalid gameplay test configuration')
    for axis in ('x','y','z'): number(data['test'][axis], -100000, 100000, axis, False)
    number(data['test']['yaw'], -360, 360, 'yaw', False)
    number(data['test']['maxGroup'], 1, 12, 'maxGroup')
    if type(data['test']['skilledEnabled']) is not bool: raise ValueError('Invalid skilledEnabled')
    counts = {'levels': 35, 'weapons': 34, 'armor': 8, 'monsters': 70}
    for group, fields in FIELDS.items():
        rows = data[group]
        if not isinstance(rows, list) or len(rows) != counts[group]:
            raise ValueError(f'{group}: expected {counts[group]} rows')
        for i, row in enumerate(rows, 1):
            extra = {'level'} if group == 'levels' else {'id'}
            if group == 'monsters': extra.add('type')
            if group == 'weapons':
                extra |= {'type','rarity'}
                if isinstance(row, dict) and row.get('type') == 'dualswords': extra.add('recipe')
            if not isinstance(row, dict) or set(row) != set(fields) | extra:
                raise ValueError(f'{group}: invalid row {i}')
            if group == 'levels':
                if type(row['level']) is not int or row['level'] != i or (row['xpNext'] == 0) != (i == 35):
                    raise ValueError('Level sequence / cap invalid')
            else:
                prefix = {'weapons':'weapon','armor':'armor','monsters':'monster'}[group]
                if row['id'] != f'{prefix}_{i:03d}': raise ValueError(f'{group}: stable ID required')
            for field, (lo, hi) in fields.items():
                number(row[field], lo, hi, f'{group}.{i}.{field}', field not in ('radius','arc','critChance'))
            if group == 'monsters':
                expected_type = 'melee' if i <= 35 else 'ranged'
                if row['type'] != expected_type or row['level'] != (i - 1) % 35 + 1:
                    raise ValueError('Monster type / level sequence invalid')
                if row['type'] == 'ranged' and row['attackRange'] < 8:
                    raise ValueError('Ranged attack range must be at least 8 studs')
            if group == 'weapons' and (row['type'] not in TYPES or row['rarity'] not in RARITIES):
                raise ValueError('Invalid weapon type / rarity')
    swords = {r['id']: r for r in data['weapons'] if r['type'] == 'sword'}
    for row in data['weapons']:
        if row['type'] != 'dualswords': continue
        recipe = row['recipe']
        if row['level'] < 30 or not isinstance(recipe, dict) or set(recipe) != {'swordId','quantity','fee'}:
            raise ValueError('Dualswords require B grade and a sword recipe')
        if not isinstance(recipe['swordId'], str) or recipe['swordId'] not in swords or swords[recipe['swordId']]['level'] != row['level']:
            raise ValueError('Dualswords recipe requires a sword of the same item level')
        number(recipe['quantity'], 2, 2, 'recipe.quantity')
        number(recipe['fee'], 0, 100000000, 'recipe.fee')
        if row['price'] != 2 * swords[recipe['swordId']]['price'] + recipe['fee']:
            raise ValueError('Dualswords price must match two swords plus recipe fee')
    if any(b['hp'] < a['hp'] for a,b in zip(data['levels'], data['levels'][1:])):
        raise ValueError('Player HP cannot decrease with level')
    for key, group in (('weaponBindings','weapons'), ('monsterBindings','monsters')):
        ids = {r['id'] for r in data[group]}
        bindings = data[key]
        if not isinstance(bindings, dict) or len(bindings) > 4096:
            raise ValueError(f'Invalid {key}')
        for slug, identity in bindings.items():
            if not isinstance(slug,str) or not 1 <= len(slug) <= 64 or not all(c in 'abcdefghijklmnopqrstuvwxyz0123456789_' for c in slug) or not isinstance(identity,str) or identity not in ids:
                raise ValueError(f'Invalid {key} binding: {slug}')
    skill_balance.validate(data, number)
    return data


def check_bindings(data, models, monsters):
    types = {r['slug']:r['weapon_type'] for r in models}
    rows = {r['id']:r for r in data['weapons']}
    for slug, identity in data['weaponBindings'].items():
        if types.get(slug) != rows[identity]['type']:
            raise ValueError(f'{slug}: missing model or incompatible weapon type')
    known = {r['slug'] for r in monsters}
    if set(data['monsterBindings']) - known:
        raise ValueError('Remove unknown monster model bindings before saving')


def _lua(value, depth=0):
    if isinstance(value, bool): return str(value).lower()
    if isinstance(value, (int,float)): return str(value)
    if isinstance(value,str): return json.dumps(value, ensure_ascii=False)
    if isinstance(value,(dict,list)):
        pairs = ([(f'[{json.dumps(k)}] = ',v) for k,v in sorted(value.items())] if isinstance(value,dict) else [('',v) for v in value])
        if not pairs: return 'table.freeze({})'
        return 'table.freeze({\n' + ''.join('    '*(depth+1)+key+_lua(v,depth+1)+',\n' for key,v in pairs) + '    '*depth+'})'
    raise ValueError('Unsupported registry value')


def render(data):
    projection = deepcopy(validate(data))
    projection['resolvedSkilledMonsters'] = skill_balance.resolve(data)
    return '-- Generated from config/balance/gameplay.json. Edit Database, not this file.\nreturn '+_lua(projection)+'\n'


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def load():
    with LOCK:
        data = validate(json.loads(SOURCE.read_text(encoding='utf-8')))
        if OUTPUT.read_text(encoding='utf-8') != render(data):
            raise ValueError('Balance source and runtime registry differ; restore matching versions')
        return data


def atomic(path, content):
    with NamedTemporaryFile('w',encoding='utf-8',newline='\n',dir=path.parent,delete=False) as f:
        temp = Path(f.name)
        try:
            f.write(content); f.flush(); os.fsync(f.fileno())
        except BaseException:
            temp.unlink(missing_ok=True); raise
    try: os.replace(temp,path)
    finally: temp.unlink(missing_ok=True)


def save(data, expected, models, monsters):
    with LOCK:
        previous = load()
        if digest(previous) != expected: raise ValueError('Balance changed elsewhere; refresh')
        data = validate(data)
        check_bindings(data, models, monsters)
        old_source = SOURCE.read_text(encoding='utf-8')
        old_output = OUTPUT.read_text(encoding='utf-8')
        backup = SOURCE.with_name('gameplay.previous.json')
        atomic(backup, old_source)
        try:
            atomic(SOURCE,json.dumps(data,ensure_ascii=False,indent=2)+'\n')
            atomic(OUTPUT,render(data))
        except BaseException:
            atomic(SOURCE,old_source); atomic(OUTPUT,old_output); raise
        return data
