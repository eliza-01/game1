"""Read-only projection of saved LOD settings for the local Studio Play bridge.

No placement snapshot, authoring paths, credentials or mutable runtime state.
The compiler remains the authority for actual Runtime Place preparation.
"""
from .location_streaming_config import runtime_mode, distance_profile, published_id
from .house_part_distances import validate
import hashlib
import json


def snapshot(manager):
    assets = manager.assets.snapshot()['items']
    settings = manager.read_settings(assets)
    locations = {}
    for asset in assets:
        slug = asset['slug']
        locations[slug] = {'mode': runtime_mode(settings, slug),
                           'distances': distance_profile(settings, slug),
                           'lod1': published_id(asset.get('lod1')),
                           'lod2': published_id(asset.get('lod2'))}
    houses = {}
    for house in manager.houses.list() if manager.houses else []:
        parts = {}
        for name in house['meshParts']:
            slot = house['partStreaming'][name]
            parts[name] = {**validate({'lod1': slot['lod1'], 'hide': slot['hide']}),
                           'assetId': published_id(house['partLod1'].get(name))}
        houses[house['slug']] = {'mode': house['runtimeProfile']['mode'], 'parts': parts}
    active_ids = {value for row in locations.values() for value in
                  ((row['lod1'], row['lod2']) if row['mode'] == 'lod2' else
                   (row['lod1'],) if row['mode'] == 'lod1' else ()) if value}
    active_ids.update(part['assetId'] for row in houses.values() if row['mode'] == 'lod1'
                      for part in row['parts'].values() if part['assetId'])
    if len(active_ids) > 256:
        raise ValueError('Studio LOD preview exceeds 256 active LOD prototypes')
    payload = {'schemaVersion': 2, 'hysteresis': settings['hysteresis'],
               'locations': locations, 'houses': houses}
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    payload['digest'] = hashlib.sha256(encoded.encode()).hexdigest()
    if len(encoded) > 170000:
        raise ValueError('Studio LOD preview configuration exceeds size limit')
    return payload
