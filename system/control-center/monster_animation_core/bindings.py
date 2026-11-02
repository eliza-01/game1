"""Authored animation binding edits; preserve clip identity and publication history."""
from __future__ import annotations


from pathlib import Path
import json
import time
from animation_retirement import retire_unbound_clip
from npc_animation_taxonomy import validate_compatibility, validate_rename, filename as npc_filename

class MonsterAnimationBindingsMixin:
    def set_weight(self, binding_id: str, weight: int) -> dict:
        weight = max(0 if self.kind == "npc" else 1, min(10000, int(weight)))
        with self.connect() as connection:
            row = connection.execute("SELECT monster_slug FROM monster_animation_bindings WHERE id=?", (binding_id,)).fetchone()
            if not row:
                raise ValueError(f"unknown monster animation binding: {binding_id}")
            connection.execute("UPDATE monster_animation_bindings SET weight=?,updated_at=? WHERE id=?", (weight, time.time(), binding_id))
            slug = str(row["monster_slug"])
        self.export()
        return self.snapshot(slug)

    def set_disarm(self, binding_id: str, enabled: bool) -> dict:
        if self.kind != "npc":
            raise ValueError("disarm is only available for NPC idle specials")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT monster_slug,slot FROM monster_animation_bindings WHERE id=?", (binding_id,)
            ).fetchone()
            if not row:
                raise ValueError("unknown NPC animation binding")
            if row["slot"] != "idle_special":
                raise ValueError("disarm is only available for idle_special")
            connection.execute("UPDATE monster_animation_bindings SET disarm=?,updated_at=? WHERE id=?",
                               (int(bool(enabled)), time.time(), binding_id))
            slug = str(row["monster_slug"])
        self.export()
        return self.snapshot(slug)

    def set_animation_options(self, binding_id: str, compatible_with: object,
                              weight: object, disarm: object) -> dict:
        """Commit authored compatibility and presentation options atomically.

        Publication identity and source animation bytes are never modified.
        """
        if self.kind != "npc":
            raise ValueError("animation options apply to NPC animation bindings")
        values = validate_compatibility(compatible_with)
        if isinstance(weight, bool):
            raise ValueError("weight must be an integer between 0 and 10000")
        try:
            parsed_weight = int(weight)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("weight must be an integer between 0 and 10000") from error
        if str(weight).strip() != str(parsed_weight) or not 0 <= parsed_weight <= 10000:
            raise ValueError("weight must be an integer between 0 and 10000")
        if not isinstance(disarm, bool):
            raise ValueError("disarm must be a boolean")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT monster_slug,slot FROM monster_animation_bindings WHERE id=?", (binding_id,)
            ).fetchone()
            if not row:
                raise ValueError("unknown NPC animation binding")
            if disarm and str(row["slot"]) != "idle_special":
                raise ValueError("disarm is only available for idle_special")
            connection.execute("""UPDATE monster_animation_bindings
                SET compatible_sets=?,weight=?,disarm=?,updated_at=? WHERE id=?""",
                (json.dumps(values, separators=(",", ":")), parsed_weight,
                 int(disarm), time.time(), binding_id),
            )
            slug = str(row["monster_slug"])
        self.export()
        return self.snapshot(slug)

    def set_compatibility(self, binding_id: str, compatible_with: object) -> dict:
        if self.kind != "npc":
            raise ValueError("compatibility applies to NPC animation bindings")
        values = validate_compatibility(compatible_with)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT monster_slug FROM monster_animation_bindings WHERE id=?", (binding_id,)
            ).fetchone()
            if not row:
                raise ValueError("unknown NPC animation binding")
            connection.execute(
                "UPDATE monster_animation_bindings SET compatible_sets=?,updated_at=? WHERE id=?",
                (json.dumps(values, separators=(",", ":")), time.time(), binding_id),
            )
            slug = str(row["monster_slug"])
        self.export()
        return self.snapshot(slug)

    def rename_npc_binding(self, binding_id: str, weapon_set: str, proposed_filename: str) -> dict:
        """Move canonical source and atomically migrate its coordinate metadata.

        Asset id/publications/revisions are untouched because animation bytes do not change.
        Filesystem moves are reversed if SQLite validation/commit fails.
        """
        if self.kind != "npc":
            raise ValueError("NPC animations only")
        moved_files = []
        try:
            with self.connect() as connection:
                row = connection.execute("""SELECT b.monster_slug,b.slot,b.variant,b.weapon_set,b.clip_id,
                     c.source_path,c.prepared_path,c.name FROM monster_animation_bindings b
                     JOIN monster_animation_clips c ON c.id=b.clip_id WHERE b.id=?""", (binding_id,)).fetchone()
                if not row:
                    raise ValueError("unknown NPC animation binding")
                slug, slot, variant = str(row["monster_slug"]), str(row["slot"]), int(row["variant"])
                ext = Path(row["source_path"]).suffix.lower()
                expected = validate_rename(proposed_filename, slug, weapon_set, slot, variant, ext)
                conflict = connection.execute("""SELECT id FROM monster_animation_bindings
                    WHERE monster_slug=? AND weapon_set=? AND slot=? AND variant=? AND id<>?""",
                    (slug, weapon_set, slot, variant, binding_id)).fetchone()
                if conflict:
                    raise ValueError(f"animation {weapon_set}_{slot}_{variant:02d} already registered")
                old_path = (self.root / str(row["source_path"])).resolve()
                # Preserve the existing extension and use one canonical path for all NPCs.
                managed_filename = f"{weapon_set}_{slot}{'_%02d' % variant if variant else ''}{ext}"
                canonical = Path("assets/source/npcs") / slug / "animations" / managed_filename
                new_path = (self.root / canonical).resolve()
                if not old_path.is_file():
                    raise ValueError(f"source animation file not found: {old_path}")
                if old_path != new_path and new_path.exists():
                    raise ValueError(f"destination already exists: {new_path}")
                # Also migrate the input scan folder when it still contains the
                # original source. Otherwise the next scan would resurrect the
                # old 1hs binding after we renamed it to base.
                scan = connection.execute(
                    "SELECT scan_root FROM monster_animation_profiles WHERE monster_slug=?", (slug,)
                ).fetchone()
                scan_root = Path(str(scan["scan_root"] or "")).resolve() if scan else None
                if scan_root and scan_root.is_dir():
                    old_filename = npc_filename(slug, str(row["weapon_set"]), slot, variant, ext)
                    matches = [p for p in scan_root.rglob(old_filename) if p.is_file() and p.resolve() != old_path]
                    matches = [p for p in matches if self._sha256(p) == self._sha256(old_path)]
                    if len(matches) > 1:
                        raise ValueError("several matching source animations in the scan folder; rename manually to " + expected)
                    if matches:
                        source = matches[0]
                        dest = source.with_name(expected)
                        if source != dest:
                            if dest.exists():
                                raise ValueError("scan source destination already exists: " + str(dest))
                            source.replace(dest)
                            moved_files.append((source, dest))
                if old_path != new_path:
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    old_path.replace(new_path)
                    moved_files.append((old_path, new_path))
                now = time.time()
                connection.execute("UPDATE monster_animation_bindings SET weapon_set=?,updated_at=? WHERE id=?",
                                   (weapon_set, now, binding_id))
                connection.execute("""UPDATE monster_animation_clips SET name=?,source_path=?,prepared_path=?,updated_at=? WHERE id=?""",
                                   (Path(expected).stem, canonical.as_posix(), canonical.as_posix(), now, str(row["clip_id"])))
        except Exception:
            for source, destination in reversed(moved_files):
                if destination.exists():
                    destination.replace(source)
            raise
        self.export()
        return self.snapshot(slug)

    def delete_binding(self, binding_id: str) -> dict:
        with self.connect() as connection:
            row = connection.execute("SELECT monster_slug,clip_id FROM monster_animation_bindings WHERE id=?", (binding_id,)).fetchone()
            if not row:
                raise ValueError(f"unknown monster animation binding: {binding_id}")
            slug, clip_id = str(row["monster_slug"]), str(row["clip_id"])
            connection.execute("DELETE FROM monster_animation_bindings WHERE id=?", (binding_id,))
            # Remove the active clip even if it was published. Retain the
            # publication audit in the archive, never in the new registration.
            retire_unbound_clip(connection, self.kind, clip_id)
        self.export()
        return self.snapshot(slug)
