"""Read-only, version-controlled patch changelog; never part of gameplay data."""
import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[3] / 'config/balance/patch-logs.json'


def load():
    data = json.loads(SOURCE.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) != {'schemaVersion', 'entries'} or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1:
        raise ValueError('Invalid patch log schema')
    entries = data['entries']
    if not isinstance(entries, list) or len(entries) > 10000:
        raise ValueError('Invalid patch log entries')
    previous = 0
    for row in entries:
        if not isinstance(row, dict) or set(row) != {'patch', 'message'}:
            raise ValueError('Invalid patch log row')
        patch, message = row['patch'], row['message']
        if type(patch) is not int or patch <= previous:
            raise ValueError('Patch log numbers must increase')
        if not isinstance(message, str) or not 1 <= len(message) <= 500 or message != message.strip() or len(message.splitlines()) != 1:
            raise ValueError('Patch log message must be one nonempty line')
        previous = patch
    return data
