"""NPC loadout persistence and publication-independent runtime registry.

Do not mutate weapon definitions or NPC model revisions when loadout changes.
"""
from __future__ import annotations
from pathlib import Path
import json
import time
from sqlite_connection import connect as connect_sqlite

class NpcEquipmentStore:
    def __init__(self, root: Path, npcs, weapons):
        self.root, self.npcs, self.weapons = root.resolve(), npcs, weapons
        self.db = self.root / '.control-center/game1_npcs.db'
        with connect_sqlite(self.db) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS npc_loadouts(
                npc_slug TEXT PRIMARY KEY, right_weapon_slug TEXT NOT NULL DEFAULT '',
                left_weapon_slug TEXT NOT NULL DEFAULT '', updated_at REAL NOT NULL DEFAULT 0)''')
        self.export()

    def snapshot(self, slug: str = '') -> dict:
        with connect_sqlite(self.db) as conn:
            entries = [dict(row) for row in conn.execute('SELECT * FROM npc_loadouts ORDER BY npc_slug')]
        loadouts = {row['npc_slug']: {'right': row['right_weapon_slug'], 'left': row['left_weapon_slug']} for row in entries}
        weapon_options = [dict(slug=row['slug'], nameEn=row['name_en'], weaponType=row['weapon_type'], status=row['status']) for row in self.weapons.list()]
        return {'schemaVersion': 1, 'npcSlug': slug, 'loadout': loadouts.get(slug, {'right':'', 'left':''}),
                'loadouts': loadouts, 'weapons': weapon_options}

    def set_loadout(self, npc_slug: str, right: str, left: str) -> dict:
        npc_slug = str(npc_slug or '').lower().strip()
        if not self.npcs.get(npc_slug):
            raise ValueError('unknown NPC: ' + npc_slug)
        selected = {}
        for hand, value in (('right',right), ('left',left)):
            slug = str(value or '').lower().strip()
            if slug:
                row = self.weapons.get(slug)
                if not row or row['status'] != 'PUBLISHED' or not row.get('model_asset_id'):
                    raise ValueError(f'{hand}-hand weapon must be published and registered: {slug}')
            selected[hand] = slug
        with connect_sqlite(self.db) as conn:
            conn.execute('''INSERT INTO npc_loadouts(npc_slug,right_weapon_slug,left_weapon_slug,updated_at)
                            VALUES(?,?,?,?) ON CONFLICT(npc_slug) DO UPDATE SET
                            right_weapon_slug=excluded.right_weapon_slug,
                            left_weapon_slug=excluded.left_weapon_slug,updated_at=excluded.updated_at''',
                         (npc_slug,selected['right'],selected['left'],time.time()))
        self.export()
        return self.snapshot(npc_slug)

    def users_of_weapon(self, weapon_slug: str) -> list[str]:
        with connect_sqlite(self.db) as conn:
            return [str(row[0]) for row in conn.execute(
                "SELECT npc_slug FROM npc_loadouts WHERE right_weapon_slug=? OR left_weapon_slug=? ORDER BY npc_slug",
                (weapon_slug, weapon_slug)
            )]

    def delete(self, npc_slug: str):
        with connect_sqlite(self.db) as conn:
            conn.execute('DELETE FROM npc_loadouts WHERE npc_slug=?', (npc_slug,))
        self.export()

    def export(self):
        snapshot = self.snapshot()
        manifest = self.root / 'assets/manifests/npc-equipment.json'
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        target = self.root / 'src/shared/npc/NpcEquipmentRegistry.luau'
        target.parent.mkdir(parents=True, exist_ok=True)
        q=lambda text:json.dumps(str(text),ensure_ascii=False)
        lines=['-- generated. do not edit by hand.', 'return table.freeze({', '\tschemaVersion = 1,','\tloadouts = table.freeze({']
        for slug, row in sorted(snapshot['loadouts'].items()):
            lines += [f'\t\t[{q(slug)}] = table.freeze({{',f'\t\t\tright = {q(row["right"])},',f'\t\t\tleft = {q(row["left"])},','\t\t}),']
        lines += ['\t}),','})','']
        target.write_text('\n'.join(lines), encoding='utf-8')
