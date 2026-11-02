"""Canonical character FBX registration, model reassignment and immutable publication."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import shutil
import tempfile
import time
from character_analysis import analyze_character_fbx, prepare_character_fbx, prepare_character_publication_fbx
from opencloud_assets import create_model_asset, wait_for_operation
from character_core.archetype_contract import ACTIVE_KEY, CHARACTER_PUBLICATION_PIPELINE

def _assert_publication_skeleton_matches(row: dict, analysis: dict):
    expected_count = int(row.get("bone_count") or 0)
    actual_count = int(analysis.get("boneCount") or 0)
    if expected_count <= 0 or actual_count != expected_count:
        raise ValueError(
            f"publication FBX skeleton mismatch: expected {expected_count} bones, got {actual_count}"
        )

    expected_structure = str(row.get("skeleton_structure_signature") or "")
    actual_structure = str(analysis.get("skeletonStructureSignature") or "")
    if expected_structure and actual_structure != expected_structure:
        raise ValueError("publication FBX changed bone names or parent hierarchy; upload cancelled")

    try:
        expected_analysis = json.loads(str(row.get("skeleton_json") or "{}"))
    except Exception as exc:
        raise ValueError("registered character skeleton metadata is invalid") from exc

    expected_bones = {str(item.get("name") or ""): item for item in expected_analysis.get("bones") or []}
    actual_bones = {str(item.get("name") or ""): item for item in analysis.get("bones") or []}
    if expected_bones.keys() != actual_bones.keys():
        missing = sorted(expected_bones.keys() - actual_bones.keys(), key=str.casefold)
        extra = sorted(actual_bones.keys() - expected_bones.keys(), key=str.casefold)
        raise ValueError(
            "publication FBX changed the bone set; upload cancelled"
            + (f"; missing: {', '.join(missing[:12])}" if missing else "")
            + (f"; extra: {', '.join(extra[:12])}" if extra else "")
        )

    tolerance = 1e-4
    for name, expected in expected_bones.items():
        actual = actual_bones[name]
        if str(expected.get("parent") or "") != str(actual.get("parent") or ""):
            raise ValueError(f"publication FBX changed parent of bone {name!r}; upload cancelled")
        left = [float(value) for value in expected.get("matrixLocal") or []]
        right = [float(value) for value in actual.get("matrixLocal") or []]
        if len(left) != len(right) or any(abs(a - b) > tolerance for a, b in zip(left, right)):
            raise ValueError(f"publication FBX moved rest bone {name!r}; upload cancelled")


class CharacterModelWorkflowMixin:
    def register(self, data):
        candidate = self.get(str(data.get('existingId') or data.get('id') or ''))
        if candidate and candidate.get('visual_mode') == 'assembly':
            raise ValueError('use the assembly editor for this character')
        expected_existing_id = str(data.get("existingId") or "").strip().lower()
        seed_old = self.get(expected_existing_id) if expected_existing_id else None
        character_id, display_name, race, gender = self._identity(data, seed_old)

        if expected_existing_id:
            if not seed_old:
                raise ValueError(f"unknown archetype revision target: {expected_existing_id}")
            if character_id != expected_existing_id:
                raise ValueError("save archetype identity before registering a model revision")
            old = seed_old
        else:
            old = self.get(character_id)
            if old:
                raise ValueError(
                    f"archetype {character_id} already exists; select that row to register a new model revision"
                )

        self._identity_conflict(character_id, race, gender)

        raw_source = str(data.get("sourcePath", "")).strip()
        if not raw_source and not old:
            raise ValueError("choose an FBX with a skinned armature before registering the character")

        source = str(old.get("source_path") or "") if old else ""
        prepared = str(old.get("prepared_path") or "") if old else ""
        sha = str(old.get("sha256") or "") if old else ""
        analysis = json.loads(str(old.get("skeleton_json") or "{}")) if old else {}

        created_files: list[Path] = []
        if raw_source:
            source_file = Path(raw_source).expanduser()
            if not source_file.is_absolute():
                source_file = (self.root / source_file).resolve()
            if not source_file.is_file() or source_file.suffix.lower() != ".fbx":
                raise ValueError(f"select a valid character FBX: {source_file}")

            relative = Path("characters") / race / gender / character_id / "model" / source_file.name
            canonical_target = self.root / "assets" / "source" / relative

            with tempfile.TemporaryDirectory(prefix="game1-character-prepare-") as tmp:
                canonical_candidate = Path(tmp) / source_file.name
                prepare_character_fbx(self.root, source_file, canonical_candidate)
                analysis = analyze_character_fbx(self.root, canonical_candidate)
                canonical_digest = hashlib.sha256(canonical_candidate.read_bytes()).hexdigest()

                revision_stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
                canonical_target.parent.mkdir(parents=True, exist_ok=True)
                if canonical_target.exists():
                    existing = hashlib.sha256(canonical_target.read_bytes()).hexdigest()
                    if existing != canonical_digest:
                        archive = (
                            self.root
                            / "assets"
                            / "reimported"
                            / "characters"
                            / race
                            / gender
                            / character_id
                            / revision_stamp
                            / "canonical"
                            / canonical_target.name
                        )
                        archive.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(canonical_target, archive)
                        canonical_target.unlink()
                if not canonical_target.exists():
                    shutil.copy2(canonical_candidate, canonical_target)
                    created_files.append(canonical_target)

            canonical = canonical_target.relative_to(self.root).as_posix()
            source = canonical
            prepared = canonical
            sha = canonical_digest

        replacement_pending = int(old.get("model_replacement_pending") or 0) if old else 0
        force_replacement = bool(data.get("forceReplacement"))
        if raw_source and old and str(old.get("model_asset_id") or "").strip():
            if force_replacement:
                # Explicit Replace is an intent, not a content-diff probe. Even if
                # the replacement FBX hashes identically to the currently published
                # source, the user asked for a brand-new immutable Roblox asset id.
                replacement_pending = 1
            else:
                published_basis = str(old.get("published_sha256") or old.get("sha256") or "")
                replacement_pending = int(bool(sha and published_basis and sha != published_basis))

        now = time.time()
        revision = (int(old["revision"]) + 1) if old else 1
        created_at = old["created_at"] if old else now
        values = {
            "id": character_id,
            "display_name": display_name,
            "race": race,
            "gender": gender,
            "source_path": source,
            "prepared_path": prepared,
            "sha256": sha,
            "model_asset_id": old.get("model_asset_id") if old else None,
            "model_replacement_pending": replacement_pending,
            "published_sha256": str(old.get("published_sha256") or "") if old else "",
            "publication_pipeline": str(old.get("publication_pipeline") or "") if old else "",
            "moderation_state": str(old.get("moderation_state") or "") if old else "",
            "published_at": old.get("published_at") if old else None,
            "armature_name": str(analysis.get("armature") or ""),
            "bone_count": int(analysis.get("boneCount") or 0),
            "mesh_count": int(analysis.get("meshCount") or 0),
            "skeleton_signature": str(analysis.get("skeletonSignature") or ""),
            "skeleton_structure_signature": str(analysis.get("skeletonStructureSignature") or ""),
            "skeleton_json": json.dumps(analysis, ensure_ascii=False, separators=(",", ":")),
            "revision": revision,
            "created_at": created_at,
            "updated_at": now,
        }
        values["status"] = self._status(values)
        stats = self._validate_stats(data, old)

        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO characters(
                  id,display_name,race,gender,source_path,prepared_path,sha256,model_asset_id,model_replacement_pending,
                  status,revision,created_at,updated_at,armature_name,bone_count,mesh_count,
                  skeleton_signature,skeleton_structure_signature,skeleton_json,published_sha256,publication_pipeline,
                  moderation_state,published_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    values["id"], values["display_name"], values["race"], values["gender"],
                    values["source_path"], values["prepared_path"], values["sha256"], values["model_asset_id"], values["model_replacement_pending"],
                    values["status"], values["revision"], values["created_at"], values["updated_at"],
                    values["armature_name"], values["bone_count"], values["mesh_count"],
                    values["skeleton_signature"], values["skeleton_structure_signature"], values["skeleton_json"],
                    values["published_sha256"], values["publication_pipeline"], values["moderation_state"], values["published_at"],
                ),
            )
            for key, value in stats.items():
                connection.execute(
                    "INSERT OR REPLACE INTO character_stats(character_id,stat_key,value) VALUES(?,?,?)",
                    (character_id, key, value),
                )
        self.export()
        return self.get(character_id)

    def assign_model(self, target_character_id: str, source_character_id: str):
        target_id = str(target_character_id or "").strip().lower()
        source_id = str(source_character_id or "").strip().lower()
        target = self.get(target_id)
        source = self.get(source_id)
        if not target:
            raise ValueError(f"unknown target archetype: {target_id}")
        if not source:
            raise ValueError(f"unknown source archetype: {source_id}")
        if target.get('visual_mode') == 'assembly' or source.get('visual_mode') == 'assembly':
            raise ValueError('assembly characters reference parts, not a whole-model reassignment')
        if target_id == source_id:
            return target

        canonical_path = self.root / str(source.get("prepared_path") or source.get("source_path") or "")
        if not canonical_path.is_file():
            raise ValueError("selected registered model is missing its canonical source file")

        race = str(target.get("race") or "")
        gender = str(target.get("gender") or "")
        target_source = self.root / "assets/source/characters" / race / gender / target_id / "model" / canonical_path.name
        target_prepared = target_source
        revision_stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())

        def archive_old(stored_path: str, label: str):
            value = str(stored_path or "").strip()
            if not value:
                return
            old_path = (self.root / value).resolve()
            if not old_path.is_file():
                return
            if old_path == canonical_path.resolve():
                return
            archive = (
                self.root
                / "assets/reimported/characters"
                / race
                / gender
                / target_id
                / revision_stamp
                / "model-reassignment"
                / label
                / old_path.name
            )
            archive.parent.mkdir(parents=True, exist_ok=True)
            if not archive.exists():
                shutil.copy2(old_path, archive)

        archived_paths = set()
        for stored_path in (str(target.get("source_path") or ""), str(target.get("prepared_path") or "")):
            normalized = stored_path.replace("\\", "/")
            if normalized and normalized not in archived_paths:
                archive_old(stored_path, "canonical")
                archived_paths.add(normalized)

        target_source.parent.mkdir(parents=True, exist_ok=True)
        if canonical_path.resolve() != target_source.resolve():
            if target_source.exists():
                incoming_sha = hashlib.sha256(canonical_path.read_bytes()).hexdigest()
                destination_sha = hashlib.sha256(target_source.read_bytes()).hexdigest()
                if incoming_sha != destination_sha:
                    archive = (
                        self.root
                        / "assets/reimported/characters"
                        / race
                        / gender
                        / target_id
                        / revision_stamp
                        / "model-reassignment"
                        / "replaced"
                        / target_source.name
                    )
                    archive.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target_source, archive)
            shutil.copy2(canonical_path, target_source)

        now = time.time()
        target_asset_id = str(target.get("model_asset_id") or "").strip()
        source_sha = str(source.get("sha256") or "")
        target_published_sha = str(target.get("published_sha256") or target.get("sha256") or "")
        replacement_pending = int(bool(target_asset_id and source_sha and target_published_sha and source_sha != target_published_sha))
        values = {
            "source_path": target_source.relative_to(self.root).as_posix(),
            "prepared_path": target_prepared.relative_to(self.root).as_posix(),
            "sha256": source_sha,
            # Reassigning source files must never steal/reuse another archetype's
            # Roblox asset id. Keep the target's currently live asset until the
            # replacement has been published successfully as a brand-new asset.
            "model_asset_id": target.get("model_asset_id"),
            "model_replacement_pending": replacement_pending,
            "published_sha256": str(target.get("published_sha256") or ""),
            "moderation_state": str(target.get("moderation_state") or ""),
            "published_at": target.get("published_at"),
            "armature_name": str(source.get("armature_name") or ""),
            "bone_count": int(source.get("bone_count") or 0),
            "mesh_count": int(source.get("mesh_count") or 0),
            "skeleton_signature": str(source.get("skeleton_signature") or ""),
            "skeleton_structure_signature": str(source.get("skeleton_structure_signature") or ""),
            "skeleton_json": str(source.get("skeleton_json") or "{}"),
        }
        status_probe = {**target, **values}
        status = self._status(status_probe)
        with self.connect() as connection:
            connection.execute(
                """UPDATE characters SET
                   source_path=?,prepared_path=?,sha256=?,model_asset_id=?,model_replacement_pending=?,published_sha256=?,
                   moderation_state=?,published_at=?,armature_name=?,bone_count=?,mesh_count=?,
                   skeleton_signature=?,skeleton_structure_signature=?,skeleton_json=?,status=?,
                   revision=revision+1,updated_at=? WHERE id=?""",
                (
                    values["source_path"], values["prepared_path"], values["sha256"], values["model_asset_id"], values["model_replacement_pending"],
                    values["published_sha256"], values["moderation_state"], values["published_at"],
                    values["armature_name"], values["bone_count"], values["mesh_count"],
                    values["skeleton_signature"], values["skeleton_structure_signature"], values["skeleton_json"],
                    status, now, target_id,
                ),
            )
            connection.execute(
                "INSERT INTO character_model_assignments(target_character_id,source_character_id,asset_id,assigned_at) VALUES(?,?,?,?)",
                (target_id, source_id, "", now),
            )

        cleaned_paths = set()
        for stored_path in (str(target.get("source_path") or ""), str(target.get("prepared_path") or "")):
            normalized = stored_path.replace("\\", "/")
            if not normalized or normalized in cleaned_paths:
                continue
            cleaned_paths.add(normalized)
            old_path = (self.root / stored_path).resolve()
            if old_path == target_source.resolve() or old_path == canonical_path.resolve():
                continue
            try:
                old_path.unlink(missing_ok=True)
            except Exception:
                pass

        self.export()
        return self.get(target_id)

    def publish(self, character_id: str, publication: dict):
        character_id = str(character_id or "").strip().lower()
        row = self.get(character_id)
        if not row:
            raise ValueError(f"unknown character archetype: {character_id}")
        if row.get('visual_mode') == 'assembly':
            raise ValueError('publish the referenced rig and parts separately')
        prepared = self.root / str(row.get("prepared_path") or row.get("source_path") or "")
        if not prepared.is_file():
            raise ValueError("canonical character FBX is missing; re-register the model")

        api_key = str(publication.get("apiKey") or "").strip()
        creator_type = str(publication.get("creatorType") or "").strip().lower()
        creator_id = str(publication.get("creatorId") or "").strip()
        description = str(publication.get("description") or "game1 character model").strip()
        current_asset_id = str(row.get("model_asset_id") or "").strip()
        current_sha = str(row.get("sha256") or "")
        published_sha = str(row.get("published_sha256") or "")
        published_pipeline = str(row.get("publication_pipeline") or "")

        # Character models are immutable from the archetype manager's point of
        # view. Never PATCH an existing Roblox model asset. A normal publish of
        # unchanged content is a no-op, but an explicit Replace request is never
        # deduplicated: Replace always creates a brand-new asset id.
        replacement_pending = bool(int(row.get("model_replacement_pending") or 0))
        if (
            current_asset_id
            and current_sha
            and published_sha
            and current_sha == published_sha
            and published_pipeline == CHARACTER_PUBLICATION_PIPELINE
            and not replacement_pending
        ):
            return row

        # Open Cloud's automated FBX Model importer does not expose Studio's
        # "Keep Zero Influence Bones" option. Build a temporary publication copy
        # that strengthens only weak influences, then verify that re-exporting did
        # not move or re-parent a single registered bone before upload.
        with tempfile.TemporaryDirectory(prefix="game1-character-publish-") as tmp:
            publication_fbx = Path(tmp) / (prepared.stem + ".publication.fbx")
            publication_result = prepare_character_publication_fbx(
                self.root, prepared, publication_fbx
            )
            _assert_publication_skeleton_matches(row, publication_result["analysis"])
            operation = create_model_asset(
                publication_fbx,
                display_name=row["display_name"],
                description=description,
                creator_type=creator_type,
                creator_id=creator_id,
                api_key=api_key,
            )
            result = wait_for_operation(operation, api_key=api_key)
        now = time.time()
        with self.connect() as connection:
            connection.execute(
                """UPDATE characters SET model_asset_id=?,model_replacement_pending=0,published_sha256=?,publication_pipeline=?,moderation_state=?,published_at=?,updated_at=?
                   WHERE id=?""",
                (result.asset_id, row["sha256"], CHARACTER_PUBLICATION_PIPELINE, result.moderation_state or "", now, now, character_id),
            )
            connection.execute(
                """INSERT INTO character_publications(
                     character_id,character_revision,asset_id,operation_path,sha256,moderation_state,published_at
                   ) VALUES(?,?,?,?,?,?,?)""",
                (
                    character_id,
                    int(row["revision"]),
                    result.asset_id,
                    result.operation_path,
                    row["sha256"],
                    result.moderation_state or "",
                    now,
                ),
            )
            updated = connection.execute("SELECT * FROM characters WHERE id=?", (character_id,)).fetchone()
            updated_dict = dict(updated)
            connection.execute("UPDATE characters SET status=? WHERE id=?", (self._status(updated_dict), character_id))
        self.export()
        return self.get(character_id)

    def publications(self, character_id: str):
        with self.connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM character_publications WHERE character_id=? ORDER BY id DESC",
                    (character_id,),
                )
            ]

    def delete(self, character_id):
        character_id = str(character_id or "").strip().lower()
        with self.connect() as connection:
            connection.execute("DELETE FROM characters WHERE id=?", (character_id,))
            connection.execute("DELETE FROM character_publications WHERE character_id=?", (character_id,))
            connection.execute("DELETE FROM character_stats WHERE character_id=?", (character_id,))
            connection.execute("DELETE FROM character_model_assignments WHERE target_character_id=? OR source_character_id=?", (character_id, character_id))
            connection.execute("DELETE FROM project_settings WHERE key=? AND value=?", (ACTIVE_KEY, character_id))
        self.export()
