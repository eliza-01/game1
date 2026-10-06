from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from character_store import CharacterStore
from animation_store import AnimationStore
from weapon_store import WeaponStore
from monster_store import MonsterStore
from monster_animation_store import MonsterAnimationStore

characters = CharacterStore(ROOT)
animations = AnimationStore(ROOT)
weapons = WeaponStore(ROOT)
monsters = MonsterStore(ROOT)
monster_animations = MonsterAnimationStore(ROOT)
character_snapshot = characters.snapshot()
animation_snapshot = animations.snapshot(character_snapshot.get("activeArchetypeId"))
weapon_snapshot = weapons.snapshot()
print("game1 data migrated")
print("character schema:", character_snapshot["schemaVersion"])
print("registered characters:", len(character_snapshot["items"]))
print("active character:", character_snapshot["activeArchetypeId"] or "none")
print("animation schema:", animation_snapshot["schemaVersion"])
print("registered animations:", animation_snapshot["summary"]["registered"])

print("weapon schema:", weapon_snapshot["schemaVersion"])
print("registered weapons:", weapon_snapshot["summary"]["registered"])
print("active weapon:", weapon_snapshot["activeWeaponSlug"] or "none")

monster_snapshot = monsters.snapshot()
monster_animation_snapshot = monster_animations.snapshot(monster_snapshot["items"][0]["slug"] if monster_snapshot["items"] else None)
print("monster schema:", monster_snapshot["schemaVersion"])
print("registered monsters:", monster_snapshot["summary"]["registered"])
print("monster animation schema:", monster_animation_snapshot["schemaVersion"])
print("registered monster animations:", monster_animation_snapshot["summary"]["registered"])
