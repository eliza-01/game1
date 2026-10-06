from __future__ import annotations

from .common import ANIMATION_EXTENSIONS, _now
from opencloud_assets import create_animation_asset, wait_for_operation
from animation_reimport_check import find_confirmed_manual_reimport


class AnimationPublicationMixin:
    def publish_clip(self, clip_id: str, credentials: dict) -> dict:
        with self.connect() as connection:
            raw = connection.execute("SELECT * FROM animation_clips WHERE id=?", (clip_id,)).fetchone()
        if not raw:
            raise ValueError(f"unknown animation clip: {clip_id}")
        row = dict(raw)
        path = (self.root / str(row.get("prepared_path") or "")).resolve()
        if not path.is_file() or path.suffix.lower() not in ANIMATION_EXTENSIONS:
            raise ValueError("registered animation file is missing")
        if self._sha256(path) != str(row.get("sha256") or ""):
            raise ValueError("registered animation checksum does not match the prepared file")

        asset_id = str(row.get("asset_id") or "").strip()
        common = dict(
            display_name=str(row.get("name") or clip_id),
            description=str(credentials.get("description") or "game1 character animation"),
            creator_type=str(credentials["creatorType"]),
            creator_id=str(credentials["creatorId"]),
            api_key=str(credentials["apiKey"]),
        )
        if asset_id:
            if str(row.get("published_sha256") or "") == str(row.get("sha256") or ""):
                return self.clip(clip_id)
            raise ValueError(
                "animation content changed after publication. game1 preserves the permanent asset id; "
                "reimport it manually in Roblox Studio, then use Check Roblox Assets Animations in Asset Manager"
            )
        operation = create_animation_asset(path, **common)
        result = wait_for_operation(operation, api_key=str(credentials["apiKey"]))
        now = _now()
        with self.connect() as connection:
            connection.execute(
                """UPDATE animation_clips SET asset_id=?,published_sha256=?,moderation_state=?,published_at=?,updated_at=? WHERE id=?""",
                (result.asset_id, row["sha256"], result.moderation_state or "", now, now, clip_id),
            )
            connection.execute(
                """INSERT INTO animation_publications(
                       clip_id,clip_revision,asset_id,operation_path,sha256,moderation_state,published_at,asset_version_id,version_create_time,manual_verified
                   ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    clip_id, int(row.get("revision") or 1), result.asset_id, result.operation_path, row["sha256"],
                    result.moderation_state, now, str(result.revision_id or ""), "", 0,
                ),
            )
        self.export()
        return self.clip(clip_id)

    def publish_missing(self, character_id: str, credentials: dict) -> dict:
        rows = self.list_for_character(character_id)
        queue = [row for row in rows if row["status"] == "LOCAL_ONLY"]
        published = []
        failed = []
        for index, row in enumerate(queue, start=1):
            try:
                published.append(self.publish_clip(str(row["clip_id"]), credentials))
            except Exception as exc:
                failed.append({"clipId": row["clip_id"], "name": row["name"], "error": str(exc)})
                break
        return {"requested": len(queue), "published": published, "failed": failed, "snapshot": self.snapshot(character_id)}

    def check_manual_reimports(self, credentials: dict) -> dict:
        with self.connect() as connection:
            changed = [dict(row) for row in connection.execute(
                """SELECT * FROM animation_clips
                   WHERE asset_id IS NOT NULL AND asset_id<>'' AND published_sha256<>sha256
                   ORDER BY character_id,name,id"""
            )]

        confirmed = pending = failed = 0
        details = []
        for row in changed:
            clip_id = str(row.get("id") or "")
            asset_id = str(row.get("asset_id") or "")
            try:
                with self.connect() as connection:
                    version_rows = connection.execute(
                        "SELECT asset_version_id FROM animation_publications WHERE clip_id=? AND asset_id=?",
                        (clip_id, asset_id),
                    ).fetchall()
                known_versions = [str(version["asset_version_id"] or "") for version in version_rows]
                candidate = find_confirmed_manual_reimport(
                    asset_id=asset_id,
                    content_updated_at=float(row.get("content_updated_at") or row.get("updated_at") or 0),
                    known_version_ids=known_versions,
                    creator_type=str(credentials.get("creatorType") or ""),
                    creator_id=str(credentials.get("creatorId") or ""),
                    api_key=str(credentials.get("apiKey") or ""),
                )
                if candidate is None:
                    pending += 1
                    details.append({
                        "targetType": "character", "targetId": str(row.get("character_id") or ""),
                        "clipId": clip_id, "name": str(row.get("name") or ""), "assetId": asset_id,
                        "status": "PENDING", "message": "no newer Approved Roblox version found after the local content change",
                    })
                    continue
                now = _now()
                version_id = str(candidate.get("versionId") or "")
                version_create_time = str(candidate.get("versionCreateTime") or "")
                moderation = str(candidate.get("moderationState") or "Approved")
                with self.connect() as connection:
                    connection.execute(
                        """UPDATE animation_clips
                           SET published_sha256=sha256,moderation_state=?,published_at=?,updated_at=?
                           WHERE id=?""",
                        (moderation, now, now, clip_id),
                    )
                    connection.execute(
                        """INSERT INTO animation_publications(
                               clip_id,clip_revision,asset_id,operation_path,sha256,moderation_state,published_at,asset_version_id,version_create_time,manual_verified
                           ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (
                            clip_id, int(row.get("revision") or 1), asset_id,
                            f"roblox/manual-version-confirmation/{asset_id}/{version_id or 'unknown'}",
                            str(row.get("sha256") or ""), moderation, now, version_id, version_create_time, 1,
                        ),
                    )
                confirmed += 1
                details.append({
                    "targetType": "character", "targetId": str(row.get("character_id") or ""),
                    "clipId": clip_id, "name": str(row.get("name") or ""), "assetId": asset_id,
                    "status": "CONFIRMED", "versionId": version_id, "versionCreateTime": version_create_time,
                })
            except Exception as exc:
                failed += 1
                details.append({
                    "targetType": "character", "targetId": str(row.get("character_id") or ""),
                    "clipId": clip_id, "name": str(row.get("name") or ""), "assetId": asset_id,
                    "status": "ERROR", "message": str(exc),
                })
        if confirmed:
            self.export()
        return {"requested": len(changed), "confirmed": confirmed, "pending": pending, "failed": failed, "details": details}
