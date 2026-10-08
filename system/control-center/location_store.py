from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import uuid

SCHEMA_VERSION = 1
RUNTIME_SCHEMA_VERSION = 1
PROJECT = "game1"
MAX_POINTS = 128


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite(value: object, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: tuple[float, float], b: tuple[float, float], point: tuple[float, float]) -> bool:
    return (
        min(a[0], b[0]) - 1e-7 <= point[0] <= max(a[0], b[0]) + 1e-7
        and min(a[1], b[1]) - 1e-7 <= point[1] <= max(a[1], b[1]) + 1e-7
        and abs(_orientation(a, b, point)) <= 1e-7
    )


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    if ((o1 > 0 > o2) or (o1 < 0 < o2)) and ((o3 > 0 > o4) or (o3 < 0 < o4)):
        return True
    return (
        (abs(o1) <= 1e-7 and _on_segment(a, b, c))
        or (abs(o2) <= 1e-7 and _on_segment(a, b, d))
        or (abs(o3) <= 1e-7 and _on_segment(c, d, a))
        or (abs(o4) <= 1e-7 and _on_segment(c, d, b))
    )


class LocationStore:
    """Project-owned polygon locations authored in Studio Edit mode."""

    def __init__(self, root: Path, bridge):
        self.root = root.resolve()
        self.bridge = bridge
        self.manifest_path = self.root / "assets/manifests/locations.json"
        self.registry_path = self.root / "src/shared/world/LocationRegistry.luau"
        self._ensure()

    @staticmethod
    def _empty() -> dict:
        return {"schemaVersion": SCHEMA_VERSION, "project": PROJECT, "records": {}}

    def _ensure(self) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.is_file():
            self._atomic_json(self.manifest_path, self._empty())
        manifest = self._load()
        self._write_registry(manifest)

    def _load(self) -> dict:
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"cannot read locations.json: {exc}") from exc
        if value.get("schemaVersion") != SCHEMA_VERSION or value.get("project") != PROJECT:
            raise ValueError("invalid locations.json schema/project")
        if not isinstance(value.get("records"), dict):
            raise ValueError("invalid locations.json records")
        return value

    @staticmethod
    def _normalize_points(raw_points: object) -> list[dict]:
        if not isinstance(raw_points, list):
            raise ValueError("Location polygon points are missing")
        if len(raw_points) < 3:
            raise ValueError("Location polygon must contain at least 3 points")
        if len(raw_points) > MAX_POINTS:
            raise ValueError(f"Location polygon cannot contain more than {MAX_POINTS} points")
        points = []
        for index, raw in enumerate(raw_points, start=1):
            if not isinstance(raw, dict):
                raise ValueError(f"Location point {index} is invalid")
            points.append({
                "x": round(_finite(raw.get("x"), f"Point {index} X"), 4),
                "y": round(_finite(raw.get("y"), f"Point {index} Y"), 4),
                "z": round(_finite(raw.get("z"), f"Point {index} Z"), 4),
            })
        return points

    @classmethod
    def _validate_polygon(cls, raw_points: object) -> list[dict]:
        points = cls._normalize_points(raw_points)
        xz = [(point["x"], point["z"]) for point in points]
        if len({(round(x, 4), round(z, 4)) for x, z in xz}) < 3:
            raise ValueError("Location polygon must contain at least 3 unique X/Z points")

        count = len(xz)
        for index in range(count):
            a = xz[index]
            b = xz[(index + 1) % count]
            if math.dist(a, b) < 0.01:
                raise ValueError(f"Location polygon edge {index + 1} is too short")
            for other in range(index + 1, count):
                if other == index or other == (index + 1) % count or (other + 1) % count == index:
                    continue
                c = xz[other]
                d = xz[(other + 1) % count]
                if _segments_intersect(a, b, c, d):
                    raise ValueError("Location polygon must not self-intersect")

        twice_area = 0.0
        for index, current in enumerate(xz):
            following = xz[(index + 1) % count]
            twice_area += current[0] * following[1] - following[0] * current[1]
        if abs(twice_area) < 2.0:
            raise ValueError("Location polygon area is too small")
        return points

    @staticmethod
    def _core(record: dict) -> dict:
        return {
            "locationId": str(record.get("locationId") or ""),
            "name": str(record.get("name") or ""),
            "placeId": int(record.get("placeId") or 0),
            "points": [
                {
                    "x": float(point.get("x") or 0),
                    "y": float(point.get("y") or 0),
                    "z": float(point.get("z") or 0),
                }
                for point in (record.get("points") or [])
            ],
        }

    @classmethod
    def _fingerprint(cls, record: dict) -> str:
        body = json.dumps(cls._core(record), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def _validate_record(self, payload: dict) -> dict:
        location_id = str(payload.get("locationId") or "").strip().casefold()
        if not re.fullmatch(r"location-[a-z0-9-]{12,64}", location_id):
            raise ValueError("Location ID is invalid")
        name = " ".join(str(payload.get("name") or "").strip().split())
        if not name or len(name) > 80:
            raise ValueError("Location name must contain from 1 to 80 characters")
        place_id = _finite(payload.get("placeId", 0), "Place ID")
        if place_id < 0 or not place_id.is_integer():
            raise ValueError("Place ID must be a non-negative integer")
        points = self._validate_polygon(payload.get("points"))
        now = utc_now()
        return {
            "locationId": location_id,
            "name": name,
            "placeId": int(place_id),
            "points": points,
            "createdAtUtc": str(payload.get("createdAtUtc") or now),
            "updatedAtUtc": now,
        }

    def _record_view(self, record: dict) -> dict:
        value = json.loads(json.dumps(record))
        sync = record.get("studioSync") or {}
        synchronized = sync.get("status") == "synced" and sync.get("recordFingerprint") == self._fingerprint(record)
        value["syncState"] = "synced" if synchronized else ("error" if sync.get("status") == "error" else "stale")
        value["pointCount"] = len(record.get("points") or [])
        return value

    def snapshot(self) -> dict:
        manifest = self._load()
        records = [self._record_view(row) for _, row in sorted(manifest["records"].items())]
        return {
            "schemaVersion": SCHEMA_VERSION,
            "project": PROJECT,
            "records": records,
            "recordCount": len(records),
            "manifestPath": self.manifest_path.relative_to(self.root).as_posix(),
            "registryPath": self.registry_path.relative_to(self.root).as_posix(),
        }

    def draw(self, payload: dict) -> dict:
        manifest = self._load()
        location_id = str(payload.get("locationId") or "").strip().casefold() or f"location-{uuid.uuid4().hex}"
        existing = manifest["records"].get(location_id) or {}
        name = " ".join(str(payload.get("name") or existing.get("name") or "New Location").strip().split()) or "New Location"
        result = self.bridge(
            "draw",
            operation_id=str(uuid.uuid4()),
            location_id=location_id,
            name=name,
            place_id=int(payload.get("placeId") or existing.get("placeId") or 0),
            points=payload.get("points") if isinstance(payload.get("points"), list) else existing.get("points") or [],
            timeout_seconds=300,
        )
        draft = {
            **existing,
            "locationId": location_id,
            "name": name,
            "placeId": int(result.get("placeId") or 0),
            "points": result.get("points") or [],
        }
        self._validate_polygon(draft["points"])
        return {"ok": True, "draft": draft, "studio": result}

    def register(self, payload: dict) -> dict:
        manifest = self._load()
        location_id = str(payload.get("locationId") or "").strip().casefold()
        existing = manifest["records"].get(location_id) or {}
        record = self._validate_record({**existing, **payload})
        fingerprint = self._fingerprint(record)
        prior_sync = existing.get("studioSync") or {}
        studio_current = (
            bool(existing)
            and prior_sync.get("status") == "synced"
            and prior_sync.get("recordFingerprint") == fingerprint
        )

        if studio_current:
            record["studioSync"] = dict(prior_sync)
            studio = {"ok": True, "synchronized": True, "skipped": True, "reason": "studio-fields-unchanged"}
        else:
            try:
                studio = self.bridge(
                    "upsert",
                    operation_id=str(uuid.uuid4()),
                    location_id=record["locationId"],
                    name=record["name"],
                    place_id=record["placeId"],
                    points=record["points"],
                    timeout_seconds=30,
                )
                record["studioSync"] = {
                    "status": "synced",
                    "recordFingerprint": fingerprint,
                    "placeId": int(studio.get("placeId") or record["placeId"]),
                    "markerPath": str(studio.get("markerPath") or ""),
                    "syncedAtUtc": utc_now(),
                }
            except Exception as exc:
                studio = {"ok": False, "synchronized": False, "error": str(exc)}
                record["studioSync"] = {
                    "status": "error",
                    "recordFingerprint": fingerprint,
                    "error": str(exc),
                    "attemptedAtUtc": utc_now(),
                }
        manifest["records"][record["locationId"]] = record
        self._commit(manifest)
        return {"ok": True, "record": self._record_view(record), "studio": studio}

    def select(self, payload: dict) -> dict:
        location_id = str(payload.get("locationId") or "").strip().casefold()
        if location_id not in self._load()["records"]:
            raise ValueError("Location is not registered")
        return self.bridge("select", operation_id=str(uuid.uuid4()), location_id=location_id, timeout_seconds=30)

    def restore(self) -> dict:
        manifest = self._load()
        records = [self._core(record) for record in manifest["records"].values()]
        result = self.bridge("sync", operation_id=str(uuid.uuid4()), records=records, timeout_seconds=45)
        synced_ids = {str(value) for value in (result.get("syncedLocationIds") or [])}
        now = utc_now()
        for record in manifest["records"].values():
            if record["locationId"] not in synced_ids:
                continue
            record["studioSync"] = {
                "status": "synced",
                "recordFingerprint": self._fingerprint(record),
                "placeId": int(result.get("placeId") or record.get("placeId") or 0),
                "markerPath": "",
                "syncedAtUtc": now,
            }
        self._commit(manifest)
        return {"ok": True, "studio": result, "recordCount": len(synced_ids), "totalRecordCount": len(records)}

    def delete(self, payload: dict) -> dict:
        manifest = self._load()
        location_id = str(payload.get("locationId") or "").strip().casefold()
        removed = manifest["records"].pop(location_id, None)
        if not removed:
            raise ValueError("Location is not registered")
        self._commit(manifest)
        try:
            studio = self.bridge("delete", operation_id=str(uuid.uuid4()), location_id=location_id, timeout_seconds=30)
        except Exception as exc:
            studio = {"ok": False, "error": str(exc)}
        return {"ok": True, "locationId": location_id, "studio": studio}

    def validate(self) -> dict:
        manifest = self._load()
        errors: list[str] = []
        seen: set[str] = set()
        for key, source in manifest["records"].items():
            try:
                record = self._validate_record(source)
                if key != record["locationId"]:
                    errors.append(f"record key mismatch: {key}")
                if record["locationId"] in seen:
                    errors.append(f"duplicate locationId: {record['locationId']}")
                seen.add(record["locationId"])
            except Exception as exc:
                errors.append(f"{key}: {exc}")
        expected = self._runtime_payload(manifest)
        if not self.registry_path.is_file():
            errors.append("LocationRegistry.luau is missing")
        elif expected["sourceDigest"] not in self.registry_path.read_text(encoding="utf-8"):
            errors.append("LocationRegistry.luau is stale")
        if errors:
            raise ValueError("Location validation failed: " + " | ".join(errors))
        return {"ok": True, "recordCount": len(manifest["records"]), "registryCurrent": True}

    def _runtime_payload(self, manifest: dict) -> dict:
        records = [self._core(row) for _, row in sorted(manifest["records"].items())]
        digest = hashlib.sha256(
            json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "schemaVersion": RUNTIME_SCHEMA_VERSION,
            "project": PROJECT,
            "sourceDigest": digest,
            "records": records,
        }

    def _write_registry(self, manifest: dict) -> None:
        payload = self._runtime_payload(manifest)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(
            "-- generated from assets/manifests/locations.json. do not edit by hand.\n"
            "-- client-readable polygon location registry.\n"
            "local HttpService = game:GetService(\"HttpService\")\n\n"
            f"local data = HttpService:JSONDecode([==[{encoded}]==])\n\n"
            "return table.freeze(data)\n",
            encoding="utf-8",
        )

    def _commit(self, manifest: dict) -> None:
        self._atomic_json(self.manifest_path, manifest)
        self._write_registry(manifest)

    @staticmethod
    def _atomic_json(path: Path, value: dict) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
