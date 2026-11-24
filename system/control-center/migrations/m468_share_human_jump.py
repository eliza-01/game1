"""Additive, idempotent: promote two published female jump clips to human common."""
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'system/control-center'))
from animation_store import AnimationStore
from sqlite_connection import connect


def migrate(root: Path = ROOT):
    root = Path(root)
    store = AnimationStore(root)
    with store.connect() as db:
        bindings = db.execute("""SELECT b.id,b.slot FROM animation_bindings b
                 JOIN animation_clips c ON c.id=b.clip_id
                 WHERE b.character_id='human_female' AND b.scope='base'
                   AND b.slot IN ('jump_start','jump_loop')
                   AND c.asset_id IS NOT NULL AND c.published_sha256=c.sha256""").fetchall()
    found={row['slot']:row['id'] for row in bindings}
    if set(found)!={'jump_start','jump_loop'}:
        raise ValueError('both published human_female jump_start and jump_loop are required')
    # Check everything before changing any mappings.
    from animation_core.shared import compatible_rigs
    import json
    with store.connect() as db:
        source=json.loads(db.execute("SELECT metadata_json FROM character_component_records WHERE kind='rig' AND id='human_female'").fetchone()[0])['bones']
        target=json.loads(db.execute("SELECT metadata_json FROM character_component_records WHERE kind='rig' AND id='human_male'").fetchone()[0])['bones']
    for slot in found:compatible_rigs(source,target,scope='base',slot=slot)
    current={r['slot']:r['source_binding_id'] for r in store.shared_rows('human') if r['scope']=='base' and r['slot'] in found}
    if current==found:
        print('m468: human common jump already migrated')
        return store.shared_rows('human')
    backup = root/'.control-center'/'backups'/('m468_animation_shared_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.db')
    backup.parent.mkdir(parents=True,exist_ok=True)
    with store.connect() as source, connect(backup) as target:source.backup(target)
    for slot in ('jump_start','jump_loop'):
        store.set_shared(found[slot], True)
    print('m468: human common jump_start/jump_loop -> published female source ids, backup:',backup)
    return store.shared_rows('human')

if __name__=='__main__':migrate()
