"""Idempotent, non-destructive canonical _01 migration of published animations.

Purely changes local semantic coordinates and source filenames; no Roblox uploads.
Every old variant=0 becomes version 01; legacy social waiting_a/waiting_01
becomes slot 'waiting', version 01. Distinct version 02 remains untouched.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from animation_store import AnimationStore
from animation_core.common import _clip_id, _binding_id, _canonical_file_stem
from sqlite_connection import connect


def _semantic(slot, scope, variant):
    if scope == 'social' and slot in ('waiting_a', 'waiting_01') and variant == 0:
        return 'waiting', 1
    if scope == 'social' and slot == 'sp_wait_01' and variant == 0:
        return 'sp_wait', 1
    return slot, 1 if variant == 0 else variant


def migrate(root: Path = ROOT) -> int:
    root = Path(root).resolve()
    store = AnimationStore(root)
    with store.connect() as db:
        old = [dict(row) for row in db.execute('''
            SELECT b.id AS binding_id,b.clip_id,b.character_id,b.scope,
                b.weapon_set,b.slot,b.variant,c.name,c.source_path,c.prepared_path
            FROM animation_bindings b JOIN animation_clips c ON c.id=b.clip_id
        ''')]
        updates = []
        for row in old:
            slot, version = _semantic(row['slot'], row['scope'], row['variant'])
            if (slot,version) == (row['slot'],row['variant']):
                continue
            char, scope, weapon = row['character_id'],row['scope'],row['weapon_set']
            item=dict(row,new_slot=slot,new_variant=version,
                new_clip=_clip_id(char,scope,weapon,slot,version),
                new_binding=_binding_id(char,scope,weapon,slot,version),
                new_name=_canonical_file_stem(scope,weapon,slot,version))
            updates.append(item)
        # Validate all unique keys and ownership before touching disk/database.
        targets = {(r['character_id'],r['scope'],r['weapon_set'],r['slot'],r['variant']):r['binding_id'] for r in old}
        new_targets = set()
        old_ids = {r['clip_id'] for r in updates}
        new_ids = set()
        for row in updates:
            key=(row['character_id'],row['scope'],row['weapon_set'],row['new_slot'],row['new_variant'])
            if (key in targets and targets[key]!=row['binding_id']) or key in new_targets:
                raise ValueError('version migration collision at '+str(key))
            new_targets.add(key)
            if (row['new_clip'] in new_ids or (db.execute('SELECT 1 FROM animation_clips WHERE id=?',(row['new_clip'],)).fetchone() and row['new_clip'] not in old_ids)):
                raise ValueError('version migration clip collision: '+row['new_clip'])
            new_ids.add(row['new_clip'])
        shares=[dict(x) for x in db.execute('SELECT * FROM animation_shared_bindings')]
        updated_by_binding={r['binding_id']:r for r in updates}
        shared_keys=set()
        for share in shares:
            converted = updated_by_binding.get(share['source_binding_id'])
            key=(share['family'],share['scope'],share['weapon_set'],
                 converted['new_slot'] if converted else share['slot'],
                 converted['new_variant'] if converted else share['variant'])
            if key in shared_keys:raise ValueError('version migration shared collision: '+str(key))
            shared_keys.add(key)
    if not updates:
        print('m470: animation variants already canonical, nothing to migrate')
        return 0

    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=root/'.control-center/backups'/('m470_animation_versions_'+stamp+'.db')
    backup.parent.mkdir(parents=True,exist_ok=True)
    with store.connect() as source, connect(backup) as destination:
        source.backup(destination)

    # Physical sources may have been excluded from a diagnostic dump. Keep the
    # current file path in that case rather than inventing a missing path.
    moves=[]
    for row in updates:
        replacements={}
        for field in ('source_path','prepared_path'):
            old_path=str(row[field] or '')
            old_name=Path(old_path).name
            if not old_path or not old_name.startswith(row['name']+'.'):
                replacements[field]=old_path
                continue
            new_path=str(Path(old_path).with_name(row['new_name']+old_name[len(row['name']):])).replace('\\','/')
            src=(root/old_path).resolve()
            dest=(root/new_path).resolve()
            if not src.is_relative_to(root) or not dest.is_relative_to(root):
                raise ValueError('animation path escaped root')
            if src.is_file() and src != dest:
                if dest.exists():raise ValueError('destination already exists: '+str(dest))
                if (src,dest) not in moves:moves.append((src,dest))
                replacements[field]=new_path
            else:
                replacements[field]=old_path
        row['new_paths']=replacements
    moves.extend((a.with_suffix('.animation.json'),b.with_suffix('.animation.json'))
                 for a,b in list(moves) if a.suffix.lower() in ('.rbxm','.rbxmx') and a.with_suffix('.animation.json').is_file())
    if len({b for _,b in moves})!=len(moves):raise ValueError('duplicate migration destinations')
    for _,dest in moves:
        if dest.exists():raise ValueError('sidecar destination already exists: '+str(dest))

    moved=[]
    sidecars_original={}
    try:
        for src,dest in moves:
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.move(src,dest)
            moved.append((src,dest))
            if dest.name.endswith('.animation.json'):
                raw=dest.read_bytes()
                data=json.loads(raw.decode('utf8'))
                for row in updates:
                    if data.get('clip_name')==row['name']:
                        data['clip_name']=row['new_name']
                        sidecars_original[dest]=raw
                        dest.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
                        break
        with store.connect() as db:
            # Avoid changing unique keys in-place when two rows exchange key forms.
            for row in updates:
                db.execute('UPDATE animation_publications SET clip_id=? WHERE clip_id=?',(row['new_clip'],row['clip_id']))
                for doc in db.execute('SELECT * FROM animation_clip_documents WHERE clip_id=?',(row['clip_id'],)):
                    document=json.loads(doc['document_json'])
                    if document.get('clip_name')==row['name']:
                        document['clip_name']=row['new_name']
                    source=root/row['new_paths']['source_path']
                    sidecar=source.with_suffix('.animation.json')
                    digest=hashlib.sha256(sidecar.read_bytes()).hexdigest() if sidecar.is_file() else doc['document_sha256']
                    db.execute('''UPDATE animation_clip_documents SET clip_id=?,document_json=?,document_sha256=?
                        WHERE clip_id=? AND animation_sha256=?''',
                        (row['new_clip'],json.dumps(document,ensure_ascii=False),digest,row['clip_id'],doc['animation_sha256']))
                db.execute('''UPDATE animation_shared_bindings SET slot=?,variant=?,source_binding_id=?
                    WHERE source_binding_id=?''',(row['new_slot'],row['new_variant'],row['new_binding'],row['binding_id']))
                db.execute('UPDATE animation_bindings SET id=?,slot=?,variant=?,clip_id=? WHERE id=?',
                           (row['new_binding'],row['new_slot'],row['new_variant'],row['new_clip'],row['binding_id']))
                db.execute('''UPDATE animation_clips SET id=?,name=?,source_path=?,prepared_path=?
                    WHERE id=?''',(row['new_clip'],row['new_name'],row['new_paths']['source_path'],
                                 row['new_paths']['prepared_path'],row['clip_id']))
        store.export()
    except Exception:
        for src,dest in reversed(moved):
            if dest.is_file():
                if dest in sidecars_original:dest.write_bytes(sidecars_original[dest])
                shutil.move(dest,src)
        raise
    print('m470: migrated',len(updates),'animation slots; sqlite backup:',backup)
    print('m470: all published Roblox asset ids and publication histories preserved')
    return len(updates)


if __name__=='__main__':
    migrate()
