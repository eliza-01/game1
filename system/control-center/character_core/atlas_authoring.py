"""Character atlas authoring workflow; inspection is read-only and upload is explicit.

The shared AtlasRegistry still owns bytes, revisions and Roblox Image Asset IDs.
This adapter owns Character scope, preview data, race checks and authoring UX.
"""
from __future__ import annotations

import base64
from io import BytesIO
import os
from pathlib import Path
import re
import subprocess

from PIL import Image, UnidentifiedImageError

from services.texture_atlas_registry import parse_filename, digest
from character_core.part_names import TOKEN


class CharacterAtlasAuthoring:
    def __init__(self, components):
        self.components = components
        self.registry = components.atlases

    @staticmethod
    def _source(source_path):
        path = Path(str(source_path)).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() not in ('.jpg', '.jpeg', '.png'):
            raise ValueError('select an existing PNG/JPG atlas file')
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('atlas file exceeds the 64 MB inspection limit')
        return path

    @staticmethod
    def _preview(path):
        with Image.open(path) as image:
            image.thumbnail((256, 256))
            output = BytesIO()
            image.convert('RGBA').save(output, format='PNG')
        return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')

    @staticmethod
    def _expected(path, width, height):
        # This is a suggestion, never an automatic file rename.
        stem = re.sub(r'(_\d+x\d+)?_atlas$', '', path.stem.lower())
        stem = re.sub(r'[^a-z0-9]+', '_', stem).strip('_')
        if not stem:
            stem = 'character_face_01'
        elif not stem[0].isalpha():
            stem = 'character_' + stem
        stem = stem[:96].rstrip('_')
        return f'{stem}_{width}x{height}_atlas{path.suffix.lower()}'

    def inspect(self, source_path):
        path = self._source(source_path)
        try:
            with Image.open(path) as image:
                width, height = image.size
                image.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f'cannot read atlas image: {exc}') from exc
        try:
            parsed = parse_filename(path.name)
        except ValueError:
            parsed = None
        expected = self._expected(path, width, height)
        response = dict(sourcePath=str(path), filename=path.name, width=width, height=height,
                        expectedFilename=expected, valid=False, reason='', existing=None,
                        oldPreview='', newPreview=self._preview(path), sha256=digest(path))
        if not parsed:
            response['reason'] = 'Invalid atlas name. Rename the file manually, then select it again.'
            return response
        if (parsed['width'], parsed['height']) != (width, height):
            response['reason'] = 'Image dimensions do not match the filename. Rename the file, then select it again.'
            return response
        # Character part/set names are lower_snake_case. Require the same naming
        # for NEW Character atlas sources, without changing the global registry
        # used by Location Assets and Real Estate. Existing atlas records remain
        # untouched, including older non-canonical names and their Image IDs.
        if not TOKEN.fullmatch(parsed['atlasKey']) or path.name != expected:
            response['reason'] = ('Character atlas names must use lowercase Latin letters, '
                                  'digits and underscores (snake_case). For example, '
                                  '"fullplate imperial" becomes "fullplate_imperial".')
            return response
        for group in self.registry.catalog():
            if group['atlasKey'] != parsed['atlasKey']:
                continue
            for variant in group['variants']:
                if (variant['width'], variant['height']) != (width, height):
                    continue
                if variant['id'] not in self.registry.character_variant_ids():
                    response['reason'] = 'Atlas name/resolution already belongs to another section. Rename this Character atlas.'
                    response['expectedFilename'] = 'character_' + expected
                    return response
                response['existing'] = dict(id=variant['id'], publishedId=variant.get('published_id') or '',
                                            current=variant['current'], replacementPending=variant['replacementPending'],
                                            sha256=variant['source_sha256'])
                old_path = (self.components.root / variant['source_path']).resolve()
                if (old_path.is_relative_to(self.components.root) and old_path.is_file()
                        and digest(old_path) == variant['source_sha256']):
                    response['oldPreview'] = self._preview(old_path)
                break
        response['valid'] = True
        response['unchanged'] = bool(response['existing'] and
                                     response['existing']['sha256'] == response['sha256'] and
                                     response['existing']['current'])
        response['replacementRequired'] = bool(response['existing'] and response['existing']['publishedId'] and
                                                not response['unchanged'])
        return response

    def publish(self, payload, publication_credentials):
        inspected = self.inspect(payload.get('sourcePath') or '')
        if not inspected['valid']:
            raise ValueError(inspected['reason'] + ' Expected: ' + inspected['expectedFilename'])
        if payload.get('sha256') != inspected['sha256']:
            raise ValueError('selected file changed since preview; inspect it again')
        existing = inspected['existing']
        if int(payload.get('expectedVariantId') or 0) != (existing['id'] if existing else 0):
            raise ValueError('atlas registry changed since preview; inspect it again')
        if str(payload.get('expectedPublishedId') or '') != (existing['publishedId'] if existing else ''):
            raise ValueError('atlas publication changed since preview; inspect it again')
        if inspected['replacementRequired'] and payload.get('approveReplacement') is not True:
            raise ValueError('explicit replacement approval required')
        variant = self.registry.register_file(inspected['sourcePath'], domain='character')
        staged_sha = variant['replacement_sha256'] if variant['replacementPending'] else variant['source_sha256']
        if staged_sha != inspected['sha256']:
            raise ValueError('selected file changed while registering; inspect it again (no upload performed)')
        # An unchanged published atlas is idempotent; no fresh upload occurs.
        result = self.registry.ensure_published(variant['id'],
                    publication_credentials('game1 character atlas'), 'game1 character atlas')
        self.components.export()
        return dict(variant=result, reused=bool(inspected['unchanged']),
                    previousAssetId=existing['publishedId'] if existing else '',
                    publishedAssetId=result['published_id'])

    def reveal(self, source_path):
        path = self._source(source_path)
        if os.name != 'nt':
            raise ValueError('Show in folder is supported by the Windows Host Agent')
        # No shell, user-controlled command, or server-side rename.
        os.startfile(str(path.parent))
        return {'opened': True}
