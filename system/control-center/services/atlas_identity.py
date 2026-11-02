"""Public atlas presentation metadata, independent of the first consumer.

This is a read-only projection. Never re-key AtlasRegistry families or rewrite
legacy owner references using these names: they remain stable DB identifiers.
"""
from pathlib import Path

from services.texture_atlas_registry import atlas_version, parse_filename


def display_identity(filename: str = '', atlas_key: str = '') -> dict:
    basename = Path(str(filename or '').replace('\\', '/')).name
    try:
        parsed = parse_filename(basename) if basename else None
    except ValueError:
        # Legacy authoring filenames may advertise nonstandard sizes. A display
        # projection must never make the entire published catalog unavailable.
        parsed = None
    stem = Path(basename).stem
    fallback = stem[:-6] if stem.casefold().endswith('_atlas') else stem
    key = str(atlas_key or (parsed or {}).get('atlasKey') or fallback or 'unknown atlas').strip()
    name, version = atlas_version(key)
    resolution = f"{parsed['width']}×{parsed['height']}" if parsed else ''
    return {'atlasKey': key, 'atlasName': name, 'atlasVersion': version,
            'atlasResolution': resolution}
