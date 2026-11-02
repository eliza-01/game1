"""Stable Character archetype identity/publication constants (no storage I/O)."""
from __future__ import annotations
import re

SCHEMA_VERSION = 5
PROJECT = "game1"
STAT_KEYS = ("Level", "MaxHP", "Damage", "Defense", "AttackSpeed", "RunSpeed", "CritChance")
DEFAULT_STATS = {
    "Level": 1, "MaxHP": 100, "Damage": 10, "Defense": 0,
    "AttackSpeed": 100, "RunSpeed": 50, "CritChance": 0,
}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
ACTIVE_KEY = "active_character_archetype_id"
RACES = ("human",)
GENDERS = ("male", "female")
CHARACTER_PUBLICATION_PIPELINE = "roblox-open-cloud-bone-survival-v2-scale-safe"
