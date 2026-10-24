"""Read-only world, authoring settings, runtime config and host status routes."""
from urllib.parse import parse_qs


def route(parsed, sources, info):
    path = parsed.path
    if path == "/api/agent/info":
        return 200, info()

    if path == "/api/texture-atlases":
        search = str((parse_qs(parsed.query).get('search') or [''])[0])
        return 200, {'families': sources['location_assets'].atlases.catalog(search)}

    if path == "/api/location-assets":
        snapshot = sources["location_assets"].snapshot()
        snapshot["publication"] = sources["publication_config"]()
        return 200, snapshot

    # Historically these GET errors were encoded as 400 JSON, not a transport crash.
    simple = {
        "/api/npc-spawns": "npc_spawns",
        "/api/monster-spawns": "monster_spawns",
        "/api/animation-speed-scaling": "animation_speed_scaling",
        "/api/options": "options",
        "/api/timelines": "timelines",
        "/api/locations": "locations",
    }
    resource_name = simple.get(path)
    if resource_name:
        try:
            return 200, sources[resource_name].snapshot()
        except Exception as error:
            return 400, {"error": str(error)}

    if path == "/api/timelines/editor-state":
        try:
            session = str((parse_qs(parsed.query).get("session") or [""])[0])
            return 200, sources["timelines"].editor_state(session)
        except Exception as error:
            return 400, {"error": str(error)}
    return None
