"""Read-only world, authoring settings, runtime config and host status routes."""
from urllib.parse import parse_qs
from services.shared_asset_retirement import SharedAssetRetirement


def route(parsed, sources, info):
    path = parsed.path
    if path == "/api/agent/info":
        return 200, info()

    if path == "/api/texture-atlases":
        search = str((parse_qs(parsed.query).get('search') or [''])[0])
        return 200, {'families': sources['location_assets'].atlases.catalog_with_consumers(search)}

    if path.startswith('/api/texture-atlases/variants/') and path.endswith('/retirement'):
        try:
            raw = path[len('/api/texture-atlases/variants/'):-len('/retirement')].strip('/')
            if not raw.isdigit():
                raise ValueError('invalid atlas variant ID')
            return 200, sources['location_assets'].atlases.retirement_plan(int(raw))
        except (ValueError, OSError) as error:
            return 400, {'error': str(error)}

    if path == '/api/asset-replacements':
        try:
            query = parse_qs(parsed.query)
            domain = str((query.get('domain') or [''])[0])
            key = str((query.get('key') or [''])[0])
            event_kind = str((query.get('eventKind') or [''])[0])
            limit = int((query.get('limit') or ['200'])[0])
            raw_before = str((query.get('before') or [''])[0])
            page = sources['asset_replacement_audit'].page(
                domain=domain, key=key, event_kind=event_kind, limit=limit,
                before=int(raw_before) if raw_before else None)
            return 200, {'domain': domain, 'key': key, **page}
        except (ValueError, OSError, RuntimeError) as error:
            return 400, {'error': str(error)}

    if path == '/api/asset-retirement/impact':
        query = parse_qs(parsed.query)
        try:
            return 200, SharedAssetRetirement(
                sources['real_estate'], sources['location_assets'],
                sources.get('real_estate_publications')
            ).plan(str((query.get('kind') or [''])[0]), str((query.get('slug') or [''])[0]))
        except (ValueError, OSError) as error:
            return 400, {'error': str(error)}

    if path == "/api/location-assets/studio-history":
        try:
            query = parse_qs(parsed.query)
            slug = str((query.get('slug') or [''])[0])
            limit = int((query.get('limit') or ['200'])[0])
            raw_before = str((query.get('before') or [''])[0])
            page = sources['location_asset_sync_history'].page(
                slug, limit=limit, before=int(raw_before) if raw_before else None)
            return 200, {'slug': slug, **page}
        except (ValueError, OSError, RuntimeError) as error:
            return 400, {'error': str(error)}

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
