"""HTTP GET dispatch. Does not know HTTP transports or persistence implementations."""
from . import read_catalog, read_world


def dispatch(parsed, sources, info):
    response = read_world.route(parsed, sources, info)
    if response is not None:
        return response
    response = read_catalog.route(parsed, sources, sources["publication_config"])
    if response is not None:
        return response
    return 404, {"error": "not found"}
