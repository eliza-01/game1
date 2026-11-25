"""M481: idempotent authoring migration for two scene preview points.

It only replaces M480's placeholder points (or invalid overlapping origins),
keeps explicit user-authored placements, and always regenerates the Runtime
GameOptionsRegistry using the established OptionsStore writer.
"""
from __future__ import annotations
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'system/control-center'))
from options_store import OptionsStore

POINTS={
    'male': {'position':[179.449,-314.025,176.096], 'rotationDegrees':[0.0,-35.501,0.0]},
    'female': {'position':[177.64,-314.025,167.78], 'rotationDegrees':[0.0,-93.433,0.0]},
}
OLD={
    'male': {'position':[178.0,-311.0,173.0], 'rotationDegrees':[0.0,135.0,0.0]},
    'female': {'position':[180.0,-311.0,165.0], 'rotationDegrees':[0.0,65.0,0.0]},
}

def _placeholder(value, gender):
    if not isinstance(value,dict):
        return True
    pos=value.get('position')
    rot=value.get('rotationDegrees')
    if pos==OLD[gender]['position'] and rot==OLD[gender]['rotationDegrees']:
        return True
    return pos==[0,0,0] and rot==[0,0,0]

def migrate(root: Path=ROOT):
    # OptionsStore._ensure may itself normalize and write missing fields.
    # Capture the original file BEFORE constructing it.
    manifest=root/'assets/manifests/options.json'
    raw=json.loads(manifest.read_text(encoding='utf-8'))
    original=raw.get('characterCreation') or {}
    original_points=original.get('spawnPoints') or {}
    needs_backup=(not original.get('spawnPoints') or
        any(_placeholder(original_points.get(gender),gender) for gender in ('male','female')) or
        original.get('desktopPanelWidthPx') == 340 or original.get('mobilePanelWidthPx') == 290)
    backup=None
    if needs_backup:
        backup=manifest.with_suffix('.json.pre-m481-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.bak')
        backup.write_bytes(manifest.read_bytes())
    store=OptionsStore(root)
    current=store.snapshot()['characterCreation']
    updated=copy.deepcopy(current)
    points=updated['spawnPoints']
    changed=[]
    for gender in ('male','female'):
        if _placeholder(points.get(gender),gender):
            points[gender]=copy.deepcopy(POINTS[gender])
            changed.append(gender)
    if changed:
        # Existing scene markers were not authored in this workflow; use the
        # exact coordinates recorded from the two Studio model pivots instead.
        updated['useStudioSpawnMarkers']=False
    if updated['desktopPanelWidthPx'] == 340:
        updated['desktopPanelWidthPx']=460
    if updated['mobilePanelWidthPx'] == 290:
        updated['mobilePanelWidthPx']=330
    if updated != current:
        store.update({'characterCreation':updated})
        print('m481: migrated '+(', '.join(changed) if changed else 'panel widths')+
              ('; backup: '+str(backup) if backup else ''))
    else:
        print('m481: points and panel settings verified'+
              ('; backup: '+str(backup) if backup else ''))
    # Ensures an already-running M480's stale generated registry is repaired
    # even when the manifest was correct or intentionally user-authored.
    store=OptionsStore(root)
    assert 'spawnPoints = table.freeze({' in (root/'src/shared/GameOptionsRegistry.luau').read_text()
    return store.snapshot()['characterCreation']

if __name__=='__main__': migrate()
