"""Read-only alpha inspection for published texture bindings.

Authoring keeps image identities and files unchanged.  Alpha metadata is derived
at sync/export time, so reused textures always follow their current owner.
None means unknown (missing, unreadable or unsupported source), NOT opaque.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path


def texture_uses_alpha(root: Path | None, source_path: str) -> bool | None:
    """Return whether any pixel has alpha < 255; never modify source or DB."""
    if root is None or not source_path:
        return None
    root = root.resolve()
    try:
        path = (root / source_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return None
        if path.suffix.lower() in ('.jpg', '.jpeg'):
            return False
        if path.suffix.lower() not in ('.png', '.webp'):
            return None
        stat = path.stat()
        return _read_alpha(str(path), stat.st_mtime_ns, stat.st_size)
    except (OSError, ValueError):
        return None


def texture_binding(slot: str, asset_id: str, root: Path | None, source_path: str,
                    *, registered_sha256: str = '', published_sha256: str = '') -> dict:
    """Bridge compatibility: omit unknown alpha rather than inventing a false value."""
    binding = {'slot': str(slot), 'assetId': str(asset_id)}
    # Never describe the still-published Roblox ID using pixels from an
    # unpublished replacement source.  It remains an unknown alpha mode.
    if registered_sha256 and published_sha256 and registered_sha256 != published_sha256:
        return binding
    uses_alpha = texture_uses_alpha(root, source_path)
    if uses_alpha is not None:
        binding['usesAlpha'] = uses_alpha
    return binding


@lru_cache(maxsize=512)
def _read_alpha(path: str, _mtime_ns: int, _size: int) -> bool | None:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        return None
    try:
        with Image.open(path) as image:
            if image.width * image.height > 8192 * 8192:
                return None  # Avoid unbounded decoding in registry/Sync requests.
            # P-mode PNG can store its alpha in tRNS rather than a full A band.
            if 'A' not in image.getbands() and 'transparency' not in image.info:
                return False
            rgba = image.convert('RGBA')
            try:
                minimum, _maximum = rgba.getchannel('A').getextrema()
                return minimum < 255
            finally:
                rgba.close()
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        return None
