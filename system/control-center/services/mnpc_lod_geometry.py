"""MNPC-specific static geometry contract over the shared Blender boundary."""
from __future__ import annotations
import math
from pathlib import Path
from .fbx_blender_report import inspect_report
from .model_lod_common import sha256
from .texture_atlas_registry import image_metadata
from PIL import Image


def inspect(root: Path, source: Path) -> dict:
    report = inspect_report(root, 'analyze_mnpc_lod_fbx.py', source, label='MNPC LOD1 FBX')
    return validate(report)


def validate(report: dict) -> dict:
    if not isinstance(report, dict) or report.get('schemaVersion') != 1 or report.get('meshName') != 'lod1' or report.get('meshes') != 1 or report.get('armatures') != 0:
        raise ValueError('LOD1 inspection must prove exactly one static lod1 mesh')
    for name in ('vertices', 'triangles'):
        if type(report.get(name)) is not int or not 1 <= report[name] <= 20000:
            raise ValueError(f'LOD1 {name}: expected 1–20000 (authoring safety limit)')
    if report['vertices'] < 3:
        raise ValueError('LOD1 needs at least 3 vertices')
    for name in ('boundsMin', 'boundsMax'):
        v = report.get(name)
        if not isinstance(v, list) or len(v) != 3 or any(type(n) not in (int, float) or not math.isfinite(n) for n in v):
            raise ValueError('Invalid LOD1 FBX bounds')
    if any(b <= a for a, b in zip(report['boundsMin'], report['boundsMax'])):
        raise ValueError('LOD1 must have nonzero size on all axes')
    return {key: report[key] for key in ('schemaVersion','meshName','meshes','armatures','vertices','triangles','boundsMin','boundsMax')}


def texture_info(source_path: str) -> tuple[Path, str, int, int, str]:
    path = Path(str(source_path or '')).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in ('.png', '.jpg', '.jpeg') or not 0 < path.stat().st_size <= 20 * 1024 * 1024:
        raise ValueError('Choose a baked PNG/JPEG texture (max 20 MB)')
    try:
        with Image.open(path) as image:
            w, h = image.size
            native_format = image.format
        if native_format not in ('PNG', 'JPEG') or not 1 <= w <= 4096 or not 1 <= h <= 4096:
            raise ValueError('LOD1 texture must be a PNG/JPEG, up to 4096 × 4096')
        ext = '.png' if native_format == 'PNG' else '.jpg'
        if path.suffix.lower() not in ({'.png'} if ext == '.png' else {'.jpg', '.jpeg'}):
            raise ValueError('LOD1 texture extension does not match its format')
        image_metadata(path, {'width': w, 'height': h})
    except (OSError, Image.DecompressionBombError) as error:
        raise ValueError(f'Cannot read LOD1 texture: {error}') from error
    return path, sha256(path), w, h, ext


def validate_staged(publication: Path, report: dict) -> None:
    manifest = report.get('locationRigManifest') or {}
    parts = manifest.get('parts') or []
    if (manifest.get('rigKind') != 'static' or manifest.get('bones') != [] or
            len(parts) != 1 or parts[0].get('name') != 'lod1' or parts[0].get('role') != 'visual'):
        raise ValueError('Published FBX round-trip did not preserve one static lod1 mesh')
    if not 0 < publication.stat().st_size <= 20 * 1024 * 1024:
        raise ValueError('Prepared LOD1 FBX exceeds Open Cloud upload limit (20 MB)')
