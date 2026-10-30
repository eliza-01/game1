"""Read-only entity catalogs and publication history routes.

Do not mutate stores or depend on BaseHTTPRequestHandler/Studio transport.
"""
from urllib.parse import parse_qs, unquote
from . import character_components


def _query(parsed, name: str) -> str:
    return str((parse_qs(parsed.query).get(name) or [""])[0]).strip().lower()


def route(parsed, sources, publication_config):
    path = parsed.path
    if path == '/api/characters/assemblies':
        return 200, sources['character_assemblies'].snapshot()
    response = character_components.read(path, sources)
    if response is not None:
        return response
    catalog = {
        "/api/characters": ("characters", None),
        "/api/animations": ("animations", "character"),
        "/api/weapons": ("weapons", None),
        "/api/monsters": ("monsters", None),
        "/api/monster-animations": ("monster_animations", "monster"),
        "/api/npcs": ("npcs", None),
        "/api/npc-animations": ("npc_animations", "npc"),
    }
    entry = catalog.get(path)
    if entry is not None:
        resource_name, parameter = entry
        if parameter == "character":
            character = _query(parsed, parameter) or sources["characters"].active_id()
            snapshot = sources[resource_name].snapshot(character)
        elif parameter:
            snapshot = sources[resource_name].snapshot(_query(parsed, parameter))
        else:
            snapshot = sources[resource_name].snapshot()
        snapshot["publication"] = publication_config()
        return 200, snapshot

    if path == "/api/npc-equipment":
        return 200, sources["npc_equipment"].snapshot(_query(parsed, "npc"))

    publication_roots = {
        "/api/npcs/": "npcs",
        "/api/monsters/": "monsters",
        "/api/weapons/": "weapons",
        "/api/location-assets/": "location_assets",
        "/api/characters/": "characters",
    }
    for prefix, resource_name in publication_roots.items():
        suffix = "/publications"
        if path.startswith(prefix) and path.endswith(suffix):
            identifier = unquote(path[len(prefix):-len(suffix)].strip("/"))
            return 200, {"items": sources[resource_name].publications(identifier)}
    return None
