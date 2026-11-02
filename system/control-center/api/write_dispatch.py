"""Transport-neutral POST and DELETE routing. Handlers return (status, JSON data)."""
from . import write_files, write_actors, write_world, write_animations, delete_entities, real_estate
from services.shared_asset_retirement import SharedAssetRetirement


def dispatch_post(path, body, deps):
    if path == '/api/asset-retirement/execute':
        try:
            data = body()
            coordinator = SharedAssetRetirement(
                deps['real_estate'], deps['location_assets'],
                deps.get('real_estate_publications'))
            return 200, coordinator.execute(
                str(data.get('kind') or ''), str(data.get('slug') or ''),
                mode=str(data.get('mode') or 'preserve'),
                token=str(data.get('token') or ''))
        except (ValueError, OSError, KeyError) as error:
            return 400, {'error': str(error)}
    for handler in (real_estate.write, write_files.route, write_actors.route, write_world.route, write_animations.route):
        response = handler(path, body, deps)
        if response is not None:
            return response
    return 404, {"error": "not found"}


def dispatch_delete(path, body, deps):
    response = delete_entities.route(path, body, deps)
    if response is not None:
        return response
    return 404, {"error": "not found"}
