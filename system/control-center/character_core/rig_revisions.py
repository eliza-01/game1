"""Rig revision staging and published-history lookup. No cloud upload ownership."""
import hashlib
import json
from pathlib import Path
import shutil
import time
import uuid
from character_core.part_names import TOKEN, rig_id, skeleton_matches
from character_core.component_fbx import inspect_fbx
from sqlite_connection import connect


def published_rig(components, key, revision=None):
    row = components.get('rig', key)
    if not row:
        return None
    if revision is not None and (type(revision) is not int or revision < 1):
        return None
    wanted = revision if revision is not None else (row['published_revision'] or row['revision'])
    if row['revision'] == wanted and (revision is None or row['published_revision'] == wanted):
        return row
    with connect(components.db) as db:
        saved = db.execute('''SELECT record_json FROM character_component_history
            WHERE kind='rig' AND component_id=? AND revision=? ORDER BY id DESC LIMIT 1''',
            (key, wanted)).fetchone()
    if not saved:
        return None
    record = json.loads(saved['record_json'])
    if record['published_revision'] != wanted or not str(record['model_asset_id']).isdigit():
        return None
    return record


def stage_rig_revision(components, key, source, *, expected_revision, analyzer=inspect_fbx):
    """Freeze a rig-only FBX; pin existing recipes before replacing its record.

    Idempotent for the same skeleton. Published IDs are owned by the existing
    component publisher; no credentials or network operations occur here.
    """
    old = components.get('rig', key)
    if not old or old['revision'] != expected_revision or old['pending_operation']:
        raise ValueError('rig changed or publication pending; refresh before staging')
    if old['published_revision'] != old['revision']:
        raise ValueError('publish or resolve the staged rig revision first')
    folder = components.root/'assets/source/character_components/rig_revisions'/uuid.uuid4().hex
    folder.mkdir(parents=True)
    artifact = folder/'rig.fbx'
    shutil.copy2(Path(source).resolve(), artifact)
    info = analyzer(components.root, artifact)
    if rig_id(info['armature']) != key or [p['name'] for p in info['parts']] != ['rig_carrier']:
        raise ValueError('expected a rig-only FBX with one rig_carrier mesh')
    bones = info['bones']
    if not bones or len({b['name'] for b in bones}) != len(bones) or any(not TOKEN.fullmatch(b['name']) for b in bones):
        raise ValueError('invalid rig bones')
    previous = json.loads(old['metadata_json'])['bones']
    common = {b['name'] for b in previous} & {b['name'] for b in bones}
    skeleton_matches([b for b in previous if b['name'] in common], [b for b in bones if b['name'] in common])
    digest = hashlib.sha256(json.dumps(bones, sort_keys=True).encode()).hexdigest()
    if digest == old['content_sha256']:
        return dict(changed=False, revision=old['revision'], pinned_characters=[])
    backup = components.db.parent/'backups'/('before_rig_revision_'+uuid.uuid4().hex+'.db')
    backup.parent.mkdir(exist_ok=True)
    with connect(components.db) as db:
        with connect(backup) as target:
            db.backup(target)
    relative = str(artifact.relative_to(components.root))
    pinned = []
    with connect(components.db) as db:
        db.execute('BEGIN IMMEDIATE')
        current = db.execute("SELECT * FROM character_component_records WHERE kind='rig' AND id=?", (key,)).fetchone()
        if dict(current) != old:
            raise ValueError('rig changed during inspection; retry')
        db.execute('''INSERT INTO character_component_history(kind,component_id,revision,record_json,changed_at)
            VALUES('rig',?,?,?,?)''', (key, old['revision'], json.dumps(old), time.time()))
        for character in db.execute("SELECT * FROM characters WHERE visual_mode='assembly'").fetchall():
            recipe = json.loads(character['assembly_json'])
            if recipe.get('rig_id') != key or 'rig_revision' in recipe or not old['published_revision']:
                continue
            # Preserve its rendered result and skeleton metadata, but invalidate
            # stale editors so they cannot overwrite the new compatibility pin.
            stats = {r['stat_key']: r['value'] for r in db.execute('SELECT * FROM character_stats WHERE character_id=?', (character['id'],))}
            db.execute('''INSERT INTO character_assembly_history(character_id,revision,recipe_json,stats_json,changed_at)
                VALUES(?,?,?,?,?)''', (character['id'], character['revision'], character['assembly_json'], json.dumps(stats), time.time()))
            recipe['rig_revision'] = old['published_revision']
            db.execute('UPDATE characters SET assembly_json=?,revision=revision+1,updated_at=? WHERE id=?', (json.dumps(recipe), time.time(), character['id']))
            pinned.append(character['id'])
        db.execute('''UPDATE character_component_records SET revision=revision+1,content_sha256=?,
            source_path=?,prepared_path=?,prepared_sha256=?,metadata_json=? WHERE kind='rig' AND id=?''',
            (digest, relative, relative, hashlib.sha256(artifact.read_bytes()).hexdigest(),
             json.dumps(dict(bones=bones, armature=info['armature'])), key))
    components.export()
    return dict(changed=True, revision=old['revision']+1, bone_count=len(bones),
                pinned_characters=pinned, backup=str(backup), artifact=str(artifact))
