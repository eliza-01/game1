"""Armor authoring v2: logical equipment, reusable geometry and appearance assets.

No FBX ownership, uploads, player inventory or Roblox Studio mutations here.
A set owns optional logical slots; each slot resolves a gender-specific variant.
"""
from __future__ import annotations

import json
import time
from character_core.part_names import TOKEN
from sqlite_connection import connect

ARMOR_SLOTS = ('upper', 'lower', 'gloves', 'boots')
ARMOR_TYPES = ('light', 'heavy', 'magic')
GENDERS = ('male', 'female')
VARIANTS = ('unisex', *GENDERS)


def identifier(value, label):
    if not isinstance(value, str) or len(value) > 64 or not TOKEN.fullmatch(value):
        raise ValueError(f'{label}: use a lowercase snake_case ID (max 64 characters)')
    return value


def gender_pair(value):
    if not isinstance(value, list) or not value or len(set(value)) != len(value) or any(
        not isinstance(g, str) or g not in GENDERS for g in value
    ):
        raise ValueError('allowedGenders must be ["male"], ["female"] or ["male","female"]')
    return sorted(value)


class ArmorCatalog:
    """SQLite writer / resolver. CharacterComponents and AtlasRegistry stay asset owners."""

    def __init__(self, components):
        self.components = components
        self.db = components.db
        with connect(self.db) as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS armor_sets (
                    id TEXT PRIMARY KEY, display_name TEXT NOT NULL, armor_type TEXT NOT NULL,
                    stats_json TEXT NOT NULL DEFAULT '{}', revision INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS armor_pieces (
                    id TEXT PRIMARY KEY, set_id TEXT NOT NULL REFERENCES armor_sets(id) ON DELETE CASCADE,
                    slot TEXT NOT NULL, display_name TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL, UNIQUE(set_id,slot));
                CREATE TABLE IF NOT EXISTS character_appearances (
                    id TEXT PRIMARY KEY, atlas_variant_id INTEGER NOT NULL UNIQUE,
                    material_json TEXT NOT NULL DEFAULT '{}', created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS armor_piece_variants (
                    piece_id TEXT NOT NULL REFERENCES armor_pieces(id) ON DELETE CASCADE,
                    gender TEXT NOT NULL, mesh_part_id TEXT, appearance_id TEXT,
                    revision INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY(piece_id,gender));
            ''')
            db.execute('PRAGMA foreign_keys=ON')

    def _atlas(self, variant_id):
        if variant_id is None or variant_id == '':
            return None
        if type(variant_id) is not int or variant_id < 1:
            raise ValueError('atlasVariantId must be a positive integer or null')
        if variant_id not in self.components.atlases.character_variant_ids():
            raise ValueError('atlas is not registered in the Character atlas catalog')
        atlas = self.components.atlases.get_variant(variant_id)
        if not atlas or atlas['retired']:
            raise ValueError('atlas variant is missing or retired')
        return atlas

    def appearance(self, appearance_id):
        if not appearance_id:
            return None
        with connect(self.db) as db:
            row = db.execute('SELECT * FROM character_appearances WHERE id=?', (appearance_id,)).fetchone()
        if not row:
            raise ValueError('unknown Character appearance: ' + str(appearance_id))
        return dict(row)

    def _ensure_appearance(self, db, atlas):
        if atlas is None:
            return None
        key = 'atlas_' + str(atlas['id'])
        db.execute('''INSERT OR IGNORE INTO character_appearances(id,atlas_variant_id,created_at)
            VALUES(?,?,?)''', (key, atlas['id'], time.time()))
        return key

    def ensure_appearance(self, atlas_variant_id):
        atlas = self._atlas(atlas_variant_id)
        if atlas is None:
            return None
        with connect(self.db) as db:
            return self._ensure_appearance(db, atlas)

    def snapshot(self):
        with connect(self.db) as db:
            sets = [dict(row) for row in db.execute('SELECT * FROM armor_sets ORDER BY id')]
            pieces = [dict(row) for row in db.execute('SELECT * FROM armor_pieces ORDER BY slot,id')]
            variants = [dict(row) for row in db.execute('SELECT * FROM armor_piece_variants ORDER BY gender')]
            appearances = [dict(row) for row in db.execute('SELECT * FROM character_appearances ORDER BY id')]
        for item in sets:
            item['stats'] = json.loads(item.pop('stats_json'))
            item['pieces'] = []
        group = {s['id']: s for s in sets}
        by_piece = {p['id']: p for p in pieces}
        for piece in pieces:
            piece['variants'] = {}
            if piece['set_id'] in group:
                group[piece['set_id']]['pieces'].append(piece)
        for variant in variants:
            if variant['piece_id'] in by_piece:
                by_piece[variant['piece_id']]['variants'][variant['gender']] = dict(
                    meshPartId=variant['mesh_part_id'], appearanceId=variant['appearance_id'],
                    revision=variant['revision'])
        meshes = [p for p in self.components.snapshot()['items'] if
                  p['kind'] == 'part' and p['slot'] in ARMOR_SLOTS and p.get('mesh_family_id')]
        atlases = [v for f in self.components.atlases.catalog(domain='character') for v in f['variants']]
        return dict(schema_version=2, sets=sets, meshes=meshes, appearances=appearances, atlases=atlases,
                    slots=list(ARMOR_SLOTS), types=list(ARMOR_TYPES), genders=list(VARIANTS))

    def save_set(self, payload):
        key = identifier(payload.get('id'), 'armor set')
        name = str(payload.get('displayName') or '').strip()
        armor_type = payload.get('armorType')
        if not 1 <= len(name) <= 120:
            raise ValueError('set name must contain 1–120 characters')
        if armor_type not in ARMOR_TYPES:
            raise ValueError('armorType must be light, heavy or magic')
        revision = payload.get('expectedRevision', 0)
        if type(revision) is not int or revision < 0:
            raise ValueError('expectedRevision must be a nonnegative integer')
        now = time.time()
        with connect(self.db) as db:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT revision FROM armor_sets WHERE id=?', (key,)).fetchone()
            if (row['revision'] if row else 0) != revision:
                raise ValueError('set changed; refresh before saving')
            if row:
                db.execute('''UPDATE armor_sets SET display_name=?,armor_type=?,revision=revision+1,updated_at=?
                    WHERE id=?''', (name, armor_type, now, key))
            else:
                db.execute('''INSERT INTO armor_sets(id,display_name,armor_type,created_at,updated_at)
                    VALUES(?,?,?,?,?)''', (key, name, armor_type, now, now))
        return self.snapshot()

    def add_piece(self, payload):
        set_id = identifier(payload.get('setId'), 'setId')
        slot = payload.get('slot')
        if slot not in ARMOR_SLOTS:
            raise ValueError('unknown armor slot')
        key = set_id + '_' + slot  # logical item identity, NOT geometry identity
        if len(key) > 96:
            raise ValueError('set id is too long for a slot identifier')
        now = time.time()
        with connect(self.db) as db:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM armor_sets WHERE id=?', (set_id,)).fetchone():
                raise ValueError('register the armor set first')
            if db.execute('SELECT 1 FROM armor_pieces WHERE set_id=? AND slot=?', (set_id, slot)).fetchone():
                raise ValueError('this set already has a piece in that slot')
            db.execute('INSERT INTO armor_pieces(id,set_id,slot,display_name,created_at) VALUES(?,?,?,?,?)',
                       (key, set_id, slot, str(payload.get('displayName') or slot)[:120], now))
            db.execute('UPDATE armor_sets SET revision=revision+1,updated_at=? WHERE id=?', (now, set_id))
        return self.snapshot()

    def remove_piece(self, payload):
        piece_id = identifier(payload.get('pieceId'), 'pieceId')
        with connect(self.db) as db:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT set_id FROM armor_pieces WHERE id=?', (piece_id,)).fetchone()
            if not row:
                raise ValueError('unknown armor piece')
            db.execute('DELETE FROM armor_piece_variants WHERE piece_id=?', (piece_id,))
            db.execute('DELETE FROM armor_pieces WHERE id=?', (piece_id,))
            db.execute('UPDATE armor_sets SET revision=revision+1,updated_at=? WHERE id=?',
                       (time.time(), row['set_id']))
        return self.snapshot()

    def set_variant(self, payload):
        piece_id = identifier(payload.get('pieceId'), 'pieceId')
        gender = payload.get('gender')
        if gender not in VARIANTS:
            raise ValueError('gender must be male, female or unisex')
        mesh_id = payload.get('meshPartId') or None
        if mesh_id is not None:
            identifier(mesh_id, 'meshPartId')
        atlas = self._atlas(payload.get('atlasVariantId'))
        # Two completely optional dependencies for a draft. Do not infer from the set name.
        mesh = self.components.get('part', mesh_id) if mesh_id else None
        if mesh_id:
            if (not mesh or mesh['slot'] not in ARMOR_SLOTS or mesh['role'] != 'part'
                    or not mesh.get('mesh_family_id')):
                raise ValueError('choose a registered m001 armor MeshPart')
        with connect(self.db) as db:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE')
            piece = db.execute('SELECT * FROM armor_pieces WHERE id=?', (piece_id,)).fetchone()
            if not piece:
                raise ValueError('register the armor set part first')
            if mesh and mesh['slot'] != piece['slot']:
                raise ValueError('mesh slot does not match this armor piece')
            if mesh:
                allowed = json.loads(mesh['allowed_genders_json'])
                wanted = GENDERS if gender == 'unisex' else (gender,)
                if not all(g in allowed for g in wanted):
                    raise ValueError('MeshPart allowedGenders does not include ' + gender)
            old = db.execute('SELECT revision FROM armor_piece_variants WHERE piece_id=? AND gender=?',
                             (piece_id, gender)).fetchone()
            expected = payload.get('expectedRevision', 0)
            if type(expected) is not int or expected != (old['revision'] if old else 0):
                raise ValueError('variant changed; refresh before saving')
            appearance_id = self._ensure_appearance(db, atlas)
            db.execute('''INSERT INTO armor_piece_variants(piece_id,gender,mesh_part_id,appearance_id)
                VALUES(?,?,?,?) ON CONFLICT(piece_id,gender) DO UPDATE SET
                mesh_part_id=excluded.mesh_part_id,appearance_id=excluded.appearance_id,
                revision=armor_piece_variants.revision+1''',
                       (piece_id, gender, mesh_id, appearance_id))
            db.execute('UPDATE armor_pieces SET revision=revision+1 WHERE id=?', (piece_id,))
            db.execute('UPDATE armor_sets SET revision=revision+1,updated_at=? WHERE id=?',
                       (time.time(), piece['set_id']))
        return self.snapshot()

    def resolve(self, set_id, gender, rig_id):
        """Pure-ish read resolver. An absent slot is valid; an authored incomplete slot is not."""
        if gender not in GENDERS:
            return {}, ['choose an explicit character gender']
        with connect(self.db) as db:
            set_row = db.execute('SELECT id FROM armor_sets WHERE id=?', (set_id,)).fetchone() if set_id else None
            pieces = db.execute('SELECT * FROM armor_pieces WHERE set_id=?', (set_id,)).fetchall() if set_row else []
            variants = {r['piece_id']: dict(r) for r in db.execute('''SELECT v.* FROM armor_piece_variants v
                JOIN armor_pieces p ON p.id=v.piece_id WHERE p.set_id=? AND v.gender=?''',
                (set_id, gender))} if set_row else {}
            fallbacks = {r['piece_id']: dict(r) for r in db.execute('''SELECT v.* FROM armor_piece_variants v
                JOIN armor_pieces p ON p.id=v.piece_id WHERE p.set_id=? AND v.gender='unisex' ''',
                (set_id,))} if set_row else {}
        if not set_row:
            return {}, ['armor set not registered: ' + str(set_id)]
        missing = []
        resolved = {}
        for piece in pieces:
            slot = piece['slot']
            choice = variants.get(piece['id']) or fallbacks.get(piece['id'])
            if not choice or not choice['mesh_part_id'] or not choice['appearance_id']:
                missing.append(slot + ': assign mesh and texture for ' + gender)
                continue
            mesh = self.components.get('part', choice['mesh_part_id'])
            if (not mesh or mesh['slot'] != slot or not self.components.part_compatible_with_rig(mesh, rig_id)
                    or gender not in json.loads(mesh['allowed_genders_json'])):
                missing.append(slot + ': mesh incompatible with rig/gender')
                continue
            appearance = self.appearance(choice['appearance_id'])
            atlas = self._atlas(appearance['atlas_variant_id'])
            if not atlas or not atlas['current'] or atlas['replacementPending']:
                missing.append(slot + ': texture not published/current')
                continue
            if not str(mesh['model_asset_id']).isdigit() or mesh['published_revision'] != mesh['revision']:
                missing.append(slot + ': mesh not published/current')
                continue
            resolved[slot] = (mesh, appearance, atlas)
        return resolved, missing
