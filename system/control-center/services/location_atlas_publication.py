"""First publication of a Location Asset's active or connected atlas.

The AtlasRegistry owns uploads and history. The consumer binding revision guards
stale editor actions. An explicit request for a connected variant publishes its
Image ID, but never silently changes the active atlas or Model publication.
"""
from __future__ import annotations


def publish_pending_atlas(location_assets, slug: str, *, variant_id: int,
                          expected_revision: int, credentials: dict,
                          exports=()) -> dict:
    item = location_assets.get(slug)
    if not item:
        raise ValueError('unknown Location Asset')
    binding = location_assets.atlases.binding('location_asset', slug)
    if not binding:
        raise ValueError('Location Asset has no atlas binding; reopen the asset')
    if int(binding['revision']) != expected_revision:
        raise ValueError('atlas binding changed; refresh and review the selected atlas')
    # The shared picker displays connected variants and other resolutions from
    # the active atlas family. Only those may be explicitly published here.
    # No variant switch or Model publication is performed by this operation.
    if not any(int(v['id']) == variant_id for v in
               location_assets.atlases.attached_variants('location_asset', slug)):
        raise ValueError('atlas is not connected to this Location Asset')
    # Registry performs the publication under its upload lock. In particular
    # the first-publication contract must not republish an existing shared ID.
    published = location_assets.atlases.publish_initial(
        variant_id, credentials, f'Location Asset {slug} atlas')
    warnings = []
    for name, export in exports:
        try:
            export()
        except Exception as error:
            # Upload already succeeded. Do not return a retry-inducing 400.
            warnings.append(f'{name} registry export failed after publication: {error}')
    return {'resourceKind': 'Atlas', 'variant': published,
            'publishedAssetId': str(published['published_id']),
            'studioSyncRequired': True, 'exportWarnings': warnings}
