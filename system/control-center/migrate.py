from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from character_store import CharacterStore
from animation_store import AnimationStore

characters = CharacterStore(ROOT)
animations = AnimationStore(ROOT)
character_snapshot = characters.snapshot()
animation_snapshot = animations.snapshot(character_snapshot.get("activeArchetypeId"))
print("game1 data migrated")
print("character schema:", character_snapshot["schemaVersion"])
print("registered characters:", len(character_snapshot["items"]))
print("active character:", character_snapshot["activeArchetypeId"] or "none")
print("animation schema:", animation_snapshot["schemaVersion"])
print("registered animations:", animation_snapshot["summary"]["registered"])
