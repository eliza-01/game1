"""Mechanics catalog, allowlisted source reading and validated tuning authoring."""
from pathlib import Path
from urllib.parse import parse_qs

from mechanics.catalog import snapshot, permitted_source
from mechanics import settings as fireplace_settings

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAX_SOURCE_BYTES = 256_000


def route(parsed):
    if parsed.path == '/api/mechanics':
        return 200, snapshot()
    if parsed.path == '/api/mechanics/fireplace-settings':
        try:
            return 200, {'settings': fireplace_settings.load(),
                         'limits': fireplace_settings.FIELD_LIMITS}
        except (ValueError, OSError) as error:
            return 500, {'error': f'Fireplace settings cannot be read: {error}'}
    if parsed.path != '/api/mechanics/source':
        return None
    query = parse_qs(parsed.query)
    item = (query.get('item') or [''])[0]
    source = (query.get('source') or [''])[0]
    selected = permitted_source(item, source)
    if not selected:
        return 404, {'error': 'mechanics source not found'}
    relative_path, title = selected
    path = (PROJECT_ROOT / relative_path).resolve()
    if not path.is_relative_to(PROJECT_ROOT.resolve()) or not path.is_file():
        return 404, {'error': 'mechanics source unavailable'}
    if path.stat().st_size > MAX_SOURCE_BYTES:
        return 413, {'error': 'mechanics source too large'}
    try:
        content = path.read_text(encoding='utf-8')
    except (UnicodeError, OSError):
        return 500, {'error': 'mechanics source cannot be read'}
    return 200, {'item': item, 'source': source, 'title': title,
                 'path': relative_path, 'content': content}


def write(path, body, _deps):
    if path != '/api/mechanics/fireplace-settings':
        return None
    try:
        payload = body()
        if not isinstance(payload, dict):
            raise ValueError('settings payload must be an object')
        saved = fireplace_settings.save(payload.get('settings'), payload.get('expected'))
        return 200, {'settings': saved, 'studioSyncRequired': True}
    except ValueError as error:
        return (409 if 'changed elsewhere' in str(error) else 400), {'error': str(error)}
    except (OSError, TypeError) as error:
        return 500, {'error': f'Fireplace settings cannot be saved: {error}'}
