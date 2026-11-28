"""Preparation only: a reviewed posed assembly and its shared atlas → static LOD1.

Persistence/publication remain in MnpcLodResource. No implicit rest-pose or
material inference; pose/weapon assembly and actual Roblox alignment are open.
"""
from pathlib import Path
from PIL import Image
from .fbx_blender_report import run_report
from .model_lod_common import MAX_FBX_BYTES, preserve_source, sha256
from . import mnpc_lod_geometry as geometry


FIELDS = {'posePath', 'texturePath', 'frame', 'targetTriangles', 'textureSize',
          'expectedRevision', 'fullFingerprint', 'reviewedAssembly'}


def validate_request(payload):
    if not isinstance(payload, dict) or set(payload) != FIELDS:
        raise ValueError('Prepare requires posed assembly, atlas, frame, triangle target, texture size and reviewed FULL revision')
    if payload['reviewedAssembly'] is not True:
        raise ValueError('Confirm that the posed assembly includes the current FULL appearance and equipment, using the supplied common atlas')
    for key, lo, hi in [('frame', -100000, 100000), ('targetTriangles', 100, 10000)]:
        if type(payload[key]) is not int or not lo <= payload[key] <= hi:
            raise ValueError(f'{key} must be an integer in {lo}–{hi}')
    if type(payload['textureSize']) is not int or payload['textureSize'] not in (128, 256, 512, 1024):
        raise ValueError('textureSize must be 128, 256, 512 or 1024')
    for key in ('posePath', 'texturePath'):
        if not isinstance(payload[key], str) or not payload[key].strip():
            raise ValueError(f'Choose {key}')


def prepare(root: Path, slug: str, payload: dict, directory: Path):
    validate_request(payload)
    source = Path(payload['posePath']).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != '.fbx' or not 0 < source.stat().st_size <= MAX_FBX_BYTES:
        raise ValueError('Choose a posed FULL assembly FBX (max 200 MB)')
    with source.open('rb') as stream:
        header = stream.read(4096)
    if not (header.startswith(b'Kaydara FBX Binary') or b'FBXHeaderExtension' in header):
        raise ValueError('Posed assembly is not an FBX')
    source_sha = sha256(source)
    texture, texture_sha, _, _, ext = geometry.texture_info(payload['texturePath'])
    # Snapshot exact bytes before Blender; no mutation of registered FULL.
    # External FBX images are deliberately not used by this geometry-only worker.
    pose_snapshot = directory / 'assembly.fbx'
    atlas_snapshot = directory / ('source_atlas' + ext)
    preserve_source(source, pose_snapshot, directory / '_unused_pose', source_sha)
    preserve_source(texture, atlas_snapshot, directory / '_unused_atlas', texture_sha)
    output = directory / f'{slug}_lod1.fbx'
    atlas = directory / 'lod1.png'
    report_path = directory / 'prepare.json'
    report = run_report(root, 'prepare_mnpc_lod_fbx.py',
        (pose_snapshot, output, report_path, str(payload['frame']), str(payload['targetTriangles'])),
        report_path=report_path, label='MNPC LOD1 preparation', timeout=120)
    if not isinstance(report, dict) or report.get('schemaVersion') != 1 or report.get('poseMode') not in ('embedded_frame','posed_static'):
        raise ValueError('Invalid MNPC preparation report')
    g = geometry.validate(report.get('geometry'))
    before = report.get('inputTriangles')
    meshes = report.get('inputMeshes')
    if (type(before) is not int or not g['triangles'] <= before <= 500000 or
            type(meshes) is not int or not 1 <= meshes <= 64 or g['triangles'] > payload['targetTriangles']):
        raise ValueError('Preparation did not meet geometry budget')
    if not output.is_file():
        raise ValueError('Prepared LOD1 FBX missing')
    # Do not upscale. Preserve aspect/UV and alpha; no lighting baked into color.
    with Image.open(atlas_snapshot) as image:
        rgba = image.convert('RGBA')
        rgba.thumbnail((payload['textureSize'], payload['textureSize']), Image.Resampling.LANCZOS)
        rgba.save(atlas, format='PNG')
        out_size = list(rgba.size)
    if sha256(source) != source_sha or sha256(texture) != texture_sha:
        raise ValueError('Preparation inputs changed; retry with the current assembly')
    recipe = {'schemaVersion': 1, 'mode': report['poseMode'], 'poseSha256': source_sha,
              'atlasSha256': texture_sha, 'frame': payload['frame'], 'targetTriangles': payload['targetTriangles'],
              'textureSize': payload['textureSize'], 'outputTextureSize': out_size,
              'inputTriangles': before, 'inputMeshes': meshes, 'reviewedAssembly': True}
    return output, atlas, recipe, g, sha256(output)
