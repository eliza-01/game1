from __future__ import annotations

import json
import re
import time
import threading
from services.camera_settings import DEFAULT_CAMERA, normalize_camera
from copy import deepcopy
from pathlib import Path


# M322: one versioned visual contract, independently authored per input class.
# Numeric limits are validated here before generation for the Roblox runtime.
HEALTH_UI_DEFAULTS = {
    "desktop": {
        "screen": {"enabled": True, "width": 320, "height": 20, "border": 2, "textSize": 15, "top": 22},
        "self": {"enabled": True, "width": 148, "height": 12, "border": 2, "nameSize": 13, "levelSize": 15, "offsetStuds": 1.7},
        "monster": {"enabled": True, "width": 182, "height": 18, "border": 2.5, "nameSize": 20, "levelSize": 22, "offsetStuds": 2.6},
        "colors": {"green": "#45DB8B", "yellow": "#FFC64B", "red": "#FF5B5D"},
    },
    "mobile": {
        "screen": {"enabled": True, "width": 214, "height": 17, "border": 2, "textSize": 13, "top": 35},
        "self": {"enabled": True, "width": 126, "height": 11, "border": 1.7, "nameSize": 12, "levelSize": 13, "offsetStuds": 1.8},
        "monster": {"enabled": True, "width": 150, "height": 15, "border": 2, "nameSize": 17, "levelSize": 19, "offsetStuds": 2.8},
        "colors": {"green": "#45DB8B", "yellow": "#FFC64B", "red": "#FF5B5D"},
    },
}
HEALTH_BOUNDS = {
    "width": (60, 560), "height": (6, 60), "border": (0, 8),
    "textSize": (8, 36), "nameSize": (8, 40), "levelSize": (8, 40),
    "offsetStuds": (0, 12), "top": (0, 160),
}


def normalize_health_profile(profile, base=None):
    """Canonical full profile. Reject unrecognized fields and non-finite numbers."""
    import math
    if not isinstance(profile, dict):
        raise ValueError('health UI profile must be an object')
    defaults = base or HEALTH_UI_DEFAULTS['desktop']
    result = deepcopy(defaults)
    if set(profile) - set(defaults):
        raise ValueError('unknown health UI section')
    for section, fields in profile.items():
        if not isinstance(fields, dict) or set(fields) - set(defaults[section]):
            raise ValueError(f'invalid health UI {section} fields')
        for key, value in fields.items():
            if key == 'enabled':
                if type(value) is not bool:
                    raise ValueError('health UI enabled must be boolean')
            elif section == 'colors':
                if not isinstance(value, str) or not re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
                    raise ValueError(f'{key} must be an RGB hex color')
                value = value.upper()
            else:
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError(f'{section}.{key} must be a finite number')
                low, high = HEALTH_BOUNDS[key]
                if not low <= value <= high:
                    raise ValueError(f'{section}.{key} must be {low}..{high}')
            result[section][key] = value
    return result


def normalize_health_ui(change, base=None):
    if not isinstance(change, dict) or set(change) - {'desktop', 'mobile'}:
        raise ValueError('healthUi expects desktop/mobile profiles')
    base = base or HEALTH_UI_DEFAULTS
    return {device: normalize_health_profile(change.get(device, {}), base[device])
            for device in ('desktop', 'mobile')}


def normalize_debug_ui(change, base=None):
    if not isinstance(change, dict) or set(change) - {'desktop', 'mobile'}:
        raise ValueError('debugUi expects desktop/mobile profiles')
    result = deepcopy(base or DEFAULT_PAYLOAD['debugUi'])
    for device, settings in change.items():
        if not isinstance(settings, dict) or set(settings) != {'showPublishedControls'} or type(settings['showPublishedControls']) is not bool:
            raise ValueError('debugUi.showPublishedControls must be boolean')
        result[device] = deepcopy(settings)
    return result


def lua_literal(value, indent=1):
    """Only validated options are serialized; never execute user-provided Lua."""
    pad = '\t' * indent
    if isinstance(value, dict):
        return 'table.freeze({\n' + ''.join(
            f'{pad}\t{key} = {lua_literal(item, indent + 1)},\n'
            for key, item in value.items()) + pad + '})'
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return f'{value:.12g}'
    return json.dumps(value)


DEFAULT_PAYLOAD = {
    "schemaVersion": 1,
    "project": "game1",
    "combat": {
        "stateDurationSeconds": 6.0,
    },
    "camera": DEFAULT_CAMERA.copy(),
    "healthUi": deepcopy(HEALTH_UI_DEFAULTS),
    "debugUi": {"desktop": {"showPublishedControls": False}, "mobile": {"showPublishedControls": False}},
    "cameraPresets": [],
    "activeCameraPreset": "",
    "characterAnimations": {
        "deathPlaybackPercent": 100.0,
        "revivePlaybackPercent": 100.0,
    },
}


class OptionsStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.manifest_path = self.root / "assets/manifests/options.json"
        self.registry_path = self.root / "src/shared/GameOptionsRegistry.luau"
        self._debug_lock = threading.Lock()
        self._camera_draft = None  # transient Studio debug preview; never auto-saved
        self._camera_draft_at = 0
        self._health_draft = None
        self._health_draft_at = 0
        self._ensure()

    def _read(self) -> dict:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _validate(self, payload: dict):
        if int(payload.get("schemaVersion") or 0) != 1:
            raise ValueError("unsupported options schema")
        combat = payload.get("combat") or {}
        duration = float(combat.get("stateDurationSeconds") or 0)
        if not (0 <= duration <= 3600):
            raise ValueError("combat state duration must be 0..3600 seconds")
        normalize_camera(payload.get("camera") or {})
        presets = payload.get("cameraPresets") or []
        if not isinstance(presets, list) or len(presets) > 32:
            raise ValueError('camera presets must be a list of up to 32 presets')
        names = set()
        for row in presets:
            if not isinstance(row, dict) or not re.fullmatch(r'[\w .-]{1,40}', str(row.get('name') or '')):
                raise ValueError('invalid camera preset name')
            if row['name'] in names:
                raise ValueError('duplicate camera preset name')
            names.add(row['name'])
            normalize_camera(row.get('settings') or {})
        normalize_health_ui(payload.get('healthUi', HEALTH_UI_DEFAULTS))
        normalize_debug_ui(payload.get('debugUi', DEFAULT_PAYLOAD['debugUi']))
        animations = payload.get("characterAnimations") or {}
        for key in ("deathPlaybackPercent", "revivePlaybackPercent"):
            percent = float(animations.get(key) or 0)
            if not (1 <= percent <= 400):
                raise ValueError(f"{key} must be 1..400 percent")

    def _write_registry(self, payload: dict):
        combat = payload["combat"]
        animations = payload["characterAnimations"]
        camera = normalize_camera(payload.get("camera") or {})
        lines = [
            "-- generated by Asset Manager. do not edit by hand.",
            "return table.freeze({",
            "\tschemaVersion = 1,",
            '\tproject = "game1",',
            "\tcombat = table.freeze({",
            f"\t\tstateDurationSeconds = {float(combat['stateDurationSeconds']):.12g},",
            "\t}),",
            "\tcamera = table.freeze({",
            *(f"\t\t{key} = {value:.12g}," for key,value in camera.items()),
            "\t}),",
            "\thealthUi = " + lua_literal(normalize_health_ui(payload.get('healthUi', HEALTH_UI_DEFAULTS))) + ",",
            "\tdebugUi = " + lua_literal(normalize_debug_ui(payload.get('debugUi', DEFAULT_PAYLOAD['debugUi']))) + ",",
            "\tcharacterAnimations = table.freeze({",
            f"\t\tdeathPlaybackPercent = {float(animations['deathPlaybackPercent']):.12g},",
            f"\t\trevivePlaybackPercent = {float(animations['revivePlaybackPercent']):.12g},",
            "\t}),",
            "})",
            "",
        ]
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text("\n".join(lines), encoding="utf-8")

    def _write(self, payload: dict):
        self._validate(payload)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._write_registry(payload)

    def _ensure(self):
        if not self.manifest_path.is_file():
            self._write(deepcopy(DEFAULT_PAYLOAD))
            return
        payload = self._read()
        changed = False
        for group, defaults in (("combat", DEFAULT_PAYLOAD["combat"]), ("characterAnimations", DEFAULT_PAYLOAD["characterAnimations"]), ("camera", DEFAULT_CAMERA)):
            if not isinstance(payload.get(group), dict):
                payload[group] = {}
                changed = True
            for key, value in defaults.items():
                if key not in payload[group]:
                    payload[group][key] = value
                    changed = True
        for field in ('healthUi', 'debugUi'):
            if field not in payload:
                payload[field] = deepcopy(DEFAULT_PAYLOAD[field])
                changed = True
        for field in ('cameraPresets', 'activeCameraPreset'):
            if field not in payload:
                payload[field] = deepcopy(DEFAULT_PAYLOAD[field])
                changed = True
        if changed:
            payload["schemaVersion"] = 1
            payload["project"] = "game1"
            self._write(payload)
        else:
            self._validate(payload)
            self._write_registry(payload)

    def snapshot(self) -> dict:
        payload = self._read()
        self._validate(payload)
        return payload

    def preview_camera(self, request: dict) -> dict:
        # Called ONLY from the authenticated local host agent through the
        # Studio plugin. Edits are transient until Save in Asset Manager.
        camera = normalize_camera(request)
        with self._debug_lock:
            self._camera_draft = camera
            self._camera_draft_at = time.time()
        return {'cameraDebugDraft':camera, 'cameraDebugDraftAt':self._camera_draft_at,
                'saved':False}

    def preview_health_ui(self, request: dict) -> dict:
        if not isinstance(request, dict) or set(request) != {'device', 'settings'}:
            raise ValueError('health UI draft requires device + settings')
        device = request['device']
        if device not in ('desktop', 'mobile'):
            raise ValueError('unknown health UI device')
        profile = normalize_health_profile(request['settings'], HEALTH_UI_DEFAULTS[device])
        with self._debug_lock:
            self._health_draft = {'device': device, 'settings': profile}
            self._health_draft_at = time.time()
        return {'saved': False, 'healthUiDebugDraftAt': self._health_draft_at}

    def snapshot_with_debug(self) -> dict:
        payload = self.snapshot()
        with self._debug_lock:
            payload['cameraDebugDraft'] = deepcopy(self._camera_draft)
            payload['cameraDebugDraftAt'] = self._camera_draft_at
            payload['healthUiDebugDraft'] = deepcopy(self._health_draft)
            payload['healthUiDebugDraftAt'] = self._health_draft_at
        return payload

    def update(self, request: dict) -> dict:
        payload = self._read()
        combat = request.get("combat")
        if isinstance(combat, dict) and "stateDurationSeconds" in combat:
            payload.setdefault("combat", {})["stateDurationSeconds"] = float(combat["stateDurationSeconds"])
        animations = request.get("characterAnimations")
        if isinstance(animations, dict):
            for key in ("deathPlaybackPercent", "revivePlaybackPercent"):
                if key in animations:
                    payload.setdefault("characterAnimations", {})[key] = float(animations[key])
        if 'healthUi' in request:
            payload['healthUi'] = normalize_health_ui(request['healthUi'],
                                                       payload.get('healthUi', HEALTH_UI_DEFAULTS))
        if 'debugUi' in request:
            payload['debugUi'] = normalize_debug_ui(request['debugUi'],
                                                    payload.get('debugUi', DEFAULT_PAYLOAD['debugUi']))
        if 'camera' in request:
            payload['camera'] = normalize_camera(request['camera'],base=payload.get('camera'))
            payload['activeCameraPreset'] = ''
        preset_action = request.get('cameraPresetAction')
        if preset_action:
            name = str(request.get('cameraPresetName') or '').strip()
            if not re.fullmatch(r'[\w .-]{1,40}',name):
                raise ValueError('camera preset name must be 1..40 safe characters')
            presets = payload.setdefault('cameraPresets',[])
            found = next((row for row in presets if row['name'] == name),None)
            if preset_action == 'save':
                if not found and len(presets) >= 32:
                    raise ValueError('camera preset limit 32 reached')
                if found: found['settings'] = deepcopy(payload['camera'])
                else: presets.append({'name':name,'settings':deepcopy(payload['camera'])})
                payload['activeCameraPreset'] = name
            elif preset_action == 'apply':
                if not found: raise ValueError('camera preset not found')
                payload['camera'] = normalize_camera(found['settings'])
                payload['activeCameraPreset'] = name
            elif preset_action == 'delete':
                if not found: raise ValueError('camera preset not found')
                presets.remove(found)
                if payload.get('activeCameraPreset') == name: payload['activeCameraPreset'] = ''
            else:
                raise ValueError('unknown camera preset action')
        self._write(payload)
        return payload
