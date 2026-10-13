from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path


DEFAULT_PAYLOAD = {
    "schemaVersion": 1,
    "project": "game1",
    "profiles": [
        {
            "targetType": "humanoid",
            "targetId": "all",
            "displayName": "All Characters & NPCs",
            "rules": [
                {
                    "channel": "run",
                    "label": "Run Speed",
                    "stat": "RunSpeed",
                    "unitsPerPercent": 2.0,
                },
                {
                    "channel": "walk",
                    "label": "Walk Speed",
                    "stat": "RunSpeed",
                    "unitsPerPercent": 4.0,
                },
                {
                    "channel": "combat_idle",
                    "label": "Idle Combat Speed",
                    "stat": "AttackSpeed",
                    "unitsPerPercent": 2.0,
                },
                {
                    "channel": "attack",
                    "label": "Attack Speed",
                    "stat": "AttackSpeed",
                    "unitsPerPercent": 2.0,
                },
            ],
        },
        {
            "targetType": "monster",
            "targetId": "gremlin",
            "displayName": "Gremlin",
            "rules": [
                {
                    "channel": "run",
                    "label": "Run Speed",
                    "stat": "RunSpeed",
                    "unitsPerPercent": 0.6,
                },
            ],
        },
    ],
}


class AnimationSpeedScalingStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.manifest_path = self.root / "assets/manifests/animation-speed-scaling.json"
        self.registry_path = self.root / "src/shared/animation/AnimationSpeedScalingRegistry.luau"
        self._ensure()

    def _ensure(self):
        if not self.manifest_path.is_file():
            payload = deepcopy(DEFAULT_PAYLOAD)
            self._write(payload)
        else:
            payload = self._read()
            if self._migrate_shared_humanoid_profile(payload):
                self._write(payload)
            else:
                self._validate(payload)
                self._write_registry(payload)

    @staticmethod
    def _migrate_shared_humanoid_profile(payload: dict) -> bool:
        """One-time non-destructive migration from archetype-specific rules.

        Preserve the full legacy profiles separately, including any other
        character overrides, but expose and publish ONE authoritative rule set
        for all player Characters and NPCs. Monster rules are independent.
        """
        profiles = payload.get("profiles") or []
        if any(str(p.get("targetType") or "").lower() == "humanoid" for p in profiles):
            return False
        source = next((p for p in profiles if p.get("targetType") == "character"
                       and p.get("targetId") == "human_female"), None)
        if source is None:
            source = next((p for p in profiles if p.get("targetType") == "character"), None)
        defaults = deepcopy(DEFAULT_PAYLOAD["profiles"][0])
        if source:
            authored = {r["channel"]: r for r in source.get("rules", [])}
            defaults["rules"] = [deepcopy(authored.get(r["channel"], r)) for r in defaults["rules"]]
        former = [p for p in profiles if p.get("targetType") == "character"]
        if former:
            payload.setdefault("legacyProfiles", []).extend(deepcopy(former))
        payload["profiles"] = [defaults] + [p for p in profiles if p.get("targetType") != "character"]
        return True

    def _read(self) -> dict:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _validate(self, payload: dict):
        self._validate_custom(payload)
        if int(payload.get("schemaVersion") or 0) != 1:
            raise ValueError("unsupported animation speed scaling schema")
        profiles = payload.get("profiles")
        if not isinstance(profiles, list):
            raise ValueError("animation speed scaling profiles must be a list")
        seen = set()
        for profile in profiles:
            target_type = str(profile.get("targetType") or "").strip().lower()
            target_id = str(profile.get("targetId") or "").strip().lower()
            if target_type not in {"humanoid", "monster"} or not target_id:
                raise ValueError("invalid animation speed scaling target")
            if target_type == "humanoid" and target_id != "all":
                raise ValueError("invalid animation speed scaling target")
            rules = profile.get("rules")
            if not isinstance(rules, list) or not rules:
                raise ValueError(f"animation speed scaling target {target_id} has no rules")
            for rule in rules:
                channel = str(rule.get("channel") or "").strip().lower()
                stat = str(rule.get("stat") or "").strip()
                key = (target_type, target_id, channel)
                if not channel or not stat or key in seen:
                    raise ValueError("invalid or duplicate animation speed scaling rule")
                seen.add(key)
                units = float(rule.get("unitsPerPercent") or 0)
                if not (0.001 <= units <= 100000):
                    raise ValueError("units per 1% must be between 0.001 and 100000")

    @staticmethod
    def _lua_string(value: str) -> str:
        return json.dumps(str(value), ensure_ascii=False)

    @staticmethod
    def _lua_number(value: float) -> str:
        text = format(float(value), ".12g")
        return text if "." in text else text + ".0"

    def catalog(self) -> list[dict]:
        """Published clips, indexed by permanent Roblox Animation Asset ID.

        UI names are informational; user overrides do not depend on filenames,
        profile names or the currently selected NPC/Character in Asset Manager.
        """
        found: dict[str, dict] = {}
        for kind, filename in (
            ("character", "character-animations.json"),
            ("monster", "monster-animations.json"),
            ("npc", "npc-animations.json"),
        ):
            path = self.root / "assets/manifests" / filename
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            bindings: dict[str, list[dict]] = {}
            for binding in data.get("bindings", []):
                bindings.setdefault(str(binding.get("clipId") or binding.get("clip_id") or ""), []).append(binding)
            for clip in data.get("clips", []):
                asset_id = str(clip.get("assetId") or clip.get("asset_id") or "")
                if not asset_id.isdecimal() or int(asset_id) == 0:
                    continue
                clip_id = str(clip.get("id") or "")
                subject = str(clip.get("characterId") or clip.get("monster_slug") or kind)
                for binding in bindings.get(clip_id, []):
                    slot = str(binding.get("slot") or "idle").lower()
                    channel = "idle" if slot == "idle_special" else slot
                    row = {
                        "assetId": asset_id,
                        "clipId": clip_id,
                        "name": str(clip.get("name") or clip_id),
                        "kind": kind,
                        "subject": subject,
                        "channel": channel,
                        "stat": "RunSpeed" if channel in {"walk", "run"} else "AttackSpeed",
                    }
                    found.setdefault(asset_id, row)
        return sorted(found.values(), key=lambda r: (r["kind"], r["subject"], r["name"]))

    def _validate_custom(self, payload: dict):
        rows = payload.get("customScaling", [])
        if not isinstance(rows, list):
            raise ValueError("custom scaling must be a list")
        seen = set()
        for row in rows:
            aid = str(row.get("assetId") or "")
            units = float(row.get("unitsPerPercent") or 0)
            if not aid.isdecimal() or int(aid) == 0 or aid in seen:
                raise ValueError("invalid or duplicate custom animation asset id")
            if not math.isfinite(units) or not 0.001 <= units <= 1000:
                raise ValueError("custom units must be 0.001..1000")
            if row.get("stat") not in {"AttackSpeed", "RunSpeed"}:
                raise ValueError("unsupported custom gameplay stat")
            seen.add(aid)

    def save_custom(self, request: dict) -> dict:
        asset_id = str(request.get("assetId") or "").strip()
        catalog = {r["assetId"]: r for r in self.catalog()}
        if asset_id not in catalog:
            raise ValueError("select a published animation from the catalog")
        payload = self._read()
        rows = payload.setdefault("customScaling", [])
        rows[:] = [r for r in rows if r["assetId"] != asset_id]
        if not bool(request.get("delete")):
            stat = str(request.get("stat") or catalog[asset_id]["stat"])
            units = float(request.get("unitsPerPercent") or 0)
            rows.append({"assetId": asset_id, "stat": stat, "unitsPerPercent": units})
        rows.sort(key=lambda r: r["assetId"])
        self._write(payload)
        return self.snapshot()

    def _write_registry(self, payload: dict):
        grouped: dict[str, dict[str, dict]] = {"humanoid": {}, "monster": {}}
        for profile in payload.get("profiles") or []:
            target_type = str(profile["targetType"]).lower()
            target_id = str(profile["targetId"]).lower()
            rules = {}
            for rule in profile.get("rules") or []:
                rules[str(rule["channel"]).lower()] = {
                    "stat": str(rule["stat"]),
                    "unitsPerPercent": float(rule["unitsPerPercent"]),
                }
            grouped[target_type][target_id] = rules

        lines = [
            "-- generated by Asset Manager. do not edit by hand.",
            "return table.freeze({",
            "\tschemaVersion = 1,",
            '\tproject = "game1",',
            "\tprofiles = table.freeze({",
        ]
        for target_type in ("humanoid", "monster"):
            lines.append(f"\t\t[{self._lua_string(target_type)}] = table.freeze({{")
            for target_id in sorted(grouped[target_type]):
                lines.append(f"\t\t\t[{self._lua_string(target_id)}] = table.freeze({{")
                for channel in sorted(grouped[target_type][target_id]):
                    rule = grouped[target_type][target_id][channel]
                    lines += [
                        f"\t\t\t\t[{self._lua_string(channel)}] = table.freeze({{",
                        f"\t\t\t\t\tstat = {self._lua_string(rule['stat'])},",
                        f"\t\t\t\t\tunitsPerPercent = {self._lua_number(rule['unitsPerPercent'])},",
                        "\t\t\t\t}),",
                    ]
                lines.append("\t\t\t}),")
            lines.append("\t\t}),")
        lines.append("\t}),")
        lines.append("\tcustom = table.freeze({")
        for row in payload.get("customScaling", []):
            aid = row["assetId"]
            lines += [
                f"\t\t[{self._lua_string(aid)}] = table.freeze({{",
                f"\t\t\tstat = {self._lua_string(row['stat'])},",
                f"\t\t\tunitsPerPercent = {self._lua_number(row['unitsPerPercent'])},",
                "\t\t}),",
            ]
        lines.append("\t}),")
        lines.append("\tcatalog = table.freeze({")
        for row in self.catalog():
            lines += [
                f"\t\t[{self._lua_string(row['assetId'])}] = table.freeze({{",
                f"\t\t\tlabel = {self._lua_string(row['kind'] + ' / ' + row['subject'] + ' / ' + row['name'])},",
                f"\t\t\tchannel = {self._lua_string(row['channel'])},",
                "\t\t}),",
            ]
        lines += ["\t}),", "})", ""]
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        rendered = "\n".join(lines)
        if not self.registry_path.is_file() or self.registry_path.read_text(encoding="utf-8") != rendered:
            self.registry_path.write_text(rendered, encoding="utf-8")

    def _write(self, payload: dict):
        self._validate(payload)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._write_registry(payload)

    def snapshot(self) -> dict:
        payload = self._read()
        self._validate(payload)
        self._write_registry(payload)
        payload["catalog"] = self.catalog()
        return payload

    def update(self, request: dict) -> dict:
        target_type = str(request.get("targetType") or "").strip().lower()
        target_id = str(request.get("targetId") or "").strip().lower()
        channel = str(request.get("channel") or "").strip().lower()
        units = float(request.get("unitsPerPercent") or 0)
        if not (0.001 <= units <= 100000):
            raise ValueError("units per 1% must be between 0.001 and 100000")

        payload = self._read()
        found = False
        for profile in payload.get("profiles") or []:
            if str(profile.get("targetType") or "").lower() != target_type:
                continue
            if str(profile.get("targetId") or "").lower() != target_id:
                continue
            for rule in profile.get("rules") or []:
                if str(rule.get("channel") or "").lower() == channel:
                    rule["unitsPerPercent"] = units
                    found = True
                    break
        if not found:
            raise ValueError("unknown animation speed scaling rule")
        self._write(payload)
        return self.snapshot()
