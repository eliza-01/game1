"""Transport-neutral POST and DELETE routing. Handlers return (status, JSON data)."""
from . import write_files, write_actors, write_world, write_animations, delete_entities, real_estate, kanban
from services.shared_asset_retirement import SharedAssetRetirement


def _requires_asset_audit(path):
    return (path.endswith('/publish-pending-atlas')
            or path == '/api/texture-atlases/publish-reviewed'
            or path == '/api/asset-retirement/execute'
            or path == '/api/characters/workflow'
            or path.endswith(('/publish', '/publish-missing', '/republish',
                               '/replace-model', '/model')))


def dispatch_post(path, body, deps):
    audit = deps.get('asset_replacement_audit')
    requires_audit = audit is not None and _requires_asset_audit(path)
    if requires_audit:
        try:
            audit.sync_all()
        except Exception as error:
            return 503, {'error': f'asset audit unavailable; mutation refused: {error}'}
    if path == '/api/asset-retirement/execute':
        try:
            data = body()
            coordinator = SharedAssetRetirement(
                deps['real_estate'], deps['location_assets'],
                deps.get('real_estate_publications'))
            response = 200, coordinator.execute(
                str(data.get('kind') or ''), str(data.get('slug') or ''),
                mode=str(data.get('mode') or 'preserve'),
                token=str(data.get('token') or ''))
            audit.sync_all()
            return response
        except (ValueError, OSError, KeyError) as error:
            return 400, {'error': str(error)}
    for handler in (kanban.write, real_estate.write, write_files.route, write_actors.route, write_world.route, write_animations.route):
        response = handler(path, body, deps)
        if response is not None:
            if requires_audit and response[0] < 300:
                try:
                    audit.sync_all()
                except Exception as error:
                    if path == '/api/texture-atlases/publish-reviewed' or path.endswith('/publish-pending-atlas'):
                        result = dict(response[1])
                        result.setdefault('exportWarnings', []).append(
                            f'Asset History import failed after publication: {error}')
                        return response[0], result
                    return 503, {'error': f'asset mutation completed but audit import failed: {error}'}
            return response
    return 404, {"error": "not found"}


def dispatch_delete(path, body, deps):
    audit = deps.get('asset_replacement_audit')
    if audit is not None:
        try:
            # Publication rows are store-owned and some deletion flows remove
            # them. Import first so history remains immutable after retirement.
            audit.sync_all()
        except Exception as error:
            return 503, {'error': f'asset audit unavailable; deletion refused: {error}'}
    response = delete_entities.route(path, body, deps)
    if response is not None:
        return response
    return 404, {"error": "not found"}
