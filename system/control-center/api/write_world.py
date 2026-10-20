"""World, placement and timeline write operations. No HTTP, persistence, or Studio ownership.

Dependencies are supplied by the composition root; unhandled paths return None.
"""
from urllib.parse import unquote


def route(path, body, deps):
    if not path.startswith(('/api/location-assets', '/api/npc-spawns', '/api/monster-spawns', '/api/options', '/api/locations', '/api/timelines',)):
        return None

    def out(status, payload):
        return status, payload

    deco_layouts = deps["deco_layouts"]
    location_assets = deps["location_assets"]
    locations = deps["locations"]
    monster_spawns = deps["monster_spawns"]
    npc_place_spawn = deps["npc_place_spawn"]
    npc_register_spawn = deps["npc_register_spawn"]
    npc_spawns = deps["npc_spawns"]
    options_store = deps["options_store"]
    publication_credentials = deps["publication_credentials"]
    request_active_studio_save = deps["request_active_studio_save"]
    run_timeline_editor_bridge = deps["run_timeline_editor_bridge"]
    sync_monster_to_studio = deps["sync_monster_to_studio"]
    timelines = deps["timelines"]

    if path == "/api/location-assets/studio-sync":
        try:
            return out(200, {"studio": deps["sync_location_assets_to_studio"]()})
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/location-assets":
        try:
            return out(200, location_assets.register(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/location-assets/layout":
        try:
            payload = body()
            result = deco_layouts.save(payload)
            result["studioSave"] = request_active_studio_save()
            return out(200, result)
        except Exception as error:
            return out(400, {"error": str(error)})

    npc_spawn_actions = {
        "/api/npc-spawns/place": lambda body: npc_place_spawn(body),
        "/api/npc-spawns/register": lambda body: npc_register_spawn(body),
        "/api/npc-spawns/select": lambda body: npc_spawns.select(body),
        "/api/npc-spawns/delete": lambda body: npc_spawns.delete(body),
        "/api/npc-spawns/restore": lambda body: npc_spawns.restore(),
        "/api/npc-spawns/validate": lambda body: npc_spawns.validate(),
    }

    if path in npc_spawn_actions:
        try:
            return out(200, npc_spawn_actions[path](body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-spawns/place":
        try:
            return out(200, monster_spawns.place(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-spawns/register":
        try:
            payload = body()
            slug = str(payload.get("monsterSlug") or "").strip().lower()
            sync_monster_to_studio(slug)
            return out(200, monster_spawns.register(payload))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-spawns/select":
        try:
            return out(200, monster_spawns.select(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-spawns/delete":
        try:
            return out(200, monster_spawns.delete(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-spawns/restore":
        try:
            return out(200, monster_spawns.restore())
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/monster-spawns/validate":
        try:
            return out(200, monster_spawns.validate())
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/options":
        try:
            return out(200, options_store.update(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/locations/draw":
        try:
            return out(200, locations.draw(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/locations/register":
        try:
            return out(200, locations.register(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/locations/select":
        try:
            return out(200, locations.select(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/locations/restore":
        try:
            return out(200, locations.restore())
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/locations/delete":
        try:
            return out(200, locations.delete(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/locations/validate":
        try:
            return out(200, locations.validate())
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/timelines/open":
        try:
            payload = body()
            session = timelines.begin_editor_session(str(payload.get("clipId") or ""))
            studio = run_timeline_editor_bridge(session, timelines.event_catalog_for_subject(session["subjectType"]))
            duration = float(studio.get("duration") or 0)
            if duration > 0:
                timelines.update_editor_state({"sessionId": session["sessionId"], "action": "ready", "duration": duration})
            return out(200, {"session": timelines.editor_state(session["sessionId"]), "studio": studio})
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/timelines/editor-event":
        try:
            return out(200, timelines.update_editor_state(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    if path == "/api/timelines/save":
        try:
            return out(200, timelines.save(body()))
        except Exception as error:
            return out(400, {"error": str(error)})

    location_asset_prefix = "/api/location-assets/"

    location_asset_publish_suffix = "/publish"

    if path.startswith(location_asset_prefix) and path.endswith(location_asset_publish_suffix):
        slug = unquote(path[len(location_asset_prefix):-len(location_asset_publish_suffix)].strip("/"))
        try:
            payload = body()
            credentials = publication_credentials(str(payload.get("description") or "game1 location asset"))
            return out(200, location_assets.publish(slug, credentials))
        except Exception as error:
            return out(400, {"error": str(error)})
    return None
