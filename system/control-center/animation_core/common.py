from __future__ import annotations

from pathlib import Path
import re
import time

SCHEMA_VERSION = 2
PROJECT = "game1"
MAX_SCAN_FILES = 5000
ANIMATION_EXTENSIONS = {".rbxm", ".rbxmx"}
WEAPON_SETS = ("hands", "1hs", "2hs", "bow")

BASE_SLOT_CATALOG = [
    {"group": "locomotion", "slot": "idle", "label": "idle", "looped": True, "priority": "Idle"},
    {"group": "locomotion", "slot": "walk", "label": "walk", "looped": True, "priority": "Movement"},
    {"group": "locomotion", "slot": "run", "label": "run", "looped": True, "priority": "Movement"},
    {"group": "airborne", "slot": "jump_start", "label": "jump start", "looped": False, "priority": "Movement"},
    {"group": "airborne", "slot": "jump_loop", "label": "jump loop", "looped": True, "priority": "Movement"},
    {"group": "airborne", "slot": "fall", "label": "fall", "looped": True, "priority": "Movement"},
    {"group": "airborne", "slot": "land", "label": "land", "looped": False, "priority": "Movement"},
    {"group": "seated", "slot": "seated.enter", "label": "sit down", "looped": False, "priority": "Action"},
    {"group": "seated", "slot": "seated.loop", "label": "sit", "looped": True, "priority": "Movement"},
    {"group": "seated", "slot": "seated.exit", "label": "sit up", "looped": False, "priority": "Action"},
    {"group": "life", "slot": "death", "label": "death", "looped": False, "priority": "Action"},
    {"group": "life", "slot": "death_wait", "label": "wait in death state", "looped": True, "priority": "Action"},
    {"group": "life", "slot": "revive", "label": "rise after death", "looped": False, "priority": "Action"},
]

WEAPON_SLOT_CATALOG = [
    {"group": "stance", "slot": "idle", "label": "idle", "looped": True, "priority": "Idle", "variants": False},
    {"group": "stance", "slot": "combat_idle", "label": "combat idle", "looped": True, "priority": "Idle", "variants": False},
    {"group": "movement", "slot": "walk", "label": "walk", "looped": True, "priority": "Movement", "variants": False},
    {"group": "movement", "slot": "run", "label": "run", "looped": True, "priority": "Movement", "variants": False},
    {"group": "combat", "slot": "attack", "label": "attack", "looped": False, "priority": "Action", "variants": True},
    {"group": "combat", "slot": "special_attack", "label": "special attack", "looped": False, "priority": "Action", "variants": True},
]

BOW_EXTRA_SLOTS = [
    {"group": "stance", "slot": "aim", "label": "aim", "looped": True, "priority": "Movement", "variants": False},
]

SLOT_BY_BASE = {row["slot"]: row for row in BASE_SLOT_CATALOG}
SLOT_BY_WEAPON = {row["slot"]: row for row in WEAPON_SLOT_CATALOG}
SLOT_BY_BOW = {**SLOT_BY_WEAPON, **{row["slot"]: row for row in BOW_EXTRA_SLOTS}}

NAMING_EXAMPLES = [
    "human_female_hands_idle.rbxm -> hands / idle",
    "human_female_hands_attack_01.rbxm -> hands / attack / 01",
    "human_female_1hs_attack_02.rbxm -> 1hs / attack / 02",
    "human_female_bow_aim.rbxm -> bow / aim",
    "human_female_idle.rbxm -> base / idle",
    "Atk02_1HS_FFighter.rbxm -> 1hs / attack / 02 (reference form)",
]




def filename_rule_catalog(character_id: str = "") -> list[dict]:
    """Return every canonical semantic state with the filename scanner expects.

    This is the single source of truth for the Control Center filename-rules UI.
    Variant slots use variant 01 as the canonical example and expose 01..n separately.
    """
    rows: list[dict] = []
    archetype = _safe_token(str(character_id or ""))
    filename_prefix = archetype + "_" if archetype else ""

    for definition in BASE_SLOT_CATALOG:
        slot = definition["slot"]
        rows.append({
            "scope": "base",
            "context": "base",
            "group": definition.get("group", ""),
            "state": slot,
            "label": definition.get("label", slot),
            "variants": False,
            "variantPattern": "",
            "canonicalFilename": filename_prefix + _canonical_file_stem("base", "", slot, 0) + ".rbxm",
        })

    for weapon_set in WEAPON_SETS:
        for definition in _catalog_for_weapon(weapon_set).values():
            slot = definition["slot"]
            has_variants = bool(definition.get("variants"))
            example_variant = 1 if has_variants else 0
            rows.append({
                "scope": "weapon",
                "context": weapon_set,
                "group": definition.get("group", ""),
                "state": slot,
                "label": definition.get("label", slot),
                "variants": has_variants,
                "variantPattern": "01..n" if has_variants else "",
                "canonicalFilename": filename_prefix + _canonical_file_stem("weapon", weapon_set, slot, example_variant) + ".rbxm",
            })

    return rows

def _now() -> float:
    return time.time()


def _safe_token(value: str) -> str:
    value = re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")
    return re.sub(r"_+", "_", value)


def _canonical_file_stem(scope: str, weapon_set: str, slot: str, variant: int) -> str:
    slot_token = slot.replace(".", "_")
    if scope == "base":
        return f"base_{slot_token}"
    suffix = f"_{variant:02d}" if variant > 0 else ""
    return f"{weapon_set}_{slot_token}{suffix}"


def _clip_id(character_id: str, scope: str, weapon_set: str, slot: str, variant: int) -> str:
    parts = [character_id, scope]
    if weapon_set:
        parts.append(weapon_set)
    parts.extend([slot.replace(".", "_"), f"{variant:02d}"])
    return "__".join(parts)


def _binding_id(character_id: str, scope: str, weapon_set: str, slot: str, variant: int) -> str:
    return "binding__" + _clip_id(character_id, scope, weapon_set, slot, variant)


def _normalize_stem(path: Path) -> str:
    return _safe_token(path.stem)


def _parse_variant(value: str) -> tuple[str, int]:
    match = re.match(r"^(.*?)(?:_([0-9]{1,3}))?$", value)
    if not match:
        return value, 0
    base = match.group(1)
    raw = match.group(2)
    return base, int(raw) if raw else 0


def _catalog_for_weapon(weapon_set: str) -> dict[str, dict]:
    return SLOT_BY_BOW if weapon_set == "bow" else SLOT_BY_WEAPON


def _strip_character_prefix(stem: str, character_id: str | None) -> str:
    character = _safe_token(str(character_id or ""))
    prefix = character + "_" if character else ""
    if prefix and stem.startswith(prefix):
        return stem[len(prefix):]
    return stem


def normalize_manual_binding(scope: str, weapon_set: str, slot: str, variant: int | str = 0) -> dict:
    scope = _safe_token(str(scope or ""))
    weapon_set = _safe_token(str(weapon_set or ""))
    slot = _safe_token(str(slot or "")).replace("seated_enter", "seated.enter").replace("seated_loop", "seated.loop").replace("seated_exit", "seated.exit")
    try:
        variant_number = max(0, int(variant or 0))
    except (TypeError, ValueError):
        variant_number = 0

    if scope == "base":
        if slot not in SLOT_BY_BASE:
            raise ValueError(f"unknown base animation slot: {slot}")
        definition = SLOT_BY_BASE[slot]
        return {"scope": "base", "weaponSet": "", "slot": slot, "variant": 0, **definition}

    if scope != "weapon":
        raise ValueError("animation scope must be base or weapon")
    if weapon_set not in WEAPON_SETS:
        raise ValueError(f"unknown weapon animation set: {weapon_set}")
    catalog = _catalog_for_weapon(weapon_set)
    if slot not in catalog:
        raise ValueError(f"slot {slot} is not available for {weapon_set}")
    definition = catalog[slot]
    if definition.get("variants"):
        variant_number = max(1, variant_number)
    else:
        variant_number = 0
    return {"scope": "weapon", "weaponSet": weapon_set, "slot": slot, "variant": variant_number, **definition}


def classify_animation(path: Path, character_id: str | None = None) -> dict | None:
    """Map a Studio-exported clip filename to the canonical game1 semantic coordinate."""
    stem = _strip_character_prefix(_normalize_stem(path), character_id)
    if not stem:
        return None

    base_aliases = {
        "idle": "idle", "base_idle": "idle", "walk": "walk", "base_walk": "walk",
        "run": "run", "base_run": "run", "jump_start": "jump_start",
        "base_jump_start": "jump_start", "jump_loop": "jump_loop",
        "base_jump_loop": "jump_loop", "fall": "fall", "falling": "fall",
        "base_fall": "fall", "land": "land", "base_land": "land",
        "sitdown": "seated.enter", "sit_down": "seated.enter",
        "seated_enter": "seated.enter", "base_seated_enter": "seated.enter",
        "sit": "seated.loop", "sitwait": "seated.loop", "sit_wait": "seated.loop",
        "seated_loop": "seated.loop", "base_seated_loop": "seated.loop",
        "situp": "seated.exit", "sit_up": "seated.exit", "stand": "seated.exit",
        "seated_exit": "seated.exit", "base_seated_exit": "seated.exit",
        "death": "death", "die": "death", "base_death": "death",
        "dead": "death_wait", "dead_idle": "death_wait", "death_wait": "death_wait", "dead_wait": "death_wait", "base_dead_idle": "death_wait", "base_death_wait": "death_wait",
        "revive": "revive", "rise": "revive", "resurrection": "revive", "base_revive": "revive",
    }
    if stem in base_aliases:
        slot = base_aliases[stem]
        return {"scope": "base", "weaponSet": "", "slot": slot, "variant": 0, **SLOT_BY_BASE[slot]}

    for weapon_set in WEAPON_SETS:
        prefix = weapon_set + "_"
        if not stem.startswith(prefix):
            continue
        body, variant = _parse_variant(stem[len(prefix):])
        slot = {
            "idle": "idle", "combat_idle": "combat_idle", "attack_wait": "combat_idle",
            "walk": "walk", "run": "run", "attack": "attack",
            "special_attack": "special_attack", "aim": "aim",
        }.get(body)
        catalog = _catalog_for_weapon(weapon_set)
        if slot in catalog:
            if not catalog[slot].get("variants"):
                variant = 0
            elif variant <= 0:
                variant = 1
            return {"scope": "weapon", "weaponSet": weapon_set, "slot": slot, "variant": variant, **catalog[slot]}

    # proven reference forms: Wait_1HS_*, AtkWait_Bow_*, Atk01_1HS_*, SpAtk02_Bow_*
    tokens = stem.split("_")
    weapon_index = next((i for i, token in enumerate(tokens) if token in WEAPON_SETS), None)
    if weapon_index is None or weapon_index <= 0:
        return None
    head = tokens[0]
    weapon_set = tokens[weapon_index]
    slot = {"wait": "idle", "atkwait": "combat_idle", "walk": "walk", "run": "run"}.get(head)
    variant = 0
    if head == "aim" and weapon_set == "bow":
        slot = "aim"
    if slot is None:
        attack_match = re.fullmatch(r"atk0*([0-9]+)", head)
        special_match = re.fullmatch(r"spatk0*([0-9]+)", head)
        if attack_match:
            slot = "attack"
            variant = max(1, int(attack_match.group(1)))
        elif special_match:
            slot = "special_attack"
            variant = max(1, int(special_match.group(1)))
    catalog = _catalog_for_weapon(weapon_set)
    if slot in catalog:
        return {"scope": "weapon", "weaponSet": weapon_set, "slot": slot, "variant": variant, **catalog[slot]}
    return None
