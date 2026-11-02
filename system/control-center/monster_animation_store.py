from __future__ import annotations

from pathlib import Path
from animation_scan_conflicts import partition_scan_candidates
import hashlib
import json
import re
import shutil
import time

from sqlite_connection import connect as connect_sqlite
from npc_animation_taxonomy import (
    WEAPON_SETS, EQUIPMENT_SETS, default_compatibility,
    filename as npc_filename, parse as npc_parse,
)


from monster_animation_core.schema import MonsterAnimationSchemaMixin
from monster_animation_core.bindings import MonsterAnimationBindingsMixin
from monster_animation_core.publication import MonsterAnimationPublicationMixin

SCHEMA_VERSION = 1
PROJECT = "game1"
MAX_SCAN_FILES = 5000
ANIMATION_EXTENSIONS = {".rbxm", ".rbxmx"}
SLOT_CATALOG = [
    {"group": "stance", "slot": "idle", "state": "idle", "role": "base", "label": "idle · base", "looped": True, "priority": "Idle", "variants": False},
    {"group": "stance", "slot": "idle_special", "state": "idle", "role": "special", "label": "idle · special", "looped": False, "priority": "Idle", "variants": True},
    {"group": "movement", "slot": "walk", "state": "walk", "role": "base", "label": "walk", "looped": True, "priority": "Movement", "variants": False},
    {"group": "movement", "slot": "run", "state": "run", "role": "base", "label": "run", "looped": True, "priority": "Movement", "variants": False},
    {"group": "combat", "slot": "combat_idle", "state": "combat_idle", "role": "base", "label": "combat idle", "looped": True, "priority": "Idle", "variants": False},
    {"group": "combat", "slot": "attack", "state": "attack", "role": "variant", "label": "attack", "looped": False, "priority": "Action", "variants": True},
    {"group": "life", "slot": "death", "state": "death", "role": "base", "label": "death", "looped": False, "priority": "Action", "variants": False},
]
SLOT_BY_NAME = {row["slot"]: row for row in SLOT_CATALOG}


def _safe_token(value: str) -> str:
    value = re.sub(r"[^a-z0-9_]+", "_", str(value or "").lower()).strip("_")
    return re.sub(r"_+", "_", value)


def _parse_variant(value: str) -> tuple[str, int]:
    match = re.match(r"^(.*?)(?:_([0-9]{1,3}))?$", value)
    if not match:
        return value, 0
    return match.group(1), int(match.group(2) or 0)


def classify(path: Path, slug: str, npc: bool = False) -> dict | None:
    stem = _safe_token(path.stem)
    prefix = _safe_token(slug) + "_"
    if prefix and stem.startswith(prefix):
        stem = stem[len(prefix):]
    weapon_set = ""
    if npc:
        parsed = npc_parse(path.name, slug)
        if not parsed:
            return None
        weapon_set = parsed["weaponSet"]
        stem = parsed["slot"] + ("_%02d" % parsed["variant"] if parsed["variant"] else "")
    body, variant = _parse_variant(stem)
    aliases = {
        "idle": "idle",
        "wait": "idle",
        "wait_idle": "idle",
        "idle_special": "idle_special",
        "special_idle": "idle_special",
        "sp_wait": "idle_special",
        "walk": "walk",
        "run": "run",
        "attack": "attack",
        "atk": "attack",
        "combat_idle": "combat_idle",
        "idle_combat": "combat_idle",  # accepted filename alias; internal slot remains combat_idle
        "attack_wait": "combat_idle",  # legacy filename compatibility only
        "atkwait": "combat_idle",
        "death": "death",
        "dead": "death",
        "die": "death",
    }
    slot = aliases.get(body)
    if not slot:
        special_idle = re.fullmatch(r"(?:spwait|idlespecial)0*([0-9]+)", body)
        if special_idle:
            slot = "idle_special"
            variant = max(1, int(special_idle.group(1)))
    if not slot:
        atk = re.fullmatch(r"atk0*([0-9]+)", body)
        if atk:
            slot = "attack"
            variant = max(1, int(atk.group(1)))
    if slot not in SLOT_BY_NAME:
        return None
    definition = SLOT_BY_NAME[slot]
    if definition.get("variants"):
        variant = max(1, variant)
    else:
        variant = 0
    return {"slot": slot, "variant": variant, "weaponSet": weapon_set, **definition}


def filename_rules(slug: str, npc: bool = False) -> list[dict]:
    prefix = _safe_token(slug)
    rows = []
    for definition in SLOT_CATALOG:
        variant = 1 if definition.get("variants") else 0
        suffix = f"_{variant:02d}" if variant else ""
        rows.append({
            **definition,
            "state": definition.get("state") or definition["slot"],
            "variantPattern": "01..n" if definition.get("variants") else "",
            "canonicalFilename": npc_filename(prefix, "base", definition["slot"], variant) if npc else f"{prefix}_{definition['slot']}{suffix}.rbxm",
        })
    return rows


class MonsterAnimationStore(MonsterAnimationSchemaMixin, MonsterAnimationBindingsMixin, MonsterAnimationPublicationMixin):
    def __init__(self, root: Path, kind: str = "monster"):
        if kind not in {"monster", "npc"}:
            raise ValueError("unsupported actor kind")
        self.kind = kind
        self.root = root.resolve()
        self.runtime = self.root / ".control-center"
        self.db = self.runtime / ("game1_npcs.db" if self.kind == "npc" else "game1.db")
        self._init()
        self._sync_profiles()
        self.export()

    def connect(self):
        return connect_sqlite(self.db)


    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _sync_profiles(self):
        now = time.time()
        with self.connect() as connection:
            for monster in connection.execute("SELECT slug,skeleton_signature FROM monsters ORDER BY slug"):
                slug = str(monster["slug"])
                skeleton = str(monster["skeleton_signature"] or "")
                existing = connection.execute("SELECT * FROM monster_animation_profiles WHERE monster_slug=?", (slug,)).fetchone()
                if existing is None:
                    connection.execute(
                        "INSERT INTO monster_animation_profiles(monster_slug,skeleton_signature,scan_root,created_at,updated_at) VALUES(?,?,?,?,?)",
                        (slug, skeleton, "", now, now),
                    )
                elif str(existing["skeleton_signature"] or "") != skeleton:
                    connection.execute(
                        "UPDATE monster_animation_profiles SET skeleton_signature=?,updated_at=? WHERE monster_slug=?",
                        (skeleton, now, slug),
                    )

    def _monster(self, slug: str) -> dict:
        slug = str(slug or "").strip().lower()
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM monsters WHERE slug=?", (slug,)).fetchone()
        if not row:
            raise ValueError(f"unknown monster: {slug}")
        return dict(row)

    def _profile(self, slug: str) -> dict:
        self._monster(slug)
        self._sync_profiles()
        with self.connect() as connection:
            return dict(connection.execute("SELECT * FROM monster_animation_profiles WHERE monster_slug=?", (slug,)).fetchone())

    def usage(self, slug: str) -> dict:
        with self.connect() as connection:
            clips = int(connection.execute("SELECT COUNT(*) FROM monster_animation_clips WHERE monster_slug=?", (slug,)).fetchone()[0])
            bindings = int(connection.execute("SELECT COUNT(*) FROM monster_animation_bindings WHERE monster_slug=?", (slug,)).fetchone()[0])
        return {"monsterSlug": slug, "clips": clips, "bindings": bindings}

    def delete_profile(self, slug: str):
        with self.connect() as connection:
            ids = [row[0] for row in connection.execute("SELECT id FROM monster_animation_clips WHERE monster_slug=?", (slug,))]
            for clip_id in ids:
                connection.execute("DELETE FROM monster_animation_publications WHERE clip_id=?", (clip_id,))
            connection.execute("DELETE FROM monster_animation_bindings WHERE monster_slug=?", (slug,))
            connection.execute("DELETE FROM monster_animation_clips WHERE monster_slug=?", (slug,))
            connection.execute("DELETE FROM monster_animation_profiles WHERE monster_slug=?", (slug,))
        self.export()

    def _managed(self, path: Path) -> bool:
        for root in (self.root / f"assets/source/{self.kind}s",):
            try:
                path.relative_to(root.resolve())
                return True
            except ValueError:
                pass
        return False

    def _register(self, connection, slug: str, source: Path, binding: dict, now: float) -> tuple[str, dict]:
        slot = binding["slot"]
        variant = int(binding["variant"])
        suffix = f"_{variant:02d}" if variant else ""
        weapon_set = binding.get("weaponSet", "1hs") if self.kind == "npc" else ""
        stem = f"{weapon_set + '_' if weapon_set else ''}{slot}{suffix}"
        clip_id = f"{self.kind}__{slug}__{weapon_set + '__' if weapon_set else ''}{slot}__{variant:02d}"
        if self.kind == "npc" and weapon_set == "1hs":
            legacy_id = f"npc__{slug}__{slot}__{variant:02d}"
            if connection.execute("SELECT 1 FROM monster_animation_clips WHERE id=?", (legacy_id,)).fetchone():
                clip_id = legacy_id
        binding_id = "binding__" + clip_id
        if self.kind == "npc":
            # Coordinate identity wins over filename identity after an in-place
            # rename: re-scanning must retain the published clip id/history.
            existing = connection.execute("""SELECT id,clip_id FROM monster_animation_bindings
                WHERE monster_slug=? AND weapon_set=? AND slot=? AND variant=?""",
                (slug,weapon_set,slot,variant)).fetchone()
            if existing:
                clip_id = str(existing["clip_id"])
                binding_id = str(existing["id"])
        relative = Path(f"{self.kind}s") / slug / "animations" / f"{stem}{source.suffix.lower()}"
        source_target = self.root / "assets/source" / relative
        prepared_target = source_target
        source_target.parent.mkdir(parents=True, exist_ok=True)
        source_sha = self._sha256(source)
        old = connection.execute("SELECT * FROM monster_animation_clips WHERE id=?", (clip_id,)).fetchone()
        old_dict = dict(old) if old else None
        previous_source_sha = str((old_dict or {}).get("source_sha256") or (old_dict or {}).get("sha256") or "")
        same_source = bool(old_dict and previous_source_sha == source_sha)
        if not same_source or not source_target.is_file():
            shutil.copy2(source, source_target)
        digest = self._sha256(source_target)
        source_sha = digest
        if old_dict is None:
            connection.execute(
                """INSERT INTO monster_animation_clips(id,monster_slug,name,source_path,prepared_path,sha256,source_sha256,asset_id,published_sha256,moderation_state,revision,created_at,updated_at,content_updated_at,published_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (clip_id, slug, stem, source_target.relative_to(self.root).as_posix(), prepared_target.relative_to(self.root).as_posix(), digest, source_sha, None, "", "", 1, now, now, now, None),
            )
            outcome = "created"
        else:
            content_changed = str(old_dict.get("sha256") or "") != digest
            revision = int(old_dict.get("revision") or 1) + (1 if content_changed else 0)
            if content_changed:
                connection.execute(
                    "UPDATE monster_animation_clips SET name=?,source_path=?,prepared_path=?,sha256=?,source_sha256=?,revision=?,updated_at=?,content_updated_at=? WHERE id=?",
                    (stem, source_target.relative_to(self.root).as_posix(), prepared_target.relative_to(self.root).as_posix(), digest, source_sha, revision, now, now, clip_id),
                )
            else:
                connection.execute(
                    "UPDATE monster_animation_clips SET name=?,source_path=?,prepared_path=?,sha256=?,source_sha256=?,revision=?,updated_at=? WHERE id=?",
                    (stem, source_target.relative_to(self.root).as_posix(), prepared_target.relative_to(self.root).as_posix(), digest, source_sha, revision, now, clip_id),
                )
            outcome = "changed" if content_changed else "unchanged"
        if self.kind == "npc":
            connection.execute(
                """INSERT INTO monster_animation_bindings(id,monster_slug,slot,variant,clip_id,weight,looped,priority,created_at,updated_at,weapon_set,disarm)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,0)
                   ON CONFLICT(monster_slug,weapon_set,slot,variant)
                   DO UPDATE SET clip_id=excluded.clip_id,looped=excluded.looped,priority=excluded.priority,updated_at=excluded.updated_at""",
                (binding_id, slug, slot, variant, clip_id, 100, int(binding["looped"]), binding["priority"], now, now, weapon_set),
            )
        else:
            connection.execute(
                """INSERT INTO monster_animation_bindings(id,monster_slug,slot,variant,clip_id,weight,looped,priority,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(monster_slug,slot,variant) DO UPDATE SET clip_id=excluded.clip_id,looped=excluded.looped,priority=excluded.priority,updated_at=excluded.updated_at""",
                (binding_id, slug, slot, variant, clip_id, 100, int(binding["looped"]), binding["priority"], now, now),
            )
        return outcome, {"filename": source.name, "clipId": clip_id, **binding}

    def scan_folder(self, slug: str, folder: str) -> dict:
        monster = self._monster(slug)
        self._profile(slug)
        root = Path(str(folder or "")).expanduser().resolve()
        if not root.is_dir():
            raise ValueError("choose an existing monster animation folder")
        files = sorted(
            [path.resolve() for path in root.rglob("*") if path.is_file() and path.suffix.lower() in ANIMATION_EXTENSIONS and not self._managed(path.resolve())],
            key=lambda path: path.as_posix().casefold(),
        )
        if len(files) > MAX_SCAN_FILES:
            raise ValueError(f"monster animation scan found more than {MAX_SCAN_FILES} files; choose a narrower folder")
        candidates, unassigned = [], []
        for path in files:
            binding = classify(path, slug, npc=self.kind == "npc")
            if binding is None:
                unassigned.append({
                    "path": str(path),
                    "filename": path.name,
                    "reason": ("name does not match an NPC animation type/state; "
                               "expected <npc>_<type>_<state>[_01].rbxm")
                    if self.kind == "npc" else "name does not match a monster animation state",
                })
                continue
            candidates.append((path, binding))
        # A duplicate semantic slot must never overwrite a surviving registration.
        # Report both files for explicit assignment instead of guessing which wins.
        recognized, conflicts = partition_scan_candidates(candidates, kind=self.kind)
        unassigned.extend(conflicts)
        created = changed = unchanged = 0
        imported = []
        now = time.time()
        with self.connect() as connection:
            for source, binding in recognized:
                outcome, item = self._register(connection, slug, source, binding, now)
                created += outcome == "created"
                changed += outcome == "changed"
                unchanged += outcome == "unchanged"
                imported.append(item)
            connection.execute(
                "UPDATE monster_animation_profiles SET scan_root=?,skeleton_signature=?,updated_at=? WHERE monster_slug=?",
                (str(root), str(monster.get("skeleton_signature") or ""), now, slug),
            )
        self.export()
        return {
            "monsterSlug": slug, "rootPath": str(root), "filesScanned": len(files), "recognized": len(imported),
            "created": created, "changed": changed, "unchanged": unchanged, "items": imported, "unassigned": unassigned,
        }

    def assign_file(self, slug: str, source_path: str, slot: str, variant: int = 0, weapon_set: str = "1hs") -> dict:
        self._monster(slug)
        profile = self._profile(slug)
        source = Path(str(source_path or "")).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() not in ANIMATION_EXTENSIONS:
            raise ValueError("choose an existing .rbxm/.rbxmx monster animation")
        scan_root = str(profile.get("scan_root") or "")
        if scan_root:
            try:
                source.relative_to(Path(scan_root).resolve())
            except ValueError as exc:
                raise ValueError("manual assignment must use a file from the current scan folder") from exc
        slot = _safe_token(slot)
        if slot not in SLOT_BY_NAME:
            raise ValueError(f"unknown monster animation state: {slot}")
        definition = SLOT_BY_NAME[slot]
        variant = max(1, int(variant or 0)) if definition.get("variants") else 0
        binding = {"slot": slot, "variant": variant, **definition}
        if self.kind == "npc":
            if weapon_set not in WEAPON_SETS:
                raise ValueError(f"unknown NPC animation subtype: {weapon_set}")
            binding["weaponSet"] = weapon_set
        now = time.time()
        with self.connect() as connection:
            outcome, item = self._register(connection, slug, source, binding, now)
        self.export()
        return {"monsterSlug": slug, "outcome": outcome, "item": item}

    @staticmethod
    def _status(row: dict) -> str:
        asset = str(row.get("asset_id") or "")
        if not asset:
            return "LOCAL_ONLY"
        return "PUBLISHED" if str(row.get("published_sha256") or "") == str(row.get("sha256") or "") else "CHANGED"

    def list_for_monster(self, slug: str) -> list[dict]:
        if not slug:
            return []
        with self.connect() as connection:
            extra = "b.weapon_set,b.disarm,b.compatible_sets," if self.kind == "npc" else ""
            rows = connection.execute(
                f"""SELECT b.id AS binding_id,b.monster_slug,b.slot,b.variant,b.clip_id,b.weight,b.looped,b.priority,
                          {extra}c.name,c.source_path,c.prepared_path,c.sha256,c.source_sha256,c.asset_id,c.published_sha256,c.moderation_state,c.revision,c.published_at
                   FROM monster_animation_bindings b JOIN monster_animation_clips c ON c.id=b.clip_id
                   WHERE b.monster_slug=? ORDER BY b.slot,b.variant""",
                (slug,),
            ).fetchall()
        result = []
        for row in rows:
            value = dict(row)
            definition = SLOT_BY_NAME.get(str(value.get("slot") or ""), {})
            value["state"] = str(definition.get("state") or value.get("slot") or "")
            value["role"] = str(definition.get("role") or "base")
            if self.kind == "npc":
                value["weaponSet"] = value["weapon_set"]
                value["disarm"] = bool(value["disarm"])
                value["compatibleWith"] = self._compatible_for_binding(value)
                value["canonicalFilename"] = npc_filename(slug, value["weapon_set"], value["slot"], value["variant"], Path(value["source_path"]).suffix)
            value["status"] = self._status(value)
            value["looped"] = bool(value.get("looped"))
            result.append(value)
        return result

    def snapshot(self, slug: str | None = None) -> dict:
        with self.connect() as connection:
            monsters = [dict(row) for row in connection.execute("SELECT slug,name_en,skeleton_signature FROM monsters ORDER BY name_en,slug")]
        selected = str(slug or "").strip().lower()
        if not selected and monsters:
            selected = str(monsters[0]["slug"])
        items = self.list_for_monster(selected) if selected else []
        profile = self._profile(selected) if selected else None
        monster = next((row for row in monsters if row["slug"] == selected), None)
        compatible = bool(profile and monster and str(profile.get("skeleton_signature") or "") == str(monster.get("skeleton_signature") or ""))
        return {
            "schemaVersion": SCHEMA_VERSION, "project": PROJECT, "monsterSlug": selected, "monsters": monsters,
            "profile": profile, "skeletonCompatible": compatible, "slotCatalog": SLOT_CATALOG, "weaponSets": (list(WEAPON_SETS) if self.kind == "npc" else []),
            "equipmentSets": (list(EQUIPMENT_SETS) if self.kind == "npc" else []),
            "filenameRules": filename_rules(selected, npc=self.kind == "npc"), "items": items,
            "summary": {
                "registered": len(items), "published": sum(row["status"] == "PUBLISHED" for row in items),
                "localOnly": sum(row["status"] == "LOCAL_ONLY" for row in items), "changed": sum(row["status"] == "CHANGED" for row in items),
            },
        }


    def export(self):
        with self.connect() as connection:
            profiles = [dict(row) for row in connection.execute("SELECT * FROM monster_animation_profiles ORDER BY monster_slug")]
            clips = [dict(row) for row in connection.execute("SELECT * FROM monster_animation_clips ORDER BY monster_slug,name")]
            bindings = [dict(row) for row in connection.execute("SELECT * FROM monster_animation_bindings ORDER BY monster_slug,slot,variant")]
        for row in clips:
            row["status"] = self._status(row)
        manifest_bindings = [{key: value for key, value in row.items() if key != "playback_speed_percent"} for row in bindings]
        payload = {"schemaVersion": SCHEMA_VERSION, "project": PROJECT, "slotCatalog": SLOT_CATALOG, "weaponSets": (list(WEAPON_SETS) if self.kind == "npc" else []), "profiles": profiles, "clips": clips, "bindings": manifest_bindings}
        manifest = self.root / f"assets/manifests/{self.kind}-animations.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        clips_by_id = {str(row["id"]): row for row in clips if str(row.get("asset_id") or "").isdigit()}
        profiles_map = {str(row["monster_slug"]): {"skeletonSignature": str(row.get("skeleton_signature") or ""), "slots": {}} for row in profiles}
        for binding in bindings:
            clip = clips_by_id.get(str(binding["clip_id"]))
            if not clip:
                continue
            internal_slot = str(binding["slot"])
            definition = SLOT_BY_NAME.get(internal_slot, {})
            state = str(definition.get("state") or internal_slot)
            role = str(definition.get("role") or "base")
            profile = profiles_map.setdefault(str(binding["monster_slug"]), {"skeletonSignature": "", "slots": {}})
            profile["slots"].setdefault(state, []).append({
                "clipId": str(clip["id"]), "assetId": str(clip["asset_id"]), "animationId": "rbxassetid://" + str(clip["asset_id"]),
                "sourceSlot": internal_slot, "role": role, "variant": int(binding["variant"]), "weight": int(binding["weight"]),
                "looped": bool(binding["looped"]), "priority": str(binding["priority"]),
                "weaponSet": str(binding.get("weapon_set") or "1hs") if self.kind == "npc" else "",
                "compatibleWith": self._compatible_for_binding(binding) if self.kind == "npc" else [],
                "disarm": bool(binding.get("disarm")) if self.kind == "npc" else False,
            })
        for profile in profiles_map.values():
            for rows in profile["slots"].values():
                rows.sort(key=lambda row: row["variant"])
        q = lambda value: json.dumps(str(value), ensure_ascii=False)
        lines = ["-- generated. do not edit by hand.", "return table.freeze({", f"\tschemaVersion = {SCHEMA_VERSION},", '\tproject = "game1",', "\tprofiles = table.freeze({"]
        for slug in sorted(profiles_map):
            profile = profiles_map[slug]
            lines += [f"\t\t[{q(slug)}] = table.freeze({{", f"\t\t\tskeletonSignature = {q(profile['skeletonSignature'])},", "\t\t\tslots = table.freeze({"]
            for slot in sorted(profile["slots"]):
                lines.append(f"\t\t\t\t[{q(slot)}] = table.freeze({{")
                for row in profile["slots"][slot]:
                    lines += [
                        "\t\t\t\t\ttable.freeze({",
                        f"\t\t\t\t\t\tclipId = {q(row['clipId'])},",
                        f"\t\t\t\t\t\tassetId = {q(row['assetId'])},",
                        f"\t\t\t\t\t\tanimationId = {q(row['animationId'])},",
                        f"\t\t\t\t\t\tsourceSlot = {q(row['sourceSlot'])},",
                        f"\t\t\t\t\t\trole = {q(row['role'])},",
                        f"\t\t\t\t\t\tweaponSet = {q(row['weaponSet'])},",
                        "\t\t\t\t\t\tcompatibleWith = table.freeze({" + ", ".join(q(value) for value in row["compatibleWith"]) + "}),",
                        f"\t\t\t\t\t\tvariant = {row['variant']},",
                        f"\t\t\t\t\t\tweight = {row['weight']},",
                        f"\t\t\t\t\t\tdisarm = {'true' if row['disarm'] else 'false'},",
                        f"\t\t\t\t\t\tlooped = {'true' if row['looped'] else 'false'},",
                        f"\t\t\t\t\t\tpriority = {q(row['priority'])},",
                        "\t\t\t\t\t}),",
                    ]
                lines.append("\t\t\t\t}),")
            lines += ["\t\t\t}),", "\t\t}),"]
        lines += ["\t}),", "})", ""]
        target = self.root / ("src/shared/npc/NpcAnimationRegistry.luau" if self.kind == "npc" else "src/shared/monster/MonsterAnimationRegistry.luau")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines), encoding="utf-8")
