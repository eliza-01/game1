"""Immutable, per-mesh FBX revisions for Real Estate.

A complete Blender scene may be selected, but only the explicitly requested
mesh is extracted. Other published meshes retain their own source and ID.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import tempfile

from .contracts import validate_analysis
from .fbx import inspect_selected


def inspect_revision(root: Path, source: Path, part: str) -> dict:
    if not source.is_file() or source.suffix.lower() != '.fbx':
        raise ValueError('select an existing FBX source file')
    analysis = inspect_selected(root, source, part)
    if not isinstance(analysis, dict) or len(analysis.get('meshes', [])) != 1:
        raise ValueError(f'FBX must contain exactly one selected mesh {part}')
    mesh = analysis['meshes'][0]
    if mesh.get('name') != part:
        raise ValueError(f'Expected mesh {part}; found {mesh.get("name")}')
    # Use the standard validator for the house, and the same field-level
    # invariants for other meshes (a standalone FBX need not include house).
    if part == 'house':
        validate_analysis(analysis)
    elif (int(mesh.get('vertices') or 0) < 3 or not isinstance(mesh.get('bones'), list)
          or any(not isinstance(b, dict) or not isinstance(b.get('name'), str)
                 for b in mesh['bones'])):
        raise ValueError(f'{part}: invalid mesh/bone analysis')
    return mesh


def save_immutable(root: Path, slug: str, part: str, source: Path) -> dict:
    """Save a content-addressed snapshot before any DB reference is updated."""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    folder = root / 'assets' / 'source' / 'real-estate' / slug / 'mesh-revisions' / part
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (digest + '.fbx')
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise RuntimeError('Stored FBX revision checksum mismatch; refusing to use it')
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=folder, suffix='.tmp', delete=False) as file:
            candidate = Path(file.name)
        try:
            shutil.copyfile(source, candidate)
            if hashlib.sha256(candidate.read_bytes()).hexdigest() != digest:
                raise RuntimeError('FBX changed while creating its immutable snapshot; retry')
            os.replace(candidate, target)
        finally:
            candidate.unlink(missing_ok=True)
    return {'path': target.relative_to(root).as_posix(), 'sha256': digest}
