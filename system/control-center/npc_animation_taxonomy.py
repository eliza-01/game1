"""Canonical NPC animation coordinate and filename contract.

Actor identity, weapon set, semantic slot and variant are independent axes.
Never infer a game's weapon set from the NPC's name or a Roblox asset id.
"""
from __future__ import annotations
import re
from pathlib import Path

# Weapon sets are the same public animation sets supported by WeaponRegistry.
# Adding a new gameplay weapon set requires adding its name here and in the
# canonical weapon attack-movement registry, not branching by NPC slug.
WEAPON_SETS = ("base", "1hs", "2hs", "bow")
SLOTS = {
    "idle": False, "idle_special": True, "walk": False, "run": False,
    "combat_idle": False, "attack": True, "death": False,
}
ALIAS = {
    "special_idle": "idle_special", "sp_wait": "idle_special", "wait_idle": "idle",
    "attack_wait": "combat_idle", "atkwait": "combat_idle",
    "dead": "death", "die": "death", "atk": "attack", "wait": "idle",
}


def filename(slug: str, weapon_set: str, slot: str, variant: int, extension: str = ".rbxm") -> str:
    if weapon_set not in WEAPON_SETS or slot not in SLOTS:
        raise ValueError("unknown animation subtype/state")
    variant = int(variant)
    if SLOTS[slot] and not 1 <= variant <= 999:
        raise ValueError(f"{slot} requires variant 01..999")
    if not SLOTS[slot] and variant != 0:
        raise ValueError(f"{slot} does not accept a variant")
    prefix = f"{slug}_" if slug else ""
    return f"{prefix}{weapon_set}_{slot}{'_%02d' % variant if variant else ''}{extension}"


def parse(name: str, slug: str, *, allow_legacy: bool = True) -> dict | None:
    """Return semantic coordinate or None. Legacy NPC clips default to 1hs."""
    stem = Path(name).stem.lower()
    prefix = slug.lower() + "_"
    if stem.startswith(prefix):
        stem = stem[len(prefix):]
    weapon_set = next((item for item in WEAPON_SETS if stem.startswith(item + "_")), None)
    if weapon_set:
        stem = stem[len(weapon_set) + 1:]
    elif allow_legacy:
        weapon_set = "1hs"
    else:
        return None
    match = re.fullmatch(r"([a-z_]+?)(?:_([0-9]{1,3}))?", stem)
    if not match:
        return None
    slot = ALIAS.get(match.group(1), match.group(1))
    variant = int(match.group(2) or 0)
    if slot not in SLOTS:
        old_special = re.fullmatch(r"(?:spwait|idlespecial)0*([0-9]+)", stem)
        old_attack = re.fullmatch(r"atk0*([0-9]+)", stem)
        if old_special:
            slot, variant = "idle_special", int(old_special.group(1))
        elif old_attack:
            slot, variant = "attack", int(old_attack.group(1))
    if slot not in SLOTS:
        return None
    if SLOTS[slot]:
        variant = max(1, variant)
    elif variant:
        return None
    return {"weaponSet": weapon_set, "slot": slot, "variant": variant}


def validate_rename(proposed_name: str, slug: str, weapon_set: str, slot: str, variant: int, extension: str) -> str:
    expected = filename(slug, weapon_set, slot, variant, extension)
    if Path(proposed_name).name.lower() != expected.lower():
        raise ValueError(f"invalid animation name/type; rename to {expected}")
    return expected
