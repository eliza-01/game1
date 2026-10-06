from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math
import re
import uuid
from datetime import datetime, timezone

SCHEMA_VERSION = 1
PROJECT = "game1"
REQUIRED_ANIMATION_SLOTS = ("walk", "run", "combat_idle", "attack", "death")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite(value, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


class MonsterSpawnStore:
    def __init__(self, root: Path, monsters, animations, bridge):
        self.root = root.resolve()
        self.monsters = monsters
        self.animations = animations
        self.bridge = bridge
        self.manifest_path = self.root / "assets/manifests/monster-spawns.json"
        self.registry_path = self.root / "src/server/monster/MonsterSpawnRegistry.luau"
        self._ensure()

    @staticmethod
    def _empty() -> dict:
        return {"schemaVersion": SCHEMA_VERSION, "project": PROJECT, "records": {}}

    def _ensure(self):
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.is_file():
            self.manifest_path.write_text(json.dumps(self._empty(), indent=2) + "\n", encoding="utf-8")
        manifest = self._load()
        self._write_registry(manifest)

    def _load(self) -> dict:
        value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if value.get("schemaVersion") != SCHEMA_VERSION or value.get("project") != PROJECT:
            raise ValueError("invalid monster-spawns.json schema/project")
        if not isinstance(value.get("records"), dict):
            raise ValueError("invalid monster-spawns.json records")
        return value

    @staticmethod
    def _core(record: dict) -> dict:
        position = record.get("position") or {}
        return {
            "spawnId": str(record.get("spawnId") or ""),
            "monsterSlug": str(record.get("monsterSlug") or ""),
            "mapKey": str(record.get("mapKey") or ""),
            "placeId": int(record.get("placeId") or 0),
            "position": {
                "x": float(position.get("x") or 0),
                "y": float(position.get("y") or 0),
                "z": float(position.get("z") or 0),
            },
            "yawDegrees": float(record.get("yawDegrees") or 0),
            "respawnSeconds": float(record.get("respawnSeconds") or 0),
            "spawnRadius": float(record.get("spawnRadius") or 0),
            "maxAlive": int(record.get("maxAlive") or 1),
            "enabled": record.get("enabled") is not False,
        }

    @classmethod
    def _fingerprint(cls, record: dict) -> str:
        source = json.dumps(cls._core(record), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def _monster(self, slug: str) -> dict:
        row = self.monsters.get(str(slug or "").strip().lower())
        if not row:
            raise ValueError(f"unknown monster: {slug}")
        return row

    def readiness(self, slug: str) -> dict:
        monster = self._monster(slug)
        reasons = []
        if str(monster.get("status") or "") != "PUBLISHED":
            reasons.append("Monster model/textures are not published/current.")
        if not str(monster.get("model_asset_id") or "").isdigit():
            reasons.append("Monster model has no Roblox asset id.")
        rows = self.animations.list_for_monster(str(monster["slug"]))
        published_slots = {str(row.get("slot") or "") for row in rows if str(row.get("status") or "") == "PUBLISHED"}
        missing = [slot for slot in REQUIRED_ANIMATION_SLOTS if slot not in published_slots]
        if missing:
            reasons.append("Required published animations are missing: " + ", ".join(missing) + ".")
        return {
            "ready": not reasons,
            "reasons": reasons,
            "monsterSlug": str(monster["slug"]),
            "name": str(monster.get("name_en") or monster["slug"]),
            "status": str(monster.get("status") or ""),
            "modelAssetId": str(monster.get("model_asset_id") or ""),
            "publishedAnimationSlots": sorted(published_slots),
        }

    def _validate(self, payload: dict) -> dict:
        spawn_id = str(payload.get("spawnId") or "").strip().lower()
        if not re.fullmatch(r"spawn-[a-z0-9-]{12,64}", spawn_id):
            raise ValueError("Spawn ID is invalid")
        monster = self._monster(payload.get("monsterSlug"))
        map_key = str(payload.get("mapKey") or "main").strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", map_key):
            raise ValueError("Map key must contain only a-z, 0-9, dot, underscore or dash")
        place_id = _finite(payload.get("placeId", 0), "Place ID")
        if place_id < 0 or not place_id.is_integer():
            raise ValueError("Place ID must be a non-negative integer")
        source_position = payload.get("position") or {}
        if not isinstance(source_position, dict):
            raise ValueError("Spawn position is missing")
        position = {axis: _finite(source_position.get(axis), axis.upper()) for axis in ("x", "y", "z")}
        yaw = _finite(payload.get("yawDegrees", 0), "Yaw") % 360
        respawn = _finite(payload.get("respawnSeconds", 10), "Respawn Seconds")
        radius = _finite(payload.get("spawnRadius", 0), "Spawn Radius")
        max_alive = _finite(payload.get("maxAlive", 1), "Max Alive")
        if respawn < 0 or respawn > 86400:
            raise ValueError("Respawn Seconds must be 0..86400")
        if radius < 0 or radius > 10000:
            raise ValueError("Spawn Radius must be 0..10000 studs")
        if not max_alive.is_integer() or max_alive < 1 or max_alive > 1000:
            raise ValueError("Max Alive must be an integer 1..1000")
        now = utc_now()
        return {
            "spawnId": spawn_id,
            "monsterSlug": str(monster["slug"]),
            "mapKey": map_key,
            "placeId": int(place_id),
            "position": position,
            "yawDegrees": yaw,
            "respawnSeconds": respawn,
            "spawnRadius": radius,
            "maxAlive": int(max_alive),
            "enabled": payload.get("enabled") is not False,
            "createdAtUtc": str(payload.get("createdAtUtc") or now),
            "updatedAtUtc": now,
        }

    def _record_view(self, record: dict) -> dict:
        value = json.loads(json.dumps(record))
        monster = self._monster(record.get("monsterSlug"))
        value["monster"] = {
            "slug": str(monster["slug"]),
            "name": str(monster.get("name_en") or monster["slug"]),
            "nameRu": str(monster.get("name_ru") or ""),
            "status": str(monster.get("status") or ""),
        }
        value["readiness"] = self.readiness(str(monster["slug"]))
        studio_sync = record.get("studioSync") or {}
        synced = studio_sync.get("status") == "synced" and studio_sync.get("recordFingerprint") == self._fingerprint(record)
        value["syncState"] = "synced" if synced else "stale"
        return value

    def snapshot(self) -> dict:
        manifest = self._load()
        monster_rows = []
        for row in self.monsters.list():
            ready = self.readiness(str(row["slug"]))
            monster_rows.append({
                "slug": str(row["slug"]),
                "name": str(row.get("name_en") or row["slug"]),
                "nameRu": str(row.get("name_ru") or ""),
                "status": str(row.get("status") or ""),
                "ready": bool(ready["ready"]),
                "reasons": ready["reasons"],
            })
        records = [self._record_view(row) for _, row in sorted(manifest["records"].items())]
        return {
            "schemaVersion": SCHEMA_VERSION,
            "project": PROJECT,
            "records": records,
            "recordCount": len(records),
            "monsters": monster_rows,
            "defaults": {"mapKey": "main", "respawnSeconds": 10, "spawnRadius": 0, "maxAlive": 1},
            "manifestPath": self.manifest_path.relative_to(self.root).as_posix(),
            "registryPath": self.registry_path.relative_to(self.root).as_posix(),
        }

    def place(self, payload: dict) -> dict:
        monster = self._monster(payload.get("monsterSlug"))
        ready = self.readiness(str(monster["slug"]))
        if not ready["ready"]:
            raise ValueError("Monster Spawn is blocked: " + " ".join(ready["reasons"]))
        spawn_id = str(payload.get("spawnId") or "").strip().lower() or f"spawn-{uuid.uuid4().hex}"
        existing = self._load()["records"].get(spawn_id) or {}
        result = self.bridge(
            "place",
            operation_id=str(uuid.uuid4()),
            spawn_id=spawn_id,
            monster_slug=str(monster["slug"]),
            monster_name=str(monster.get("name_en") or monster["slug"]),
            map_key=str(payload.get("mapKey") or existing.get("mapKey") or "main"),
            place_id=int(payload.get("placeId") or existing.get("placeId") or 0),
            position=payload.get("position") if isinstance(payload.get("position"), dict) else existing.get("position"),
            yaw_degrees=payload.get("yawDegrees", existing.get("yawDegrees", 0)),
            spawn_radius=payload.get("spawnRadius", existing.get("spawnRadius", 0)),
            max_alive=payload.get("maxAlive", existing.get("maxAlive", 1)),
            enabled=payload.get("enabled", existing.get("enabled", True)),
            timeout_seconds=300,
        )
        draft = {
            **existing,
            "spawnId": spawn_id,
            "monsterSlug": str(monster["slug"]),
            "mapKey": str(result.get("mapKey") or payload.get("mapKey") or "main"),
            "placeId": int(result.get("placeId") or 0),
            "position": result.get("position") or {},
            "yawDegrees": float(result.get("yawDegrees") or 0),
            "respawnSeconds": float(payload.get("respawnSeconds", existing.get("respawnSeconds", 10))),
            "spawnRadius": float(payload.get("spawnRadius", existing.get("spawnRadius", 0))),
            "maxAlive": int(payload.get("maxAlive", existing.get("maxAlive", 1))),
            "enabled": payload.get("enabled", existing.get("enabled", True)) is not False,
        }
        return {"ok": True, "draft": draft, "studio": result, "readiness": ready}

    def register(self, payload: dict) -> dict:
        manifest = self._load()
        spawn_id = str(payload.get("spawnId") or "").strip().lower()
        existing = manifest["records"].get(spawn_id) or {}
        record = self._validate({**existing, **payload})
        ready = self.readiness(record["monsterSlug"])
        if not ready["ready"]:
            raise ValueError("Monster Spawn is blocked: " + " ".join(ready["reasons"]))
        manifest["records"][record["spawnId"]] = record
        self._commit(manifest)
        try:
            monster = self._monster(record["monsterSlug"])
            studio = self.bridge(
                "upsert", operation_id=str(uuid.uuid4()), spawn_id=record["spawnId"],
                monster_slug=record["monsterSlug"], monster_name=str(monster.get("name_en") or record["monsterSlug"]),
                map_key=record["mapKey"], place_id=record["placeId"], position=record["position"],
                yaw_degrees=record["yawDegrees"], spawn_radius=record["spawnRadius"], max_alive=record["maxAlive"],
                enabled=record["enabled"], timeout_seconds=30,
            )
            record["studioSync"] = {
                "status": "synced", "recordFingerprint": self._fingerprint(record),
                "placeId": int(studio.get("placeId") or record["placeId"]),
                "markerPath": str(studio.get("markerPath") or ""), "syncedAtUtc": utc_now(),
            }
        except Exception as exc:
            studio = {"ok": False, "error": str(exc)}
            record["studioSync"] = {
                "status": "error", "recordFingerprint": self._fingerprint(record),
                "error": str(exc), "attemptedAtUtc": utc_now(),
            }
        manifest["records"][record["spawnId"]] = record
        self._commit(manifest)
        return {"ok": True, "record": self._record_view(record), "studio": studio}

    def select(self, payload: dict) -> dict:
        spawn_id = str(payload.get("spawnId") or "").strip().lower()
        if spawn_id not in self._load()["records"]:
            raise ValueError("Monster Spawn is not registered")
        return self.bridge("select", operation_id=str(uuid.uuid4()), spawn_id=spawn_id, timeout_seconds=30)

    def delete(self, payload: dict) -> dict:
        manifest = self._load()
        spawn_id = str(payload.get("spawnId") or "").strip().lower()
        removed = manifest["records"].pop(spawn_id, None)
        if not removed:
            raise ValueError("Monster Spawn is not registered")
        self._commit(manifest)
        try:
            studio = self.bridge("delete", operation_id=str(uuid.uuid4()), spawn_id=spawn_id, timeout_seconds=30)
        except Exception as exc:
            studio = {"ok": False, "error": str(exc)}
        return {"ok": True, "spawnId": spawn_id, "studio": studio}

    def restore(self) -> dict:
        manifest = self._load()
        records = []
        for record in manifest["records"].values():
            monster = self._monster(record["monsterSlug"])
            records.append({**self._core(record), "monsterName": str(monster.get("name_en") or record["monsterSlug"])})
        result = self.bridge("sync", operation_id=str(uuid.uuid4()), records=records, timeout_seconds=45)
        synced = {str(value) for value in result.get("syncedSpawnIds") or []}
        now = utc_now()
        for record in manifest["records"].values():
            if record["spawnId"] in synced:
                record["studioSync"] = {"status": "synced", "recordFingerprint": self._fingerprint(record), "syncedAtUtc": now}
        self._commit(manifest)
        return {"ok": True, "studio": result, "recordCount": len(synced), "totalRecordCount": len(records)}

    def validate(self) -> dict:
        manifest = self._load()
        errors = []
        for key, source in manifest["records"].items():
            try:
                row = self._validate(source)
                if key != row["spawnId"]:
                    errors.append(f"record key mismatch: {key}")
                ready = self.readiness(row["monsterSlug"])
                if not ready["ready"]:
                    errors.append(f"{key}: {' '.join(ready['reasons'])}")
            except Exception as exc:
                errors.append(f"{key}: {exc}")
        if errors:
            raise ValueError("Monster Spawn validation failed: " + " | ".join(errors))
        return {"ok": True, "recordCount": len(manifest["records"]), "registryCurrent": True}

    def monster_usage(self, slug: str) -> list[str]:
        slug = str(slug or "").strip().lower()
        return [str(row.get("spawnId") or "") for row in self._load()["records"].values() if str(row.get("monsterSlug") or "") == slug]

    def _write_registry(self, manifest: dict):
        records = [self._core(row) for _, row in sorted(manifest["records"].items())]
        digest = hashlib.sha256(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        payload = {"schemaVersion": 1, "project": PROJECT, "sourceDigest": digest, "records": records}
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(
            "-- generated. do not edit by hand.\n"
            "local HttpService = game:GetService(\"HttpService\")\n"
            f"local data = HttpService:JSONDecode([==[{encoded}]==])\n"
            "return table.freeze(data)\n",
            encoding="utf-8",
        )

    def _commit(self, manifest: dict):
        tmp = self.manifest_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.manifest_path)
        self._write_registry(manifest)
