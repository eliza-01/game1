"""Shared, explicit atlas review and publication for location and house consumers.

Review is read-only. Commit validates the original source again, stages a
canonical native PNG/JPEG and delegates publication to the Atlas Registry.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
import shutil
import tempfile

from PIL import Image, UnidentifiedImageError

from services.texture_atlas_registry import (
    canonical_atlas_filename, convert_webp_atlas_to_png, digest, parse_filename,
)


def image_preview(path: Path) -> str:
    with Image.open(path) as image:
        image.thumbnail((256, 256))
        output = BytesIO()
        image.convert('RGBA').save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')


@contextmanager
def publication_candidate(source: Path, filename: str, native_format: str):
    """Match the Atlas Registry's native-format and canonical-filename rules.

    No registry writes or Open Cloud calls. The temporary conversion vanishes
    after review/commit, and the original file is never modified.
    """
    if native_format != 'WEBP' and source.name == filename:
        yield source
        return
    with tempfile.TemporaryDirectory(prefix='game1-atlas-review-') as temp:
        staged = Path(temp) / filename
        if native_format == 'WEBP':
            convert_webp_atlas_to_png(source, staged)
        else:
            shutil.copy2(source, staged)
        yield staged


class AtlasSourceReview:
    def __init__(self, registry):
        self.registry = registry

    def inspect(self, source_path: str) -> dict:
        path = Path(str(source_path or '')).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp'):
            raise ValueError('choose a PNG, JPEG or WebP atlas image')
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('atlas exceeds 64 MB inspection limit')
        try:
            with Image.open(path) as image:
                native_format = image.format
                width, height = image.size
                if native_format not in ('PNG', 'JPEG', 'WEBP'):
                    raise ValueError('unsupported atlas content: expected PNG/JPEG/WebP')
                if width > 16384 or height > 16384:
                    raise ValueError('atlas dimensions must not exceed 16384 pixels')
                image.verify()
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
            raise ValueError(f'cannot inspect atlas: {error}') from error

        filename = canonical_atlas_filename(path, native_format, width, height)
        parsed = parse_filename(filename)
        if not parsed or (parsed['width'], parsed['height']) != (width, height):
            raise ValueError('cannot derive a canonical atlas filename from this image')

        with publication_candidate(path, filename, native_format) as canonical:
            canonical_sha = digest(canonical)
            preview = image_preview(canonical)

        result = {
            'sourcePath': str(path), 'filename': filename,
            'width': width, 'height': height, 'sha256': digest(path),
            'oldPreview': '', 'newPreview': preview,
            'existing': None, 'valid': True, 'reason': '',
            'replacementRequired': False, 'unchanged': False,
        }
        for family in self.registry.catalog():
            if family['atlasKey'] != parsed['atlasKey']:
                continue
            for variant in family['variants']:
                if (variant['width'], variant['height']) != (width, height):
                    continue
                result['existing'] = {
                    'id': variant['id'], 'publishedId': variant['published_id'] or '',
                    'sha256': variant['source_sha256'], 'filename': variant['filename'],
                }
                old_path = (self.registry.root / variant['source_path']).resolve()
                if old_path.is_relative_to(self.registry.root) and old_path.is_file():
                    if digest(old_path) == variant['source_sha256']:
                        result['oldPreview'] = image_preview(old_path)
                break

        existing = result['existing']
        result['unchanged'] = bool(
            existing and existing['sha256'] == canonical_sha
            and self.registry.get_variant(existing['id'])['current']
        )
        result['replacementRequired'] = bool(
            existing and existing['publishedId'] and not result['unchanged']
        )
        return result

    def publish(self, payload: dict, credentials: dict) -> dict:
        inspected = self.inspect(payload.get('sourcePath') or '')
        existing = inspected['existing']
        if (
            str(payload.get('sha256') or '') != inspected['sha256']
            or int(payload.get('expectedVariantId') or 0) != (existing['id'] if existing else 0)
            or str(payload.get('expectedPublishedId') or '') != (existing['publishedId'] if existing else '')
        ):
            raise ValueError('atlas source or publication changed since preview; choose the image again')
        if inspected['replacementRequired'] and payload.get('approveReplacement') is not True:
            raise ValueError('explicit approval required to replace a shared atlas')

        path = Path(inspected['sourcePath'])
        with Image.open(path) as image:
            native_format = image.format
        with publication_candidate(path, inspected['filename'], native_format) as canonical:
            variant = self.registry.register_file(str(canonical))
            # Registry owns upload deduplication and unresolved-operation locks.
            published = self.registry.ensure_published(variant['id'], credentials, 'game1 atlas')
        return {
            'variant': published, 'unchanged': inspected['unchanged'],
            'previousAssetId': existing['publishedId'] if existing else '',
            'publishedAssetId': published['published_id'], 'studioSyncRequired': True,
        }
