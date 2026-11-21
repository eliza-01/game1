"""One FBX staging/publication mechanism shared by Location and House LOD1.

Callers own domain identity, SQLite revision CAS, audit and placement policy.
No Studio/Place mutation is performed here.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from model_publication_service import staged_model
from opencloud_assets import create_model_asset, wait_for_operation

MAX_FBX_BYTES = 200 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_fbx(source_path: str, expected_name: str) -> tuple[Path, str]:
    source = Path(str(source_path or '')).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != '.fbx':
        raise ValueError('choose a valid LOD1 FBX source')
    if source.name != expected_name:
        raise ValueError(f'LOD1 filename must be {expected_name}')
    if not 0 < source.stat().st_size <= MAX_FBX_BYTES:
        raise ValueError('LOD1 FBX is empty or exceeds 200 MB')
    with source.open('rb') as stream:
        header = stream.read(4096)
    if not (header.startswith(b'Kaydara FBX Binary') or b'FBXHeaderExtension' in header):
        raise ValueError('LOD1 source is not a recognizable binary or ASCII FBX')
    return source, sha256(source)


def preserve_source(source: Path, target: Path, archive: Path, expected_sha: str) -> None:
    """Save an immutable retired source before replacing the active revision."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if source == target.resolve():
        return
    if target.is_file():
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            shutil.copy2(target, archive)
    temporary = target.with_name(target.name + '.tmp')
    try:
        shutil.copy2(source, temporary)
        if sha256(temporary) != expected_sha:
            raise RuntimeError('LOD1 copy checksum mismatch')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def publish_geometry(root: Path, path: Path, slug: str, credentials: dict, *, description: str):
    api_key = str(credentials.get('apiKey') or '')
    with staged_model(root, path, texture_mode='geometry_only') as publication:
        operation = create_model_asset(
            publication, display_name=f'{slug}_lod1',
            description=str(credentials.get('description') or description),
            creator_type=str(credentials.get('creatorType') or ''),
            creator_id=str(credentials.get('creatorId') or ''), api_key=api_key)
    return wait_for_operation(operation, api_key=api_key)


# Single LOD1 contract for both Location Assets and Real Estate. Domain adapters
# only own their FBX storage layout, database schema, audit history and house
# FULL revision coupling; they must not implement separate state/pinning rules.
def check_revision(expected: int, actual: int, *, label: str = 'LOD1') -> None:
    if type(expected) is not int or expected < 0:
        raise ValueError(f'{label} revision is required')
    if int(actual) != expected:
        raise ValueError(f'{label} changed; refresh')


def describe_resource(row, root: Path, *, full_changed: bool = False,
                      kind: str | None = None) -> dict:
    """Canonical UI/Runtime LOD1 status, including immutable reused Model IDs."""
    blank = {'revision': 0, 'status': 'NOT_REGISTERED', 'sourcePath': '',
             'sourceSha256': '', 'publishedSha256': '', 'modelAssetId': '',
             'moderationState': '', 'reuse': None}
    if kind:
        blank = {'kind': kind, **blank}
    if row is None:
        return blank
    value = dict(row)
    reused = bool(value.get('reuse_domain'))
    source_path = str(value.get('source_path') or '')
    source_sha = str(value.get('source_sha256') or '')
    stored_sha = str(value.get('published_sha256') or '')
    model_id = str(value.get('asset_id') or '')
    available = reused
    if not reused and source_path:
        source = (root / source_path).resolve()
        # The staged source must be an actual file under the project root.
        # Status does not hide modified bytes from the verification path.
        available = source.is_relative_to(root.resolve()) and source.is_file()
    status = ('SOURCE_MISSING' if not available else
              'FULL_CHANGED' if full_changed else
              'PUBLISHED' if model_id and source_sha == stored_sha else
              'UPDATE_AVAILABLE' if model_id else 'STAGED')
    return {**blank, 'revision': int(value['revision']), 'status': status,
            'sourcePath': source_path, 'sourceSha256': source_sha,
            'publishedSha256': stored_sha, 'modelAssetId': model_id,
            'moderationState': value.get('moderation_state') or '',
            'reuse': ({'domain': value['reuse_domain'], 'slug': value['reuse_slug'],
                       'revision': int(value['reuse_revision'])} if reused else None)}


def verified_source(root: Path, resource: dict, *, digest=sha256) -> Path:
    """Both publishers must reject paths outside their project and changed FBX bytes."""
    source_path = str(resource.get('sourcePath') or '')
    if not source_path or resource.get('reuse'):
        raise ValueError('stage a new LOD1 FBX before publication')
    path = (root / source_path).resolve()
    if (not path.is_relative_to(root.resolve()) or not path.is_file()
            or digest(path) != resource.get('sourceSha256')):
        raise ValueError('LOD1 source changed; stage it again')
    return path


def reuse_values(source: dict, target_domain: str, target_slug: str,
                 expected_revision: int, current_revision: int) -> dict:
    """Immutable cross-domain LOD1 pin, with the same CAS/identity guarantees."""
    if target_domain not in ('location', 'house', 'house_part'):
        raise ValueError('invalid LOD1 target domain')
    check_revision(expected_revision, current_revision, label='target LOD1')
    if not isinstance(source, dict) or source.get('domain') not in ('location', 'house', 'house_part'):
        raise ValueError('invalid published LOD1 source')
    if source.get('domain') == target_domain and source.get('slug') == target_slug:
        raise ValueError('cannot reuse own LOD1')
    model_id = source.get('modelAssetId')
    digest = source.get('sourceSha256')
    source_revision = source.get('revision')
    if (not isinstance(model_id, str) or not model_id.isdecimal() or int(model_id) <= 0
            or not isinstance(digest, str) or len(digest) != 64
            or any(c not in '0123456789abcdef' for c in digest.lower())
            or type(source_revision) is not int or source_revision <= 0):
        raise ValueError('published LOD1 source is invalid')
    return {'source_sha256': digest, 'published_sha256': digest,
            'asset_id': model_id, 'moderation_state': source.get('moderationState') or '',
            'revision': expected_revision + 1,
            'reuse_domain': source['domain'], 'reuse_slug': source['slug'],
            'reuse_revision': source_revision}


def distances_valid(steps: tuple[int, ...], hide: int, hysteresis: int,
                    *, minimum: int) -> bool:
    """One LOD transition/hysteresis rule; owner-specific distance UI is preserved."""
    if (not steps or any(type(v) is not int for v in (*steps, hide, hysteresis))
            or not 0 <= hysteresis <= 100 or not minimum <= steps[0]
            or not hide <= 10000 or steps[0] <= hysteresis):
        return False
    thresholds = (*steps, hide)
    return all(b > a and b - a > 2 * hysteresis for a, b in zip(thresholds, thresholds[1:]))
