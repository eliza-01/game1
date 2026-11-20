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
    if not source.is_file() or source.suffix.lower() != '.fbx' or source.name != expected_name:
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
