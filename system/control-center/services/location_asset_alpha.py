"""Per-Location-Asset alpha policy; never an Atlas Registry variant property."""
from __future__ import annotations


def validate_alpha(value: object) -> bool:
    if type(value) is not bool:
        raise ValueError("alphaEnabled must be a boolean")
    return value


def update(store, slug: str, payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("appearance payload must be an object")
    if set(payload) != {'alphaEnabled', 'expectedRevision'}:
        raise ValueError("appearance requires alphaEnabled and expectedRevision only")
    enabled = validate_alpha(payload['alphaEnabled'])
    expected = payload['expectedRevision']
    if type(expected) is not int or expected < 1:
        raise ValueError("expectedRevision must be a positive integer")
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT revision,alpha_enabled FROM location_assets WHERE slug=?', (slug,)).fetchone()
        if row is None:
            raise ValueError('Location Asset not found')
        if row['revision'] != expected:
            raise ValueError('Location Asset changed since Edit opened; refresh')
        if bool(row['alpha_enabled']) != enabled:
            import time
            db.execute('UPDATE location_assets SET alpha_enabled=?,revision=revision+1,updated_at=? WHERE slug=?',
                       (int(enabled),time.time(),slug))
    # Export may fail after the committed change; the record is still saved.
    store.export()
    return store.get(slug)
