"""Cross-store deletion impact and explicitly authorized retirement orchestration.

Images belong exclusively to Atlas Registry. Model deletion only removes its
binding; shared consumers are informational and are never cascade targets.
"""
from __future__ import annotations

import hashlib
import json



def _node(kind, slug):
    return f'{kind}:{slug}'


class SharedAssetRetirement:
    def __init__(self, real_estate, location_assets, publication_jobs=None):
        self.real_estate = real_estate
        self.location_assets = location_assets
        self.jobs = publication_jobs

    def _graph(self):
        """Graph contains only model registrations; atlas use is not ownership."""
        nodes = {}
        for row in self.location_assets.list():
            key = _node('location', row['slug'])
            nodes[key] = {'kind': 'location', 'slug': row['slug'],
                'label': row.get('name_en') or row['slug'],
                'revision': int(row.get('revision') or 0),
                'textureId': str(row.get('texture_asset_id') or ''),
                'textureFilename': str(row.get('texture_filename') or ''),
                'atlasKey': str(row.get('atlasFamily') or ''),
                'atlasVariantId': int(row.get('atlasVariantId') or 0),
                'atlasBindingRevision': int(row.get('bindingRevision') or 0)}
        for row in self.real_estate.list():
            key = _node('estate', row['slug'])
            nodes[key] = {'kind': 'estate', 'slug': row['slug'],
                'label': row['slug'], 'revision': int(row.get('revision') or 0),
                'textures': {part: {'assetId': str(tex.get('assetId') or ''),
                    'filename': str(tex.get('filename') or ''),
                    'atlasKey': str(tex.get('atlasKey') or ''),
                    'atlasVariantId': int(tex.get('atlasVariantId') or 0),
                    'atlasBindingRevision': int(tex.get('atlasBindingRevision') or 0)}
                    for part,tex in row.get('textures',{}).items()}}
        return nodes, {}

    def plan(self, kind: str, slug: str) -> dict:
        if kind not in ('location', 'estate'):
            raise ValueError('invalid asset kind')
        root = _node(kind, str(slug).strip().lower())
        nodes, edges = self._graph()
        if root not in nodes:
            raise ValueError('unknown asset registration')
        visited, active, ordered, relations = set(), set(), [], []

        def walk(node):
            if node in active:
                raise ValueError('cyclic texture references: resolve them before deleting everything')
            if node in visited:
                return
            active.add(node)
            for dependent, part, owner_part in edges.get(node, []):
                if dependent not in nodes:
                    continue
                relations.append({'owner': node, 'dependent': dependent, 'part': part, 'ownerPart': owner_part})
                walk(dependent)
            active.remove(node)
            visited.add(node)
            ordered.append(node)

        walk(root)
        # Central Atlas Registry separates shared-use visibility from legacy
        # owner/dependent deletion edges. A consumer of the same published
        # image must NEVER become a cascade-delete target merely for sharing it.
        owned = nodes[root]
        images = ([{'assetId': owned['textureId'], 'filename': owned['textureFilename'],
                    'atlasKey': owned['atlasKey'],
                    'atlasVariantId': owned['atlasVariantId']}] if kind == 'location' else
                  list(owned['textures'].values()))
        shared_uses = []
        seen_ids = set()
        for image in images:
            image_id = str(image.get('assetId') or '')
            variant_id = int(image.get('atlasVariantId') or 0)
            identity = ('variant', variant_id) if variant_id else ('image', image_id)
            if identity in seen_ids or (not variant_id and not image_id):
                continue
            seen_ids.add(identity)
            uses = []
            for key, other in nodes.items():
                if key == root:
                    continue
                if other['kind'] == 'location':
                    if ((variant_id and int(other.get('atlasVariantId') or 0) == variant_id)
                            or (not variant_id and str(other.get('textureId') or '') == image_id)):
                        uses.append({'dependent': key, 'part': 'texture'})
                else:
                    for part, texture in other['textures'].items():
                        if ((variant_id and int(texture.get('atlasVariantId') or 0) == variant_id)
                                or (not variant_id and str(texture.get('assetId') or '') == image_id)):
                            uses.append({'dependent': key, 'part': part})
            if uses:
                shared_uses.append({'assetId': image_id, 'variantId': variant_id,
                    'filename': image.get('filename') or '',
                    'atlasKey': image.get('atlasKey') or '', 'uses': uses})
        # Root is last. All legacy dependents are retired before their owners;
        # independently bound atlas consumers are informational only.
        payload = {'root': root, 'nodes': [nodes[n] for n in ordered],
                   'relations': relations, 'sharedAtlasUses': shared_uses}
        token = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        return {**payload, 'dependentCount': len(ordered)-1, 'token': token,
                'defaultMode': 'preserve', 'sourceFilesPreserved': True}

    def _check_ready(self, entries):
        for entry in entries:
            if entry['kind'] != 'estate':
                continue
            slug = entry['slug']
            if self.real_estate._pending_publication_for_house(slug):
                raise ValueError(f'{slug}: unresolved publication; resolve it before retirement')
            if self.jobs is not None:
                job = self.jobs.get(slug)
                if job and job.get('status') in ('queued', 'running'):
                    raise ValueError(f'{slug}: publication is running')

    def execute(self, kind: str, slug: str, *, mode: str = 'preserve', token: str = '') -> dict:
        if mode not in ('preserve', 'all'):
            raise ValueError('unknown retirement mode')
        plan = self.plan(kind, slug)
        # Stale confirmation must not delete a different dependency tree.
        if (mode == 'all' and not token) or (token and token != plan['token']):
            raise ValueError('dependencies changed; review the deletion dialog again')
        entries = plan['nodes'] if mode == 'all' else [plan['nodes'][-1]]
        self._check_ready(entries)
        # Shared atlas use is informational, not a deletion edge. There are
        # no owner registrations and nothing to detach before deleting models.
        deleted = []
        for entry in entries:
            key = _node(entry['kind'], entry['slug'])
            if entry['kind'] == 'estate':
                result = self.real_estate.delete(entry['slug'])
            else:
                result = self.location_assets.delete(entry['slug'])
            deleted.append({'kind': entry['kind'], 'slug': entry['slug'],
                            'archive': (result or {}).get('archived', '')})
        return {'ok': True, 'mode': mode, 'deleted': deleted,
                'dependentCount': plan['dependentCount'],
                'sharedImagesPreserved': True,
                'sourceFilesPreserved': True}
