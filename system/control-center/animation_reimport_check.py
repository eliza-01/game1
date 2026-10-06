from __future__ import annotations

from datetime import datetime, timezone

from opencloud_assets import list_asset_versions


def _parse_roblox_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _version_id(row: dict) -> int | None:
    path = str(row.get("path") or "").rstrip("/")
    token = path.split("/")[-1] if path else ""
    if token.isdigit():
        return int(token)
    revision = str(row.get("revisionId") or "").strip()
    return int(revision) if revision.isdigit() else None


def _creator_matches(row: dict, creator_type: str, creator_id: str) -> bool:
    creator = (row.get("creationContext") or {}).get("creator") or {}
    if creator_type == "user":
        return str(creator.get("userId") or "") == creator_id
    if creator_type == "group":
        return str(creator.get("groupId") or "") == creator_id
    return False


def find_confirmed_manual_reimport(
    *,
    asset_id: str,
    content_updated_at: float,
    known_version_ids: list[str],
    creator_type: str,
    creator_id: str,
    api_key: str,
) -> dict | None:
    """Return the newest safe Roblox version created after this local content revision.

    This intentionally mirrors the RobloxLineage manual animation reimport flow:
    local content is detected by SHA; Studio performs the overwrite manually; the
    control-center then observes Roblox asset versions through Open Cloud. No
    KeyframeSequence/content readback from Studio is involved.
    """
    newest_known = max((int(value) for value in known_version_ids if str(value).isdigit()), default=0)
    changed_at = datetime.fromtimestamp(max(0.0, float(content_updated_at or 0)), tz=timezone.utc)
    candidates: list[tuple[int, datetime, dict]] = []
    for row in list_asset_versions(asset_id, api_key=api_key):
        version_id = _version_id(row)
        if version_id is None or version_id <= newest_known:
            continue
        created_at = _parse_roblox_time(row.get("createTime"))
        if created_at is None or created_at < changed_at:
            continue
        if not _creator_matches(row, creator_type, creator_id):
            continue
        moderation = (row.get("moderationResult") or {}).get("moderationState")
        if row.get("published") is not True or moderation != "Approved":
            continue
        candidates.append((version_id, created_at, row))
    if not candidates:
        return None
    version_id, created_at, row = max(candidates, key=lambda value: (value[0], value[1]))
    return {
        "assetId": str(asset_id),
        "versionId": str(version_id),
        "versionCreateTime": created_at.isoformat().replace("+00:00", "Z"),
        "moderationState": str((row.get("moderationResult") or {}).get("moderationState") or "Approved"),
    }
