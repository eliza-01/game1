from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json


class DecoLayoutStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.backup_dir = self.root / "assets/backups/deco-layouts"
        self.latest_path = self.root / "assets/manifests/deco-layout-latest.json"

    @staticmethod
    def _validate_record(record: dict, index: int) -> dict:
        if not isinstance(record, dict):
            raise ValueError(f"deco record {index} must be an object")
        location_asset_id = str(record.get("locationAssetId") or "").strip().lower()
        cframe = record.get("cframe")
        if not location_asset_id:
            raise ValueError(f"deco record {index} is missing locationAssetId")
        if not isinstance(cframe, list) or len(cframe) != 12:
            raise ValueError(f"deco record {index} cframe must contain 12 numbers")
        try:
            normalized_cframe = [float(value) for value in cframe]
            scale = float(record.get("scale") or 1)
        except (TypeError, ValueError):
            raise ValueError(f"deco record {index} contains non-numeric transform data")
        if scale <= 0:
            raise ValueError(f"deco record {index} scale must be positive")
        return {
            "instanceId": str(record.get("instanceId") or "").strip(),
            "name": str(record.get("name") or location_asset_id).strip(),
            "locationAssetId": location_asset_id,
            "cframe": normalized_cframe,
            "scale": scale,
        }

    def save(self, payload: dict) -> dict:
        raw_records = payload.get("records") or []
        if not isinstance(raw_records, list):
            raise ValueError("deco layout records must be an array")
        records = [self._validate_record(record, index + 1) for index, record in enumerate(raw_records)]
        now = datetime.now(timezone.utc)
        stamp = now.strftime("%Y%m%dT%H%M%S-%fZ")
        snapshot = {
            "schemaVersion": 2,
            "project": "game1",
            "savedAt": now.isoformat().replace("+00:00", "Z"),
            "placeId": int(payload.get("placeId") or 0),
            "placeName": str(payload.get("placeName") or "").strip(),
            "records": records,
            "summary": {"placed": len(records)},
        }
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.latest_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = self.backup_dir / f"deco-layout-{stamp}.json"
        encoded = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
        backup_path.write_text(encoded, encoding="utf-8")
        self.latest_path.write_text(encoded, encoding="utf-8")
        return {
            "ok": True,
            "placed": len(records),
            "backupPath": backup_path.relative_to(self.root).as_posix(),
            "latestPath": self.latest_path.relative_to(self.root).as_posix(),
            "savedAt": snapshot["savedAt"],
        }
