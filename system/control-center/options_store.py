from __future__ import annotations

import json
import re
import time
import threading
from datetime import datetime, timezone
from services.camera_settings import DEFAULT_CAMERA, normalize_camera
from services.flora_effect_settings import DEFAULTS as FLORA_DEFAULTS, normalize_flora, validate_residents
from services.character_creation_settings import DEFAULTS as CREATION_DEFAULTS, normalize_character_creation
from copy import deepcopy
from pathlib import Path


# M322: one versioned visual contract, independently authored per input class.
# Numeric limits are validated here before generation for the Roblox runtime.
HEALTH_UI_DEFAULTS = {
    "desktop": {
        "screen": {"enabled": True, "width": 320, "height": 20, "border": 2, "textSize": 15, "top": 22},
        "self": {"enabled": True, "width": 148, "height": 12, "border": 2, "nameSize": 13, "levelSize": 15, "offsetStuds": 1.7},
        "monster": {"enabled": True, "width": 182, "height": 18, "border": 2.5, "nameSize": 20, "levelSize": 22, "offsetStuds": 2.6, "maxDistanceStuds": 100},
        "colors": {"green": "#45DB8B", "yellow": "#FFC64B", "red": "#FF5B5D"},
    },
    "mobile": {
        "screen": {"enabled": True, "width": 214, "height": 17, "border": 2, "textSize": 13, "top": 35},
        "self": {"enabled": True, "width": 126, "height": 11, "border": 1.7, "nameSize": 12, "levelSize": 13, "offsetStuds": 1.8},
        "monster": {"enabled": True, "width": 150, "height": 15, "border": 2, "nameSize": 17, "levelSize": 19, "offsetStuds": 2.8, "maxDistanceStuds": 100},
        "colors": {"green": "#45DB8B", "yellow": "#FFC64B", "red": "#FF5B5D"},
    },
}
HEALTH_BOUNDS = {
    "width": (60, 560), "height": (6, 60), "border": (0, 8),
    "textSize": (8, 36), "nameSize": (8, 40), "levelSize": (8, 40),
    "offsetStuds": (0, 12), "top": (0, 160), "maxDistanceStuds": (20, 800),
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


# M443: one generated visual contract for interactions, status, feedback, and spends.
# Pixel coordinates are device-relative offsets from the authored anchor.
UI_PROFILE_DEFAULTS = {
    "desktop": {
        "interaction": {"offsetXPx": 0, "offsetYPx": 0, "widthPx": 272, "fontPx": 14},
        "status": {"offsetXPx": 0, "offsetYPx": 0, "titleFontPx": 13, "labelFontPx": 12, "timerFontPx": 11},
        "notification": {"offsetXPx": 0, "offsetYPx": 0, "fontPx": 13, "paddingPx": 5, "durationSeconds": 2.7},
        "resource": {"offsetXPx": 0, "offsetYPx": 0, "fontPx": 18, "paddingPx": 5, "risePx": 34, "durationSeconds": 0.9},
    },
    "mobile": {
        "interaction": {"offsetXPx": 0, "offsetYPx": 0, "widthPx": 272, "fontPx": 14},
        "status": {"offsetXPx": 0, "offsetYPx": 0, "titleFontPx": 13, "labelFontPx": 12, "timerFontPx": 11},
        "notification": {"offsetXPx": 0, "offsetYPx": 0, "fontPx": 13, "paddingPx": 5, "durationSeconds": 2.7},
        "resource": {"offsetXPx": 0, "offsetYPx": 0, "fontPx": 18, "paddingPx": 5, "risePx": 34, "durationSeconds": 0.9},
    },
}
UI_FIELD_BOUNDS = {
    'offsetXPx': (-500, 500), 'offsetYPx': (-500, 500),
    'widthPx': (180, 450), 'fontPx': (10, 36),
    'titleFontPx': (10, 36), 'labelFontPx': (10, 36),
    'timerFontPx': (9, 36), 'paddingPx': (0, 24), 'risePx': (0, 200),
    'durationSeconds': (0.2, 15),
}


def normalize_ui_profile(change, base):
    import math
    if not isinstance(change, dict) or set(change) - set(base):
        raise ValueError('ui profile sections invalid')
    result = deepcopy(base)
    for group, fields in change.items():
        if not isinstance(fields, dict) or set(fields) - set(base[group]):
            raise ValueError(f'ui.{group}: unexpected fields')
        for key, value in fields.items():
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f'ui.{group}.{key} must be finite')
            low, high = UI_FIELD_BOUNDS[key]
            if value < low or value > high:
                raise ValueError(f'ui.{group}.{key}: expected {low}..{high}')
            result[group][key] = float(value) if key == 'durationSeconds' else int(value) if value == int(value) else (_ for _ in ()).throw(ValueError(f'ui.{group}.{key}: integer px required'))
    return result


def normalize_ui_presentation(change, base=None):
    if not isinstance(change, dict) or set(change) - {'desktop', 'mobile'}:
        raise ValueError('uiPresentation expects desktop/mobile profiles')
    base = base or UI_PROFILE_DEFAULTS
    return {device: normalize_ui_profile(change.get(device, {}), base[device])
            for device in ('desktop', 'mobile')}


# M449: one persisted per-socket reach/reticle contract for House and Campfire.
# Noninteractive authoring/HEAD sockets are deliberately excluded from editing.
# The defaults mirror existing Luau contracts; save only changes via Options.
SOCKET_RANGE_DEFAULTS = {
    'house': {
        'door_01_handle_outside_socket': {'useRadius': 8},
        'door_01_handle_inside_socket': {'useRadius': 8},
        'door_01_padlock_01_outside_socket': {'useRadius': 6},
        'door_01_padlock_01_inside_socket': {'useRadius': 6},
        'chest_01_socket': {'useRadius': 8, 'aimRadius': 4},
        'elevator_01_socket': {'useRadius': 10, 'aimRadius': 5},
        'elevator_02_socket': {'useRadius': 10, 'aimRadius': 5},
        'elevator_03_socket': {'useRadius': 10, 'aimRadius': 5},
        'fireplace_01_socket': {'useRadius': 8, 'aimRadius': 4},
    },
    'campfire': {'fire_socket': {'useRadius': 8, 'aimRadius': 4}},
    'windmill': {'windmill_door_handle_socket': {'useRadius': 8}},
}


def normalize_socket_ranges(change, base=None):
    """Whitelist only actionable authored sockets. USE and AIM are server limits."""
    import math
    if not isinstance(change, dict) or set(change) - set(SOCKET_RANGE_DEFAULTS):
        raise ValueError('socketRanges: unknown domain')
    base = base or SOCKET_RANGE_DEFAULTS
    result = deepcopy(base)
    for domain, sockets in SOCKET_RANGE_DEFAULTS.items():
        result.setdefault(domain, {})
        for name, fields in sockets.items():
            result[domain].setdefault(name, deepcopy(fields))
    for domain, sockets in change.items():
        if not isinstance(sockets, dict) or set(sockets) - set(SOCKET_RANGE_DEFAULTS[domain]):
            raise ValueError(f'socketRanges.{domain}: unknown socket')
        for name, fields in sockets.items():
            template = SOCKET_RANGE_DEFAULTS[domain][name]
            if not isinstance(fields, dict) or set(fields) - set(template):
                raise ValueError(f'socketRanges.{domain}.{name}: unknown field')
            for field, value in fields.items():
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError(f'{name}.{field} must be a finite number')
                low, high = (2, 30) if field == 'useRadius' else (1, 16)
                if not low <= value <= high:
                    raise ValueError(f'{name}.{field} must be {low}..{high} studs')
                result[domain][name][field] = float(value)
            row = result[domain][name]
            if row.get('aimRadius', 0) > row['useRadius']:
                raise ValueError(f'{name}: AIM must not exceed USE')
    return result


# M452: per-asset mechanical rotations. Rendering uses one source of truth
# published into GameOptionsRegistry, not a client-side hard-coded period.
ROTATION_DEFAULTS = {
    'windmill_02': {'enabled': True, 'secondsPerRevolution': 3.0},
}


def normalize_rotations(change, base=None):
    import math
    if not isinstance(change, dict) or set(change) - set(ROTATION_DEFAULTS):
        raise ValueError('rotations: unsupported asset')
    result = deepcopy(base or ROTATION_DEFAULTS)
    for slug, row in change.items():
        if not isinstance(row, dict) or set(row) - {'enabled', 'secondsPerRevolution'}:
            raise ValueError(f'rotations.{slug}: unknown field')
        if 'enabled' in row:
            if type(row['enabled']) is not bool:
                raise ValueError(f'rotations.{slug}.enabled must be boolean')
            result[slug]['enabled'] = row['enabled']
        if 'secondsPerRevolution' in row:
            value = row['secondsPerRevolution']
            if type(value) not in (int, float) or not math.isfinite(value) or not 0.25 <= value <= 120:
                raise ValueError(f'rotations.{slug}.secondsPerRevolution must be 0.25..120 seconds')
            result[slug]['secondsPerRevolution'] = float(value)
    return result


# Streaming radii belong to Workspace / the published Place, not to a player.
# The command-bar helper in Asset Manager applies this value in Studio Edit.
def normalize_world_streaming(change, base=None):
    if not isinstance(change, dict) or set(change) - {'targetRadiusStuds'}:
        raise ValueError('worldStreaming accepts targetRadiusStuds only')
    result = deepcopy(base or {'targetRadiusStuds': 150})
    value = change.get('targetRadiusStuds', result['targetRadiusStuds'])
    if type(value) is not int or not (96 <= value <= 4096):
        raise ValueError('worldStreaming.targetRadiusStuds must be an integer 96..4096')
    result['targetRadiusStuds'] = value
    return result


# Player movement physics (shared on PC and mobile; does not modify Workspace.Gravity).
def normalize_player_jump(change, base=None):
    import math
    if not isinstance(change, dict) or set(change) - {'heightMultiplier', 'descentTimeMultiplier'}:
        raise ValueError('playerJump accepts heightMultiplier/descentTimeMultiplier only')
    result = deepcopy(base or {'heightMultiplier': 2.0, 'descentTimeMultiplier': 2.0})
    for key in ('heightMultiplier', 'descentTimeMultiplier'):
        value = change.get(key, result[key])
        if type(value) not in (int, float) or not math.isfinite(value) or not 0.5 <= value <= 4:
            raise ValueError(f'playerJump.{key} must be finite 0.5..4')
        result[key] = float(value)
    return result


NPC_OVERHEAD_DEFAULTS = {
    "desktop": {"nameRadiusStuds": 70, "healthRadiusStuds": 70},
    "mobile": {"nameRadiusStuds": 70, "healthRadiusStuds": 70},
}


def normalize_npc_overhead(change, base=None):
    import math
    if not isinstance(change, dict) or set(change) - {'desktop', 'mobile'}:
        raise ValueError('npcOverhead requires desktop/mobile profiles')
    result = deepcopy(base or NPC_OVERHEAD_DEFAULTS)
    for device, fields in change.items():
        if not isinstance(fields, dict) or set(fields) - {'nameRadiusStuds', 'healthRadiusStuds'}:
            raise ValueError('invalid NPC overhead fields')
        for key, value in fields.items():
            if type(value) not in (int, float) or not math.isfinite(value) or not 10 <= value <= 800:
                raise ValueError(f'npcOverhead.{device}.{key} must be 10..800')
            result[device][key] = float(value)
    return result


def normalize_monster_ai(change, base=None):
    import math
    if not isinstance(change, dict) or set(change) - {'noDamageReturnSeconds'}:
        raise ValueError('monsterAi only accepts noDamageReturnSeconds')
    result = deepcopy(base or {'noDamageReturnSeconds': 30})
    value = change.get('noDamageReturnSeconds', result['noDamageReturnSeconds'])
    if type(value) not in (int, float) or not math.isfinite(value) or not 1 <= value <= 3600:
        raise ValueError('monster return delay must be 1..3600 seconds')
    result['noDamageReturnSeconds'] = float(value)
    return result


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
    if isinstance(value, list):
        return 'table.freeze({' + ', '.join(lua_literal(item, indent + 1) for item in value) + '})'
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
    "uiPresentation": deepcopy(UI_PROFILE_DEFAULTS),
    "socketRanges": deepcopy(SOCKET_RANGE_DEFAULTS),
    "rotations": deepcopy(ROTATION_DEFAULTS),
    "flora": deepcopy(FLORA_DEFAULTS),
    "characterCreation": deepcopy(CREATION_DEFAULTS),
    "npcOverhead": deepcopy(NPC_OVERHEAD_DEFAULTS),
    "monsterAi": {"noDamageReturnSeconds": 30},
    "worldStreaming": {"targetRadiusStuds": 150},
    "playerJump": {"heightMultiplier": 2.0, "descentTimeMultiplier": 2.0},
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
        self._ui_draft = None
        self._ui_draft_at = 0
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
        normalize_ui_presentation(payload.get('uiPresentation', UI_PROFILE_DEFAULTS))
        normalize_socket_ranges(payload.get('socketRanges', SOCKET_RANGE_DEFAULTS))
        normalize_rotations(payload.get('rotations', ROTATION_DEFAULTS))
        validate_residents(self.root, normalize_flora(payload.get('flora', FLORA_DEFAULTS)))
        normalize_character_creation(payload.get('characterCreation', CREATION_DEFAULTS))
        normalize_npc_overhead(payload.get('npcOverhead', NPC_OVERHEAD_DEFAULTS))
        normalize_monster_ai(payload.get('monsterAi', DEFAULT_PAYLOAD['monsterAi']))
        normalize_world_streaming(payload.get('worldStreaming', DEFAULT_PAYLOAD['worldStreaming']))
        normalize_player_jump(payload.get('playerJump', DEFAULT_PAYLOAD['playerJump']))
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
            "\tuiPresentation = " + lua_literal(normalize_ui_presentation(payload.get('uiPresentation', UI_PROFILE_DEFAULTS))) + ",",
            "\tsocketRanges = " + lua_literal(normalize_socket_ranges(payload.get('socketRanges', SOCKET_RANGE_DEFAULTS))) + ",",
            "\trotations = " + lua_literal(normalize_rotations(payload.get('rotations', ROTATION_DEFAULTS))) + ",",
            "\tflora = " + lua_literal(normalize_flora(payload.get('flora', FLORA_DEFAULTS))) + ",",
            "\tcharacterCreation = " + lua_literal(normalize_character_creation(payload.get('characterCreation', CREATION_DEFAULTS))) + ",",
            "\tnpcOverhead = " + lua_literal(normalize_npc_overhead(payload.get('npcOverhead', NPC_OVERHEAD_DEFAULTS))) + ",",
            "\tmonsterAi = " + lua_literal(normalize_monster_ai(payload.get('monsterAi', DEFAULT_PAYLOAD['monsterAi']))) + ",",
            "\tplayerJump = " + lua_literal(normalize_player_jump(payload.get('playerJump', DEFAULT_PAYLOAD['playerJump']))) + ",",
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
        # One-time M449 migration: honor an already-authored campfire USE/AIM
        # profile from Mechanics, then make Options the only runtime authority.
        if 'socketRanges' not in payload:
            initial = deepcopy(SOCKET_RANGE_DEFAULTS)
            legacy_path = self.root / 'config/mechanics/fireplace.json'
            if legacy_path.is_file():
                try:
                    legacy = json.loads(legacy_path.read_text(encoding='utf-8'))
                    if not isinstance(legacy, dict):
                        raise ValueError('expected an object')
                    if 'CampfireInteractionRadius' in legacy and 'CampfireAimRadius' in legacy:
                        imported = {'campfire': {'fire_socket': {
                            'useRadius': legacy['CampfireInteractionRadius'],
                            'aimRadius': legacy['CampfireAimRadius'],
                        }}}
                        initial = normalize_socket_ranges(imported, initial)
                except (OSError, ValueError, TypeError) as error:
                    # An unrelated, damaged Mechanics file must not prevent
                    # Options and the rest of Control Center from starting.
                    print(f'[options] M449 campfire range migration skipped: {error}')
            payload['socketRanges'] = normalize_socket_ranges(initial)
            changed = True
        for field in ('healthUi', 'npcOverhead', 'monsterAi', 'debugUi', 'worldStreaming', 'playerJump', 'uiPresentation', 'socketRanges', 'rotations', 'flora', 'characterCreation'):
            if field not in payload:
                payload[field] = deepcopy(DEFAULT_PAYLOAD[field])
                changed = True
        for field in ('cameraPresets', 'activeCameraPreset'):
            if field not in payload:
                payload[field] = deepcopy(DEFAULT_PAYLOAD[field])
                changed = True
        # Upgrade older saved per-device HP profiles without changing authored values.
        normalized_health = normalize_health_ui(payload['healthUi'])
        if normalized_health != payload['healthUi']:
            payload['healthUi'] = normalized_health
            changed = True
        # Add newly introduced UI fields to both device profiles in existing
        # manifests without erasing player-authored offsets/fonts/timers.
        upgraded_ui = normalize_ui_presentation(payload['uiPresentation'], UI_PROFILE_DEFAULTS)
        if upgraded_ui != payload['uiPresentation']:
            payload['uiPresentation'] = upgraded_ui
            changed = True
        # Extend the existing scene contract without resetting authored camera views.
        creation = payload['characterCreation']
        old_materials = creation.get('materialChoices')
        if isinstance(old_materials, dict) and set(old_materials) == {'hair', 'eyes'}:
            creation['materialChoices'] = deepcopy(CREATION_DEFAULTS['materialChoices'])
            changed = True
        normalized_creation = normalize_character_creation({}, creation)
        if 'animations' not in creation:
            backup = self.manifest_path.with_name('options.json.pre-m505-'
                + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.bak')
            backup.write_bytes(self.manifest_path.read_bytes())
        if normalized_creation != payload['characterCreation']:
            payload['characterCreation'] = normalized_creation
            changed = True
        normalized_ranges = normalize_socket_ranges({}, payload['socketRanges'])
        if normalized_ranges != payload['socketRanges']:
            payload['socketRanges'] = normalized_ranges
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

    def preview_ui(self, request: dict) -> dict:
        if not isinstance(request, dict) or set(request) != {'device', 'settings'}:
            raise ValueError('UI draft requires device and settings')
        device = request['device']
        if device not in UI_PROFILE_DEFAULTS:
            raise ValueError('UI draft device unsupported')
        checked = normalize_ui_profile(request['settings'], UI_PROFILE_DEFAULTS[device])
        with self._debug_lock:
            self._ui_draft = {'device': device, 'settings': checked}
            self._ui_draft_at = time.time()
        return {'saved': False, 'uiPresentationDebugDraftAt': self._ui_draft_at}

    def snapshot_with_debug(self) -> dict:
        payload = self.snapshot()
        with self._debug_lock:
            payload['cameraDebugDraft'] = deepcopy(self._camera_draft)
            payload['cameraDebugDraftAt'] = self._camera_draft_at
            payload['healthUiDebugDraft'] = deepcopy(self._health_draft)
            payload['healthUiDebugDraftAt'] = self._health_draft_at
            payload['uiPresentationDebugDraft'] = deepcopy(self._ui_draft)
            payload['uiPresentationDebugDraftAt'] = self._ui_draft_at
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
        if 'npcOverhead' in request:
            payload['npcOverhead'] = normalize_npc_overhead(request['npcOverhead'], payload.get('npcOverhead', NPC_OVERHEAD_DEFAULTS))
        if 'monsterAi' in request:
            payload['monsterAi'] = normalize_monster_ai(request['monsterAi'], payload.get('monsterAi', DEFAULT_PAYLOAD['monsterAi']))
        if 'flora' in request:
            next_flora = normalize_flora(request['flora'], payload.get('flora', FLORA_DEFAULTS))
            validate_residents(self.root, next_flora)
            payload['flora'] = next_flora
        if 'characterCreation' in request:
            payload['characterCreation'] = normalize_character_creation(request['characterCreation'],
                payload.get('characterCreation', CREATION_DEFAULTS))
        if 'rotations' in request:
            payload['rotations'] = normalize_rotations(request['rotations'],
                payload.get('rotations', ROTATION_DEFAULTS))
        if 'socketRanges' in request:
            payload['socketRanges'] = normalize_socket_ranges(request['socketRanges'],
                payload.get('socketRanges', SOCKET_RANGE_DEFAULTS))
        if 'uiPresentation' in request:
            payload['uiPresentation'] = normalize_ui_presentation(request['uiPresentation'],
                payload.get('uiPresentation', UI_PROFILE_DEFAULTS))
        if 'healthUi' in request:
            payload['healthUi'] = normalize_health_ui(request['healthUi'],
                                                       payload.get('healthUi', HEALTH_UI_DEFAULTS))
        if 'playerJump' in request:
            payload['playerJump'] = normalize_player_jump(request['playerJump'], payload.get('playerJump', DEFAULT_PAYLOAD['playerJump']))
        if 'worldStreaming' in request:
            payload['worldStreaming'] = normalize_world_streaming(
                request['worldStreaming'], payload.get('worldStreaming', DEFAULT_PAYLOAD['worldStreaming']))
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
