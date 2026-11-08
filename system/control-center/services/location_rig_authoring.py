"""Explicit Location FBX authoring migration, separate from publication and Studio.

The new rig_carrier is Blender-exported geometry in an immutable authoring source;
existing canonical FBX, placement and independent Atlas bindings are preserved.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from services.fbx_blender_report import run_report
from services.location_fbx_inspection import inspect as inspect_fbx


def prepare_canonical_fbx(store, slug: str, expected_revision: int) -> dict:
    """User-initiated, fail-closed source revision; no upload or Studio mutation."""
    if type(expected_revision) is not int or expected_revision <= 0:
        raise ValueError('expectedRevision must be a positive integer')
    previous = store.get(slug)
    if not previous:
        raise ValueError('unknown Location Asset')
    if int(previous['revision']) != expected_revision:
        raise ValueError('Location Asset changed; refresh before preparing the FBX')
    source = (store.root / str(previous.get('model_path') or '')).resolve()
    if not source.is_relative_to(store.root.resolve()) or not source.is_file() or source.suffix.casefold() != '.fbx':
        raise ValueError('registered Location FBX is missing')
    if store._sha256(source) != previous.get('model_sha256'):
        raise ValueError('registered FBX was modified outside Asset Manager; re-register it first')
    analysis = previous.get('fbxAnalysis')
    if not isinstance(analysis, dict) or not isinstance(analysis.get('meshes'), list):
        raise ValueError('FBX inspection is required before preparing an authored carrier')
    if not any(mesh.get('bones') for mesh in analysis['meshes']):
        raise ValueError('FBX has no Bones; static Location does not require rig_carrier')
    if analysis.get('unassignedArmatures'):
        raise ValueError('FBX contains an unassigned armature; correct the skeletal authoring first')
    if any(part.get('name', '').casefold() == 'rig_carrier' for part in analysis['meshes']):
        raise ValueError('FBX already contains rig_carrier; publish it directly or correct it in Blender')

    with TemporaryDirectory(prefix='game1-location-authoring-') as folder:
        generated = Path(folder) / 'canonical.fbx'
        report = Path(folder) / 'manifest.json'
        manifest = run_report(store.root, 'location_rig_authoring_fbx.py',
                              (source, generated, report), report_path=report,
                              label='Location canonical FBX authoring')
        if not generated.is_file() or generated.stat().st_size <= 0:
            raise ValueError('Blender did not generate the authored FBX')
        checksum = hashlib.sha256(generated.read_bytes()).hexdigest()
        if (manifest.get('schemaVersion') != 2 or not manifest.get('structuralHash')
                or manifest.get('sourceSha256') != checksum):
            raise ValueError('Blender authoring returned an invalid or mismatched rig manifest')
        # A real FBX inspection, NOT only a metadata assertion. No mutation until
        # Blender produced and verified the new authored source.
        analysis = inspect_fbx(store.root, generated)
        names = [part['name'] for part in analysis['meshes']]
        if names.count('rig_carrier') != 1 or any(n == 'RootPart' for n in names):
            raise ValueError('authored FBX does not have exactly one canonical rig_carrier')
        if set(names) != {part['name'] for part in manifest['parts']}:
            raise ValueError('authored FBX mesh inventory does not match Blender manifest')
        # Keep generated Blender authoring FBX and its provenance, distinct from
        # the canonical registered source and its backup. Never overwrite a
        # previously generated, immutable authored revision.
        directory = store.root / 'assets/authoring/location-assets' / slug
        directory.mkdir(parents=True, exist_ok=True)
        stem = f'{slug}__rig_v2__{checksum[:16]}'
        authored = directory / f'{stem}.fbx'
        authored_manifest = directory / f'{stem}.manifest.json'
        if authored.exists():
            if hashlib.sha256(authored.read_bytes()).hexdigest() != checksum:
                raise ValueError('authored FBX provenance collision; refusing overwrite')
        else:
            with authored.open('xb') as handle, generated.open('rb') as input_file:
                shutil.copyfileobj(input_file, handle)
        if authored_manifest.exists():
            if json.loads(authored_manifest.read_text('utf-8')) != manifest:
                raise ValueError('authored rig manifest differs from existing immutable revision')
        else:
            with authored_manifest.open('x', encoding='utf-8') as handle:
                json.dump(manifest, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.write('\n')
        # Registration performs the revision/CAS check. Preserve the original
        # canonical bytes for rollback if the registration fails before commit;
        # never restore an obsolete file if a concurrent writer committed a
        # newer DB revision.
        backup = Path(folder) / 'previous_canonical.fbx'
        shutil.copy2(source, backup)
        try:
            updated = store.register({
            'slug': slug, 'nameEn': previous['name_en'],
            'category': previous['category'],
            'destructible': bool(previous['destructible']),
            'surfaceMaterial': previous['surfaceMaterial'],
            'alphaEnabled': bool(previous['alphaEnabled']),
            'atlasVariantId': int(previous['atlasVariantId']),
            'modelSourcePath': str(authored), 'inspectFbx': True,
            'expectedRevision': expected_revision, 'editOnly': True,
            })
        except Exception:
            latest = store._raw_get(slug)
            if (latest and latest['revision'] == expected_revision and
                    latest['model_sha256'] == previous['model_sha256']):
                shutil.copy2(backup, source)
            raise
        if updated['model_sha256'] != checksum:
            raise RuntimeError('canonical FBX SHA changed while registering authored source')
        return {'resourceKind': 'ModelSource', 'slug': slug, 'revision': updated['revision'],
                'authoredSource': authored.relative_to(store.root).as_posix(),
                'originalArchived': True, 'atlasUnchanged':
                str(previous.get('texture_asset_id') or '') == str(updated.get('texture_asset_id') or ''),
                'structuralHash': manifest['structuralHash'],
                'model_asset_id': updated.get('model_asset_id'),
                'readyToPublish': True}
