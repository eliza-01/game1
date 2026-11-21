"""House-level streaming switch; per-MeshPart distances belong to LOD Manager.

The old SQLite lod1/hide/hysteresis columns are legacy migration inputs only.
The shared LocationWorldStreamer owns all runtime state changes.
"""
from __future__ import annotations
from real_estate.contracts import HOUSE_NAME
from services.house_part_distances import validate as validate_part

DEFAULT={'mode':'off'}
MODES=('off','full','lod1')


def validate(slug: str, value: dict) -> dict:
    if not isinstance(slug,str) or not HOUSE_NAME.fullmatch(slug):
        raise ValueError('invalid house type')
    if not isinstance(value,dict) or set(value) != {'mode'} or value['mode'] not in MODES:
        raise ValueError('expected house streaming mode')
    return {'mode':value['mode']}


def readiness(house:dict, settings:dict, part_lods:dict) -> dict:
    warnings=[]
    if house['status']!='PUBLISHED':
        warnings.append('Publish all house meshes and atlases before Runtime build')
    mode=settings['mode']
    active=0
    for part in house.get('meshParts',[]):
        slot=(house.get('partStreaming') or {}).get(part)
        if not slot:
            warnings.append(f'{part}: missing LOD Manager distances')
        else:
            try: validate_part({'lod1':slot['lod1'],'hide':slot['hide']})
            except (ValueError,KeyError) as exc: warnings.append(f'{part}: {exc}')
        if mode=='lod1':
            status=(part_lods.get(part) or {}).get('status','NOT_REGISTERED')
            if status=='PUBLISHED': active+=1
            elif status!='NOT_REGISTERED':
                warnings.append(f'{part}: LOD1 is {status}; publish it or reset the stale slot')
    if mode=='lod1' and active==0:
        warnings.append('Publish or reuse a per-part LOD1 model for at least one house part')
    return {'readyForCompilation': not warnings and mode!='off',
            'runtimeVerified': False, 'warnings': warnings}
