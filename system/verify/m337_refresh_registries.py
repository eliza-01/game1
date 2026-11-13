"""M337: refresh runtime registries without replacing user-authored manifests.

Safe to run repeatedly; uses the same store serializers as Asset Manager.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system" / "control-center"))
from options_store import OptionsStore  # noqa: E402
from monster_spawn_store import MonsterSpawnStore  # noqa: E402

OptionsStore(ROOT)  # merges only missing keys, preserves authored HP/camera/debug
for kind in ("monster", "npc"):
    MonsterSpawnStore(ROOT, None, None, None, kind=kind)
print("M337: Options and monster/NPC spawn registries refreshed")
