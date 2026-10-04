from __future__ import annotations

from .common import ANIMATION_EXTENSIONS, _now
from opencloud_assets import create_animation_asset, wait_for_operation


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
                "update it through the studio animation-version bridge instead of creating a duplicate asset"
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
                """INSERT INTO animation_publications(clip_id,clip_revision,asset_id,operation_path,sha256,moderation_state,published_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (clip_id, int(row.get("revision") or 1), result.asset_id, result.operation_path, row["sha256"], result.moderation_state, now),
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
