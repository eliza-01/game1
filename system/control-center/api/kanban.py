"""Small transport-neutral adapters for the development Kanban service."""
from kanban_store import KanbanError


def _response(fn):
    try:
        return 200, fn()
    except KanbanError as error:
        return error.status, {'error': str(error)}
    except OSError as error:
        return 503, {'error': f'Kanban storage unavailable: {error}'}


def read(path, sources):
    if path == '/api/kanban':
        return _response(sources['kanban'].list_cards)
    if path == '/api/kanban/export':
        return _response(sources['kanban'].export)
    if path.startswith('/api/kanban/'):
        tail = path[len('/api/kanban/'):]
        if tail.endswith('/history'):
            return _response(lambda: sources['kanban'].history_for(tail[:-len('/history')]))
        return _response(lambda: sources['kanban'].detail(tail))
    return None


def write(path, body, deps):
    if path == '/api/kanban':
        return _response(lambda: deps['kanban'].create(body()))
    if not path.startswith('/api/kanban/'):
        return None
    identifier = path[len('/api/kanban/'):]
    return _response(lambda: deps['kanban'].update(identifier, body()))
