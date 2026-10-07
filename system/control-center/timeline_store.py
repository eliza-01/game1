from __future__ import annotations

from pathlib import Path
import json
import time
import uuid

PROJECT = "game1"
SCHEMA_VERSION = 2

EVENT_CATALOGS = {
    "characters": [
        {"name": "HitStart", "label": "hit start"},
        {"name": "HitEnd", "label": "hit end"},
    ],
    "monsters": [
        {"name": "Hit", "label": "hit"},
    ],
}
ALL_EVENT_NAMES = ("HitStart", "HitEnd", "Hit")


def event_catalog_for_subject(subject_type: str) -> list[dict]:
    return list(EVENT_CATALOGS.get(str(subject_type or ""), []))


def event_names_for_subject(subject_type: str) -> set[str]:
    return {str(row["name"]) for row in event_catalog_for_subject(subject_type)}


class TimelineStore:
    def __init__(self, root: Path, characters, animations, monsters, monster_animations):
        self.root = root.resolve()
        self.characters = characters
        self.animations = animations
        self.monsters = monsters
        self.monster_animations = monster_animations
        self.manifest_path = self.root / "assets/manifests/attack-timelines.json"
        self.runtime_path = self.root / "src/shared/combat/AttackTimelineData.luau"
        self.sessions: dict[str, dict] = {}
        self._ensure_manifest()
        self.export_runtime()

    def _ensure_manifest(self) -> None:
        if self.manifest_path.is_file():
            return
        self._write_manifest({
            "schemaVersion": SCHEMA_VERSION,
            "project": PROJECT,
            "timelines": [
                {
                    "clipId": "human_female__weapon__1hs__attack__01",
                    "duration": 1.866666674,
                    "events": {
                        "HitStart": {"normalizedTime": 0.40},
                        "HitEnd": {"normalizedTime": 0.50},
                    },
                },
                {
                    "clipId": "human_female__weapon__1hs__attack__02",
                    "duration": 1.866666674,
                    "events": {
                        "HitStart": {"normalizedTime": 0.40},
                        "HitEnd": {"normalizedTime": 0.50},
                    },
                },
                {
                    "clipId": "human_female__weapon__1hs__attack__03",
                    "duration": 1.866666674,
                    "events": {
                        "HitStart": {"normalizedTime": 0.40},
                        "HitEnd": {"normalizedTime": 0.50},
                    },
                },
                {
                    "clipId": "monster__gremlin__attack__01",
                    "duration": 1.799999952,
                    "events": {"Hit": {"normalizedTime": 0.50}},
                },
            ],
        })

    def _load(self) -> dict:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"attack timeline manifest is invalid: {exc}") from exc
        if int(data.get("schemaVersion") or 0) != SCHEMA_VERSION or data.get("project") != PROJECT:
            raise ValueError("attack timeline manifest identity is invalid")
        if not isinstance(data.get("timelines"), list):
            raise ValueError("attack timeline manifest timelines must be a list")
        return data

    def _write_manifest(self, data: dict) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _lua_string(value: str) -> str:
        return json.dumps(str(value), ensure_ascii=False)

    @staticmethod
    def _lua_number(value: float) -> str:
        text = f"{float(value):.9f}".rstrip("0").rstrip(".")
        return text if text else "0"

    def export_runtime(self) -> None:
        data = self._load()
        lines = [
            "-- generated from assets/manifests/attack-timelines.json; do not edit by hand.",
            "local BY_CLIP = {",
        ]
        for row in sorted(data.get("timelines") or [], key=lambda item: str(item.get("clipId") or "")):
            clip_id = str(row.get("clipId") or "").strip()
            duration = float(row.get("duration") or 0)
            if not clip_id or duration <= 0:
                continue
            lines.append(f"    [{self._lua_string(clip_id)}] = table.freeze({{")
            lines.append(f"        duration = {self._lua_number(duration)},")
            lines.append("        events = table.freeze({")
            events = row.get("events") if isinstance(row.get("events"), dict) else {}
            for event_name in ALL_EVENT_NAMES:
                event = events.get(event_name)
                if not isinstance(event, dict):
                    continue
                normalized = max(0.0, min(1.0, float(event.get("normalizedTime") or 0)))
                lines.append(
                    f"            {event_name} = table.freeze({{ normalizedTime = {self._lua_number(normalized)} }}),"
                )
            lines.extend(["        }),", "    }),"])
        lines.extend(["}", "", "return table.freeze(BY_CLIP)", ""])
        self.runtime_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_path.write_text("\n".join(lines), encoding="utf-8")

    def _timeline_map(self) -> dict[str, dict]:
        return {str(row.get("clipId") or ""): row for row in self._load().get("timelines") or []}

    def _attack_rows(self) -> list[dict]:
        timeline_map = self._timeline_map()
        rows: list[dict] = []
        for character in self.characters.list():
            character_id = str(character.get("id") or "")
            for clip in self.animations.list_for_character(character_id):
                if str(clip.get("slot") or "") != "attack":
                    continue
                clip_id = str(clip.get("clip_id") or "")
                timeline = timeline_map.get(clip_id) or {}
                rows.append({
                    "subjectType": "characters",
                    "subjectId": character_id,
                    "subjectName": str(character.get("display_name") or character_id),
                    "modelAssetId": str(character.get("model_asset_id") or ""),
                    "clipId": clip_id,
                    "clipName": str(clip.get("name") or clip_id),
                    "animationAssetId": str(clip.get("asset_id") or ""),
                    "weaponSet": str(clip.get("weapon_set") or ""),
                    "variant": int(clip.get("variant") or 0),
                    "duration": float(timeline.get("duration") or 0),
                    "events": dict(timeline.get("events") or {}),
                    "configured": bool(timeline),
                })
        for monster in self.monsters.list():
            slug = str(monster.get("slug") or "")
            for clip in self.monster_animations.list_for_monster(slug):
                if str(clip.get("slot") or "") != "attack":
                    continue
                clip_id = str(clip.get("clip_id") or clip.get("id") or "")
                timeline = timeline_map.get(clip_id) or {}
                rows.append({
                    "subjectType": "monsters",
                    "subjectId": slug,
                    "subjectName": str(monster.get("name_en") or slug),
                    "modelAssetId": str(monster.get("model_asset_id") or ""),
                    "clipId": clip_id,
                    "clipName": str(clip.get("name") or clip_id),
                    "animationAssetId": str(clip.get("asset_id") or ""),
                    "weaponSet": "",
                    "variant": int(clip.get("variant") or 0),
                    "duration": float(timeline.get("duration") or 0),
                    "events": dict(timeline.get("events") or {}),
                    "configured": bool(timeline),
                })
        rows.sort(key=lambda row: (row["subjectType"], row["subjectName"].casefold(), row["clipName"].casefold()))
        return rows

    def snapshot(self) -> dict:
        rows = self._attack_rows()
        subjects = {"characters": [], "monsters": []}
        seen: set[tuple[str, str]] = set()
        for row in rows:
            key = (row["subjectType"], row["subjectId"])
            if key in seen:
                continue
            seen.add(key)
            subjects[row["subjectType"]].append({"id": row["subjectId"], "name": row["subjectName"]})
        return {
            "schemaVersion": SCHEMA_VERSION,
            "project": PROJECT,
            "eventCatalogs": EVENT_CATALOGS,
            "subjects": subjects,
            "items": rows,
        }

    def _find_attack(self, clip_id: str) -> dict:
        clip_id = str(clip_id or "").strip()
        row = next((item for item in self._attack_rows() if item["clipId"] == clip_id), None)
        if not row:
            raise ValueError(f"unknown registered attack animation: {clip_id}")
        if not str(row.get("modelAssetId") or "").isdigit():
            raise ValueError("publish the selected character/monster model before opening the timeline editor")
        if not str(row.get("animationAssetId") or "").isdigit():
            raise ValueError("publish the selected attack animation before opening the timeline editor")
        return row

    @staticmethod
    def _validate_events(subject_type: str, raw_events: dict) -> dict:
        allowed = event_names_for_subject(subject_type)
        events = {}
        for event_name, raw in raw_events.items():
            if event_name not in allowed or not isinstance(raw, dict):
                continue
            events[event_name] = {
                "normalizedTime": max(0.0, min(1.0, float(raw.get("normalizedTime") or 0)))
            }
        if subject_type == "characters":
            if "HitStart" not in events or "HitEnd" not in events:
                raise ValueError("character attack timeline requires HitStart and HitEnd")
            if events["HitStart"]["normalizedTime"] > events["HitEnd"]["normalizedTime"]:
                raise ValueError("HitStart cannot be after HitEnd")
        elif subject_type == "monsters":
            if "Hit" not in events:
                raise ValueError("monster attack timeline requires Hit")
        else:
            raise ValueError(f"unsupported timeline subject type: {subject_type}")
        return events

    def event_catalog_for_subject(self, subject_type: str) -> list[dict]:
        return event_catalog_for_subject(subject_type)

    def begin_editor_session(self, clip_id: str) -> dict:
        row = self._find_attack(clip_id)
        session_id = uuid.uuid4().hex
        session = {
            "sessionId": session_id,
            "clipId": row["clipId"],
            "subjectType": row["subjectType"],
            "subjectId": row["subjectId"],
            "subjectName": row["subjectName"],
            "clipName": row["clipName"],
            "modelAssetId": row["modelAssetId"],
            "animationAssetId": row["animationAssetId"],
            "duration": float(row.get("duration") or 0),
            "events": json.loads(json.dumps(row.get("events") or {})),
            "revision": 0,
            "studioReady": False,
            "updatedAt": time.time(),
        }
        self.sessions[session_id] = session
        return json.loads(json.dumps(session))

    def editor_state(self, session_id: str) -> dict:
        session = self.sessions.get(str(session_id or ""))
        if not session:
            raise ValueError("timeline editor session expired or was not found")
        return json.loads(json.dumps(session))

    def update_editor_state(self, payload: dict) -> dict:
        session = self.sessions.get(str(payload.get("sessionId") or ""))
        if not session:
            raise ValueError("timeline editor session expired or was not found")
        duration = float(payload.get("duration") or session.get("duration") or 0)
        if duration > 0:
            session["duration"] = duration
        action = str(payload.get("action") or "ready")
        if action == "ready":
            session["studioReady"] = True
        elif action == "set-event":
            event_name = str(payload.get("eventName") or "")
            if event_name not in event_names_for_subject(str(session.get("subjectType") or "")):
                raise ValueError(f"unsupported event for this attack type: {event_name}")
            session.setdefault("events", {})[event_name] = {
                "normalizedTime": max(0.0, min(1.0, float(payload.get("normalizedTime") or 0)))
            }
            session["studioReady"] = True
        else:
            raise ValueError(f"unsupported timeline editor action: {action}")
        session["revision"] = int(session.get("revision") or 0) + 1
        session["updatedAt"] = time.time()
        return self.editor_state(session["sessionId"])

    def save(self, payload: dict) -> dict:
        clip_id = str(payload.get("clipId") or "").strip()
        attack = self._find_attack(clip_id)
        duration = float(payload.get("duration") or 0)
        if duration <= 0:
            raise ValueError("timeline duration must be greater than zero")
        raw_events = payload.get("events")
        if not isinstance(raw_events, dict):
            raise ValueError("timeline events are required")
        events = self._validate_events(str(attack.get("subjectType") or ""), raw_events)

        data = self._load()
        row = {"clipId": clip_id, "duration": duration, "events": events}
        for index, current in enumerate(data["timelines"]):
            if str(current.get("clipId") or "") == clip_id:
                data["timelines"][index] = row
                break
        else:
            data["timelines"].append(row)
        data["timelines"].sort(key=lambda item: str(item.get("clipId") or ""))
        self._write_manifest(data)
        self.export_runtime()
        return self.snapshot()
