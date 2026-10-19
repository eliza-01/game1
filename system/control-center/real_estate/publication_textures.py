"""Prepare Real Estate textures for Model and Image publication.

WebP decoding belongs to this image adapter, not to the Blender FBX pipeline.
Conversion is lossless to PNG; the registered original is never modified.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile


def published_format(source: Path) -> str:
    return 'png' if source.suffix.lower() == '.webp' else 'source'


def prepare_texture(root: Path, part: str, source: Path, staging: Path) -> Path:
    """Return the original source or a temporary PNG ready for Roblox upload.

    Keep the existing call signature because Store uses the same adapter for
    both the Model's embedded textures and the separate Image Assets.
    """
    if source.suffix.lower() != '.webp':
        return source
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError(
            'WebP publication requires Pillow in the Host Agent Python environment. '
            'Install it with: python -m pip install -r '
            'system/control-center/requirements-host.txt'
        ) from exc

    staging.mkdir(parents=True, exist_ok=True)
    target = staging / f'{part}.png'
    temporary: Path | None = None
    try:
        with Image.open(source) as image:
            if image.format != 'WEBP':
                raise ValueError('file contents are not a WebP image')
            image.load()  # Reject missing or truncated image data before writing.
            mode = 'RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB'
            converted = image.convert(mode)
            try:
                with tempfile.NamedTemporaryFile(
                    dir=staging, prefix=f'.{part}-', suffix='.png', delete=False
                ) as output:
                    temporary = Path(output.name)
                converted.save(temporary, format='PNG')
            finally:
                converted.close()
        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise ValueError('PNG output is empty')
        os.replace(temporary, target)
        temporary = None
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ValueError(f'WebP conversion failed for {part}: {exc}') from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target
