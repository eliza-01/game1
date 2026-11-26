from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math
import re
import uuid
import threading
from services import game_balance
from datetime import datetime, timezone

SCHEMA_VERSION = 1
PROJECT = "game1"
REQUIRED_ANIMATION_SLOTS = ("walk", "run", "combat_idle", "attack", "death")
MONSTER_SPAWN_DEFAULTS = {"mapKey": "main", "spawnRadius": 15, "maxAlive": 3,
                          "homeRadiusStuds": 150, "respawnSeconds": 10, "enabled": True}


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
    def __init__(self, root: Path, monsters, animations, bridge, kind: str = "monster"):
        if kind not in {"monster", "npc"}:
            raise ValueError("unsupported spawn kind")
        self.kind = kind
        self.root = root.resolve()
        self.monsters = monsters
        self.animations = animations
        self.bridge = bridge
        self._lock = threading.RLock()
        self.manifest_path = self.root / f"assets/manifests/{self.kind}-spawns.json"
        self.registry_path = self.root / ("src/server/npc/NpcSpawnRegistry.luau" if self.kind == "npc" else "src/server/monster/MonsterSpawnRegistry.luau")
        self._ensure()

    @staticmethod
    def _empty() -> dict:
        return {"schemaVersion": SCHEMA_VERSION, "project": PROJECT, "records": {}}

    def _ensure(self):
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.is_file():
            self.manifest_path.write_text(json.dumps(self._empty(), indent=2) + "\n", encoding="utf-8")
        manifest = self._load()
        # Idempotent upgrade: leash is per spawn for both NPCs and monsters.
        # Preserve the authored markers and keep a recoverable pre-upgrade file.
        changed = False
        for record in manifest["records"].values():
            if "homeRadiusStuds" not in record:
                default = 16.0 if self.kind == "npc" else 150.0
                if self.monsters is not None:
                    default = self.monsters.former_spawn_leash_for_migration(str(record.get("monsterSlug") or ""))
                record["homeRadiusStuds"] = default
                changed = True
        if changed:
            backup = self.manifest_path.with_suffix(".m396.backup.json")
            if not backup.exists():
                backup.write_bytes(self.manifest_path.read_bytes())
            self._commit(manifest)
        else:
            self._write_registry(manifest)

    def _load(self) -> dict:
        value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if value.get("schemaVersion") != SCHEMA_VERSION or value.get("project") != PROJECT:
            raise ValueError("invalid monster-spawns.json schema/project")
        if not isinstance(value.get("records"), dict):
            raise ValueError("invalid monster-spawns.json records")
        return value

    @staticmethod
    def _core(record: dict, *, npc: bool = False) -> dict:
        position = record.get("position") or {}
        result = {
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
            "enabled": record.get("enabled") is not False,
        }
        result["homeRadiusStuds"] = float(record.get("homeRadiusStuds", 16 if npc else 150))
        if not npc:
            result["spawnRadius"] = float(record.get("spawnRadius") or 0)
            result["maxAlive"] = int(record.get("maxAlive") or 1)
            # Old records without an override inherit the current Database row.
            if record.get("balanceId"):
                result["balanceId"] = record["balanceId"]
            if "deathChase" in record:
                result["deathChase"] = record["deathChase"]
            if "aggressive" in record:
                result["aggressive"] = record["aggressive"]
            if "aggroRadiusStuds" in record:
                result["aggroRadiusStuds"] = float(record["aggroRadiusStuds"])
        return result

    def _fingerprint(self, record: dict) -> str:
        marker = self._core(record, npc=self.kind == "npc")
        marker.pop("homeRadiusStuds", None)
        marker.pop("aggressive", None)
        marker.pop("aggroRadiusStuds", None)
        source = json.dumps(marker, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def _monster(self, slug: str) -> dict:
        row = self.monsters.get(str(slug or "").strip().lower())
        if not row:
            raise ValueError(f"unknown monster: {slug}")
        return row

    def _behavior_defaults(self, monster: dict, data=None) -> dict:
        if data is None and (self.root / 'config/balance/gameplay.json').is_file():
            data = game_balance.load(self.root)
        return game_balance.monster_spawn_defaults(data, monster)

    def _spawn_behavior(self, monster: dict, payload: dict) -> dict:
        defaults = self._behavior_defaults(monster)
        aggressive = payload.get('aggressive', defaults['aggressive'])
        if type(aggressive) is not bool:
            raise ValueError('Aggressive must be a boolean')
        radius = game_balance.number(payload.get('aggroRadiusStuds', defaults['aggroRadiusStuds']),
                                     0, 10000, 'Aggro Radius', False)
        return {'aggressive': aggressive, 'aggroRadiusStuds': radius}

    def readiness(self, slug: str) -> dict:
        monster = self._monster(slug)
        reasons = []
        if str(monster.get("status") or "") != "PUBLISHED":
            reasons.append(f"{self.kind.title()} model/textures are not published/current.")
        if not str(monster.get("model_asset_id") or "").isdigit():
            reasons.append(f"{self.kind.title()} model has no Roblox asset id.")
        rows = self.animations.list_for_monster(str(monster["slug"]))
        published_slots = {str(row.get("slot") or "") for row in rows if str(row.get("status") or "") == "PUBLISHED"}
        needed = ("idle", "death") if self.kind == "npc" else REQUIRED_ANIMATION_SLOTS
        missing = [slot for slot in needed if slot not in published_slots]
        # NPC presentation is optional: a published rig can stand in its bind pose,
        # and the death lifecycle can complete without an animation track. Monsters
        # retain their existing animation requirements.
        if missing and self.kind == "monster":
            reasons.append("Required published animations are missing: " + ", ".join(missing) + ".")
        return {
            "ready": not reasons,
            "reasons": reasons,
            "animationReady": not missing,
            "missingAnimationSlots": missing,
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
        balance_row = None
        if self.kind == "monster" and payload.get("balanceId"):
            balance_row = self._balance_row(payload["balanceId"])
            # A Database row is the authored identity, not a temporary model slug.
            monster = {"slug": ""}
        else:
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
        home_radius = _finite(payload.get("homeRadiusStuds", 16 if self.kind == "npc" else 150), "Home Leash")
        if not 1 <= home_radius <= 10000:
            raise ValueError("Home Leash must be 1..10000 studs")
        respawn = _finite(payload.get("respawnSeconds", 10), "Respawn Seconds")
        if respawn < 0 or respawn > 86400:
            raise ValueError("Respawn Seconds must be 0..86400")
        if self.kind == "monster":
            radius = _finite(payload.get("spawnRadius", 0), "Spawn Radius")
            max_alive = _finite(payload.get("maxAlive", 1), "Max Alive")
            if radius < 0 or radius > 10000:
                raise ValueError("Spawn Radius must be 0..10000 studs")
            if not max_alive.is_integer() or max_alive < 1 or max_alive > 1000:
                raise ValueError("Max Alive must be an integer 1..1000")
        now = utc_now()
        result = {
            "spawnId": spawn_id,
            "monsterSlug": str(monster["slug"]),
            "mapKey": map_key,
            "placeId": int(place_id),
            "position": position,
            "yawDegrees": yaw,
            "respawnSeconds": respawn,
            "homeRadiusStuds": home_radius,
            "enabled": payload.get("enabled") is not False,
            "createdAtUtc": str(payload.get("createdAtUtc") or now),
            "updatedAtUtc": now,
        }
        if self.kind == "npc":
            # Studio placement is distinct from model publication and registration.
            # Legacy records have only createdAtUtc: retain that historical date.
            placed = str(payload.get("placedAtUtc") or payload.get("createdAtUtc") or now)
            try:
                parsed = datetime.fromisoformat(placed.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError("timestamp lacks timezone")
            except ValueError as exc:
                raise ValueError("NPC placedAtUtc must be an ISO-8601 UTC timestamp") from exc
            result["placedAtUtc"] = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        else:
            result["spawnRadius"] = radius
            result["maxAlive"] = int(max_alive)
            if balance_row is not None:
                result["balanceId"] = balance_row["id"]
                for key in ("aggressive", "deathChase"):
                    value = payload.get(key, balance_row[key])
                    if type(value) is not bool:
                        raise ValueError(f"{key} must be a boolean")
                    result[key] = value
                result["aggroRadiusStuds"] = game_balance.number(
                    payload.get("aggroRadiusStuds", balance_row["aggroRadiusStuds"]),
                    0, 10000, "Aggro Radius", False)
            else:
                result.update(self._spawn_behavior(monster, payload))
                if "deathChase" in payload:
                    if type(payload["deathChase"]) is not bool:
                        raise ValueError("Death Chase must be a boolean")
                    result["deathChase"] = payload["deathChase"]
        return result

    def _record_view(self, record: dict, data=None) -> dict:
        value = json.loads(json.dumps(record))
        if self.kind == "npc":
            value.pop("spawnRadius", None)
            value.pop("maxAlive", None)
            value["placedAtUtc"] = value.get("placedAtUtc") or value.get("createdAtUtc")
        if self.kind == "monster" and record.get("balanceId"):
            data = data if data is not None else game_balance.load(self.root)
            row = self._balance_row(record["balanceId"], data)
            model = self._model_for_row(row, data)
            name = row["nameEn"] or row["id"]
            value["monsterName"] = name
            value["level"] = row["level"]
            value["monster"] = {"slug": model["slug"] if model else "", "name": name,
                                "nameRu": row["nameRu"], "status": model["status"] if model else "UNREGISTERED"}
            value["readiness"] = self.readiness(model["slug"]) if model else {
                "ready": False, "reasons": ["No unique model registered for this species."]}
            value["syncState"] = "saved"
            return value
        monster = self._monster(record.get("monsterSlug"))
        if self.kind == "monster":
            for key, default in self._behavior_defaults(monster, data).items():
                value.setdefault(key, default)
        value["monster"] = {
            "slug": str(monster["slug"]),
            "name": str(monster.get("name_en") or monster["slug"]),
            "nameRu": str(monster.get("name_ru") or ""),
            "status": str(monster.get("status") or ""),
        }
        value["readiness"] = self.readiness(str(monster["slug"]))
        if self.kind == "monster":
            binding = data["monsterBindings"].get(monster["slug"]) if data else None
            row = next((r for r in data["monsters"] if r["id"] == binding), None) if binding else None
            value["legacyBalanceId"] = binding
            value["level"] = row["level"] if row else None
            value["monsterName"] = value["monster"]["name"]
            value.setdefault("deathChase", bool(row and row["deathChase"]))
        studio_sync = record.get("studioSync") or {}
        synced = studio_sync.get("status") == "synced" and studio_sync.get("recordFingerprint") == self._fingerprint(record)
        value["syncState"] = "synced" if synced else "stale"
        return value

    def _balance_row(self, balance_id, data=None):
        data = data if data is not None else game_balance.load(self.root)
        row = next((r for r in data["monsters"] if r["id"] == balance_id), None)
        if row is None:
            raise ValueError("Unknown monster Database ID: " + str(balance_id))
        return row

    def _model_for_row(self, row, data, models=None):
        # Existing bindings may point at test proxies (Gremlin -> Toad).
        # For newly authored species require a matching model identity.
        if not row["nameEn"]:
            return None
        candidates = [m for m in (models if models is not None else self.monsters.list())
                      if str(m.get("name_en") or "").lower() == row["nameEn"].lower()]
        bound = [m for m in candidates if data["monsterBindings"].get(m["slug"]) == row["id"]]
        return bound[0] if len(bound) == 1 else candidates[0] if len(candidates) == 1 else None

    def studio_catalog(self):
        if self.kind != "monster":
            raise ValueError("Monster authoring only")
        with self._lock:
            data = game_balance.load(self.root)
            groups = {}
            models = self.monsters.list()
            readiness = {}
            for row in data["monsters"]:
                key = row["nameEn"] or row["id"]
                group = groups.setdefault(key, {"nameEn": row["nameEn"], "nameRu": row["nameRu"],
                                                "key": key, "levels": []})
                model = self._model_for_row(row, data, models)
                if model and model["slug"] not in readiness:
                    readiness[model["slug"]] = self.readiness(model["slug"])["ready"]
                group["levels"].append({**row, "modelSlug": model["slug"] if model else "",
                                        "ready": readiness[model["slug"]] if model else False})
            catalog = sorted(groups.values(), key=lambda g: (not bool(g["nameEn"]), g["key"].lower()))
            for group in catalog:
                group["levels"].sort(key=lambda r: (r["level"], r["type"], r["id"]))
            records = [self._record_view(r, data) for r in self._load()["records"].values()]
            return {"species": catalog, "records": records,
                    "defaults": dict(MONSTER_SPAWN_DEFAULTS)}

    def studio_apply(self, payload):
        if self.kind != "monster" or not isinstance(payload, dict):
            raise ValueError("Monster Studio authoring only")
        with self._lock:
            manifest = self._load()
            spawn_id = str(payload.get("spawnId") or "").strip().lower()
            existing = manifest["records"].get(spawn_id)
            if existing and payload.get("expectedUpdatedAtUtc") != existing.get("updatedAtUtc"):
                raise ValueError("Spawn changed elsewhere; refresh in Studio")
            if not existing and payload.get("expectedUpdatedAtUtc"):
                raise ValueError("Spawn was deleted; refresh in Studio")
            if existing and int(payload.get("placeId", -1)) != int(existing["placeId"]):
                raise ValueError("Spawn belongs to another Place")
            if payload.get("action") == "delete":
                if not existing:
                    raise ValueError("Spawn does not exist")
                del manifest["records"][spawn_id]
                self._commit(manifest)
                return {"ok": True, "spawnId": spawn_id}
            if payload.get("action") != "apply":
                raise ValueError("Unknown Studio spawn action")
            if not payload.get("balanceId"):
                raise ValueError("Select a Database monster and level")
            merged = {**MONSTER_SPAWN_DEFAULTS, **(existing or {}), **payload}
            if type(merged["enabled"]) is not bool:
                raise ValueError("Enabled must be a boolean")
            record = self._validate(merged)
            view = self._record_view(record)
            # Only a successful HTTP save projects the record; no reverse bridge
            # callback into the very plugin that is waiting for this request.
            self._commit({**manifest, "records": {**manifest["records"], record["spawnId"]: record}})
            return {"ok": True, "record": view}

    def snapshot(self) -> dict:
        manifest = self._load()
        monster_rows = []
        data = game_balance.load(self.root) if self.kind == "monster" and (self.root / 'config/balance/gameplay.json').is_file() else None
        for row in self.monsters.list():
            ready = self.readiness(str(row["slug"]))
            monster_rows.append({
                "slug": str(row["slug"]),
                "name": str(row.get("name_en") or row["slug"]),
                "nameRu": str(row.get("name_ru") or ""),
                "status": str(row.get("status") or ""),
                "ready": bool(ready["ready"]),
                "reasons": ready["reasons"],
                "animationReady": bool(ready["animationReady"]),
                "missingAnimationSlots": ready["missingAnimationSlots"],
                **(game_balance.monster_spawn_defaults(data, row) if self.kind == "monster" else {}),
            })
        records = [self._record_view(row, data) for _, row in sorted(manifest["records"].items())]
        if self.kind == "npc":
            records.sort(key=lambda row: (row.get("placedAtUtc") or "", row["spawnId"]), reverse=True)
        return {
            "schemaVersion": SCHEMA_VERSION,
            "project": PROJECT,
            "records": records,
            "recordCount": len(records),
            "monsters": monster_rows,
            "defaults": ({"mapKey": "main", "respawnSeconds": 10, "homeRadiusStuds": 16} if self.kind == "npc"
                         else {"mapKey": "main", "respawnSeconds": 10, "homeRadiusStuds": 150, "spawnRadius": 15, "maxAlive": 3}),
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
        behavior = self._spawn_behavior(monster, {**existing, **payload}) if self.kind == "monster" else {}
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
            spawn_radius=(payload.get("spawnRadius", existing.get("spawnRadius", 0)) if self.kind == "monster" else 0),
            max_alive=(payload.get("maxAlive", existing.get("maxAlive", 1)) if self.kind == "monster" else 1),
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
            "enabled": payload.get("enabled", existing.get("enabled", True)) is not False,
        }
        draft["homeRadiusStuds"] = float(payload.get("homeRadiusStuds", existing.get("homeRadiusStuds", 16 if self.kind == "npc" else 150)))
        if self.kind == "npc":
            draft.pop("spawnRadius", None)
            draft.pop("maxAlive", None)
            draft["placedAtUtc"] = utc_now()
        else:
            draft["spawnRadius"] = float(payload.get("spawnRadius", existing.get("spawnRadius", 0)))
            draft["maxAlive"] = int(payload.get("maxAlive", existing.get("maxAlive", 1)))
            draft.update(behavior)
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
                yaw_degrees=record["yawDegrees"],
                spawn_radius=record.get("spawnRadius", 0), max_alive=record.get("maxAlive", 1),
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
            records.append({**self._core(record, npc=self.kind == "npc"), "monsterName": str(monster.get("name_en") or record["monsterSlug"])})
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
                if row.get("balanceId"):
                    continue  # planned species can exist before publication
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
        result = []
        for row in self._load()["records"].values():
            if str(row.get("monsterSlug") or "") == slug:
                result.append(row["spawnId"])
            elif self.kind == "monster" and row.get("balanceId"):
                data = game_balance.load(self.root)
                model = self._model_for_row(self._balance_row(row["balanceId"], data), data)
                if model and model["slug"] == slug:
                    result.append(row["spawnId"])
        return result

    def _write_registry(self, manifest: dict):
        records = [self._core(row, npc=self.kind == "npc") for _, row in sorted(manifest["records"].items())]
        digest = hashlib.sha256(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        payload = {"schemaVersion": 1, "project": PROJECT, "sourceDigest": digest, "records": records}
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        game_balance.atomic(self.registry_path,
            "-- generated. do not edit by hand.\n"
            "local HttpService = game:GetService(\"HttpService\")\n"
            f"local data = HttpService:JSONDecode([==[{encoded}]==])\n"
            "return table.freeze(data)\n",
        )

    def _commit(self, manifest: dict):
        previous = self.manifest_path.read_text(encoding="utf-8")
        game_balance.atomic(self.manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        try:
            self._write_registry(manifest)
        except Exception:
            game_balance.atomic(self.manifest_path, previous)
            raise
