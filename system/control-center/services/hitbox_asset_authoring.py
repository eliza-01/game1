"""Revision-pinned authoring of MNPC hitbox definitions through Studio Edit.

The native oracle builds the same FULL rig as Runtime. No LOD1 geometry,
FBX approximation, cloud upload, workspace edit or automatic fallback import.
"""
import json

from . import hitbox_asset_registry as registry
from .mnpc_capture_bridge import request_studio


def _identity(kind, slug, row):
    if not row.get('fullFingerprint') or row.get('fullStatus') != 'PUBLISHED':
        raise ValueError('Publish and sync the FULL model first')
    full = row['fullIdentity']
    return dict(kind=kind, slug=slug, fullFingerprint=row['fullFingerprint'],
                modelId=full['modelId'],
                equipment={hand: {'slug': item['slug'], 'modelId': item['visual']['modelId']}
                           for hand, item in full.get('equipment', {}).items() if item})


def capture_from_studio(command):
    return request_studio(command, command_name='hitbox-capture-v1', result_path='/hitbox-capture-result',
                          identity_keys=('kind', 'slug', 'fullFingerprint', 'modelId'),
                          result_key='capture', timeout_seconds=110)


def capture(owner, kind, slug, payload, *, bridge=None, destination=registry.REGISTRY):
    if not isinstance(payload, dict) or set(payload) != {'fullFingerprint'}:
        raise ValueError('Capture requires current FULL fingerprint')
    with owner._lock:
        command = _identity(kind, slug, owner.describe(kind, slug))
        if payload['fullFingerprint'] != command['fullFingerprint']:
            raise ValueError('FULL changed; refresh and sync Model + Atlas')
        raw = (bridge or capture_from_studio)(command)
        data = registry.normalize(raw)
        if len(data['entries']) != 1:
            raise ValueError('Expected one exact authoring assembly')
        row = data['entries'][0]
        # Match the registry identity in addition to the authenticated bridge
        # envelope. The signature itself carries actual published MeshIds.
        if not row['key'].endswith('|identity:' + slug + '|head:' + _head_name(row) + '|parent:' + _parent_name(row)):
            raise ValueError('Capture belongs to a different actor')
        if _identity(kind, slug, owner.describe(kind, slug)) != command:
            raise ValueError('FULL or equipment changed during capture; retry')
        total = registry.import_payload(data, destination)
        definition = row['definition']
        return {'status': 'CAPTURED', 'entries': total, 'bodyBoxes': len(definition['bodyBoxes']),
                'headBox': 'headBox' in definition, 'vertices': definition['sourceVertexCount'],
                'nativeCoverage': 'NOT_RUN'}


def _head_name(row):
    head = json.loads(row['signature'])[2]
    return head[-1] if head else ''


def _parent_name(row):
    parent = json.loads(row['signature'])[3]
    return parent[-1] if parent else ''
