"""Transport-neutral POST and DELETE routing. Handlers return (status, JSON data)."""
from . import write_files, write_actors, write_world, write_animations, delete_entities, real_estate


def dispatch_post(path, body, deps):
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
