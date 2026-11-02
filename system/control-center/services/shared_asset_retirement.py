"""Cross-store deletion impact and explicitly authorized retirement orchestration.

A shared image is an independent publication identity, NOT owned by the model
that first selected it. Preserve mode retains legacy references without deleting
any dependent model. Cascade mode retires all dependent registrations first.
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
        nodes = {}
        edges = {}
        for row in self.location_assets.list():
            key = _node('location', row['slug'])
            nodes[key] = {'kind': 'location', 'slug': row['slug'], 'label': row.get('name_en') or row['slug'],
                          'revision': int(row.get('revision') or 0),
                          'textureId': str(row.get('texture_asset_id') or ''),
                          'textureReference': str(row.get('texture_reference_slug') or ''),
                          'atlasBindingRevision': int(row.get('bindingRevision') or 0)}
            ref = str(row.get('texture_reference_slug') or '')
            # A direct AtlasRegistry binding supersedes historical owner reuse.
            if ref and not self.location_assets.atlases.binding('location_asset', row['slug']):
                edges.setdefault(_node('location', ref), []).append((key, 'texture', ''))
        for row in self.real_estate.list():
            key = _node('estate', row['slug'])
            nodes[key] = {'kind': 'estate', 'slug': row['slug'], 'label': row['slug'],
                          'revision': int(row.get('revision') or 0),
                          'textures': {part: {'reuseReference': str(tex.get('reuseReference') or ''),
                                              'assetId': str(tex.get('assetId') or ''),
                                              'atlasBindingRevision': int(tex.get('atlasBindingRevision') or 0)}
                                       for part, tex in row.get('textures', {}).items()}}
            for part, texture in row.get('textures', {}).items():
                ref = str(texture.get('reuseReference') or '')
                if ref.startswith('location:'):
                    owner = ref
                elif ref.startswith('estate:'):
                    owner = _node('estate', ref.split(':', 2)[1])
                else:
                    continue
                edges.setdefault(owner, []).append((key, part, ref.split(':', 2)[2] if ref.startswith('estate:') else ''))
        return nodes, edges

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
        # Root is last. All dependents are retired before the owners they refer to.
        payload = {'root': root, 'nodes': [nodes[n] for n in ordered], 'relations': relations}
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
        deleted = []
        for entry in entries:
            key = _node(entry['kind'], entry['slug'])
            # Retain only references still needed by surviving consumers.
            if mode == 'preserve':
                referenced = [r for r in plan['relations'] if r['owner'] == key]
            else:
                referenced = []
            if entry['kind'] == 'estate':
                parts = {r['ownerPart'] for r in referenced}
                result = self.real_estate.delete(entry['slug'], retain_parts=parts)
            else:
                result = self.location_assets.delete(entry['slug'],
                                                     retain_shared=bool(referenced))
            deleted.append({'kind': entry['kind'], 'slug': entry['slug'],
                            'archive': (result or {}).get('archived', '')})
        return {'ok': True, 'mode': mode, 'deleted': deleted,
                'dependentCount': plan['dependentCount'],
                'sharedImagesPreserved': mode == 'preserve',
                'sourceFilesPreserved': True}
