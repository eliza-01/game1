"""Authenticated, read-only mechanics catalog and allowlisted project sources."""
from pathlib import Path
from urllib.parse import parse_qs

from mechanics.catalog import snapshot, permitted_source

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAX_SOURCE_BYTES = 256_000


def route(parsed):
    if parsed.path == '/api/mechanics':
        return 200, snapshot()
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
