"""Animation publication and manual Roblox version confirmation for Monster/NPC."""
from __future__ import annotations


import time
from opencloud_assets import create_animation_asset, wait_for_operation
from animation_reimport_check import find_confirmed_manual_reimport

class MonsterAnimationPublicationMixin:
    def publish_clip(self, clip_id: str, credentials: dict) -> dict:
        with self.connect() as connection:
            raw = connection.execute("SELECT * FROM monster_animation_clips WHERE id=?", (clip_id,)).fetchone()
        if not raw:
            raise ValueError(f"unknown monster animation clip: {clip_id}")
        row = dict(raw)
        path = self.root / str(row.get("prepared_path") or row.get("source_path") or "")
        if not path.is_file():
            raise ValueError("registered monster animation file is missing")
        asset_id = str(row.get("asset_id") or "").strip()
        if asset_id:
            if str(row.get("published_sha256") or "") == str(row.get("sha256") or ""):
                return row
            raise ValueError("monster animation changed after publication; preserve the permanent animation asset id, reimport it manually in Roblox Studio, then use Check Roblox Assets Animations")
        operation = create_animation_asset(
            path,
            display_name=str(row.get("name") or clip_id),
            description=str(credentials.get("description") or "game1 monster animation"),
            creator_type=str(credentials["creatorType"]), creator_id=str(credentials["creatorId"]), api_key=str(credentials["apiKey"]),
        )
        result = wait_for_operation(operation, api_key=str(credentials["apiKey"]))
        now = time.time()
        with self.connect() as connection:
            connection.execute(
                "UPDATE monster_animation_clips SET asset_id=?,published_sha256=?,moderation_state=?,published_at=?,updated_at=? WHERE id=?",
                (result.asset_id, row["sha256"], result.moderation_state or "", now, now, clip_id),
            )
            connection.execute(
                """INSERT INTO monster_animation_publications(
                       clip_id,clip_revision,asset_id,operation_path,sha256,moderation_state,published_at,asset_version_id,version_create_time,manual_verified
                   ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    clip_id, int(row.get("revision") or 1), result.asset_id, result.operation_path, row["sha256"],
                    result.moderation_state or "", now, str(result.revision_id or ""), "", 0,
                ),
            )
        self.export()
        return {**row, "asset_id": result.asset_id, "published_sha256": row["sha256"], "status": "PUBLISHED"}

    def check_manual_reimports(self, credentials: dict) -> dict:
        with self.connect() as connection:
            changed = [dict(row) for row in connection.execute(
                """SELECT * FROM monster_animation_clips
                   WHERE asset_id IS NOT NULL AND asset_id<>'' AND published_sha256<>sha256
                   ORDER BY monster_slug,name,id"""
            )]
        confirmed = pending = failed = 0
        details = []
        for row in changed:
            clip_id = str(row.get("id") or "")
            asset_id = str(row.get("asset_id") or "")
            try:
                with self.connect() as connection:
                    version_rows = connection.execute(
                        "SELECT asset_version_id FROM monster_animation_publications WHERE clip_id=? AND asset_id=?",
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
                        "targetType": "monster", "targetId": str(row.get("monster_slug") or ""),
                        "clipId": clip_id, "name": str(row.get("name") or ""), "assetId": asset_id,
                        "status": "PENDING", "message": "no newer Approved Roblox version found after the local content change",
                    })
                    continue
                now = time.time()
                version_id = str(candidate.get("versionId") or "")
                version_create_time = str(candidate.get("versionCreateTime") or "")
                moderation = str(candidate.get("moderationState") or "Approved")
                with self.connect() as connection:
                    connection.execute(
                        """UPDATE monster_animation_clips
                           SET published_sha256=sha256,moderation_state=?,published_at=?,updated_at=? WHERE id=?""",
                        (moderation, now, now, clip_id),
                    )
                    connection.execute(
                        """INSERT INTO monster_animation_publications(
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
                    "targetType": "monster", "targetId": str(row.get("monster_slug") or ""),
                    "clipId": clip_id, "name": str(row.get("name") or ""), "assetId": asset_id,
                    "status": "CONFIRMED", "versionId": version_id, "versionCreateTime": version_create_time,
                })
            except Exception as exc:
                failed += 1
                details.append({
                    "targetType": "monster", "targetId": str(row.get("monster_slug") or ""),
                    "clipId": clip_id, "name": str(row.get("name") or ""), "assetId": asset_id,
                    "status": "ERROR", "message": str(exc),
                })
        if confirmed:
            self.export()
        return {"requested": len(changed), "confirmed": confirmed, "pending": pending, "failed": failed, "details": details}

    def publish_missing(self, slug: str, credentials: dict) -> dict:
        queue = [row for row in self.list_for_monster(slug) if row["status"] == "LOCAL_ONLY"]
        published, failed = [], []
        for row in queue:
            try:
                published.append(self.publish_clip(str(row["clip_id"]), credentials))
            except Exception as exc:
                failed.append({"clipId": row["clip_id"], "name": row["name"], "error": str(exc)})
                break
        return {"requested": len(queue), "published": published, "failed": failed, "snapshot": self.snapshot(slug)}
