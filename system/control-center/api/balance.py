from services import game_balance as balance
from services import balance_patch_logs, skill_balance


def snapshot(deps):
    data = balance.load()
    weapons = [{'slug': r['slug'], 'type': r['weapon_type']} for r in deps['weapons'].snapshot()['items']]
    monsters = [{'slug': r['slug']} for r in deps['monsters'].snapshot()['items']]
    return {'balance': data, 'revision': balance.digest(data), 'weaponModels': weapons, 'monsterModels': monsters, 'resolvedSkilledMonsters': skill_balance.resolve(data)}


def read(path, deps):
    if path == '/api/balance/logs':
        try: return 200, balance_patch_logs.load()
        except (ValueError, OSError) as error: return 500, {'error': str(error)}
    if path != '/api/balance': return None
    try: return 200, snapshot(deps)
    except (ValueError,OSError) as error: return 500, {'error': str(error)}


def write(path, body, deps):
    if path not in ('/api/balance', '/api/balance/monster-aggro'): return None
    try:
        payload = body()
        if not isinstance(payload,dict): raise ValueError('Invalid balance request')
        if path == '/api/balance/monster-aggro':
            balance.sync_monster_aggro(payload.get('changes'),deps['weapons'].snapshot()['items'],deps['monsters'].snapshot()['items'])
            return 200, {'ok': True}
        balance.save(payload.get('balance'),payload.get('revision'),deps['weapons'].snapshot()['items'],deps['monsters'].snapshot()['items'])
        return 200, snapshot(deps)
    except (ValueError,TypeError) as error:
        return (409 if 'changed elsewhere' in str(error) else 400), {'error': str(error)}
    except OSError as error: return 500, {'error': str(error)}
