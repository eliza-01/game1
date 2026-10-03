from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from character_store import CharacterStore

store = CharacterStore(ROOT)
snapshot = store.snapshot()
print("game1 character data migrated")
print("schema:", snapshot["schemaVersion"])
print("registered:", len(snapshot["items"]))
print("active:", snapshot["activeArchetypeId"] or "none")
