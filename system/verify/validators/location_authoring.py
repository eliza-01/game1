"""Read-only Location polygon authoring and editor contracts (M169)."""

import json
import re
from pathlib import Path
from typing import Callable


def check_location_authoring(root: Path, report_error: Callable[[str], None], *,
                             index_text: str, host_agent_text: str,
                             studio_bridge_text: str, studio_plugin_text: str) -> None:
    """Validate Location M41/M42 without writing files."""
    index_m35_text = index_text
    studio_bridge_m35_text = studio_bridge_text
    # m41 Location registration: RobloxLineage polygon authoring flow adapted to game1.
    location_manifest_path = root / "assets/manifests/locations.json"
    location_store_path = root / "system/control-center/location_store.py"
    location_js_path = root / "system/control-center/static/locations.js"
    location_css_path = root / "system/control-center/static/location-assets.css"
    location_plugin_path = root / "system/studio-plugin/modules/LocationCommands.luau"
    location_registry_path = root / "src/shared/world/LocationRegistry.luau"
    for path in [location_manifest_path, location_store_path, location_js_path, location_css_path, location_plugin_path, location_registry_path]:
        if not path.is_file():
            report_error(f"m41 Location authoring file missing: {path.relative_to(root)}")
    if location_manifest_path.is_file():
        location_manifest = json.loads(location_manifest_path.read_text(encoding="utf-8"))
        if location_manifest.get("schemaVersion") != 1 or location_manifest.get("project") != "game1" or not isinstance(location_manifest.get("records"), dict):
            report_error("m41 locations.json schema/project is invalid")
    location_store_text = location_store_path.read_text(encoding="utf-8") if location_store_path.is_file() else ""
    for required in [
        "class LocationStore",
        "_validate_polygon",
        "must not self-intersect",
        "def draw",
        "def register",
        "def restore",
        "LocationRegistry.luau",
    ]:
        if required not in location_store_text:
            report_error(f"m41 LocationStore missing {required}")
    location_js_text = location_js_path.read_text(encoding="utf-8") if location_js_path.is_file() else ""
    for required in [
        "/api/locations/draw",
        "/api/locations/register",
        "/api/locations/select",
        "/api/locations/restore",
        "/api/locations/delete",
        "/api/locations/validate",
        "click the first point",
    ]:
        if required not in location_js_text:
            report_error(f"m41 Locations UI missing {required}")
    for required in ['id="nav-locations"', 'id="locations-view"', 'location-assets.css?v=1']:
        if required not in index_m35_text:
            report_error(f"m41 Asset Manager Locations section missing {required}")
    if not re.search(r'locations\.js\?v=\d+', index_m35_text):
        report_error('m41 Asset Manager Locations section missing versioned locations.js')
    for required in [
        '"/api/locations"',
        'path == "/api/locations/draw"',
        'path == "/api/locations/register"',
        'path == "/api/locations/restore"',
    ]:
        if required not in host_agent_text:
            report_error(f"m41 host agent Location API missing {required}")
    for required in [
        "run_location_authoring_bridge",
        '"command": "location-authoring"',
        '"/location-authoring-result"',
    ]:
        if required not in studio_bridge_m35_text:
            report_error(f"m41 Studio Location bridge missing {required}")
    location_plugin_text = location_plugin_path.read_text(encoding="utf-8") if location_plugin_path.is_file() else ""
    for required in [
        'AUTHORING_ROOT = "Game1Authoring"',
        'LOCATION_FOLDER = "Locations"',
        'Game1LocationMarker',
        'PreviewForLocationId',
        'plugin:Activate(true)',
        'mouse.Button1Down',
        'syncedLocationIds',
    ]:
        if required not in location_plugin_text:
            report_error(f"m41 Studio Location authoring module missing {required}")
    for required in ['require(script.Parent.modules.LocationCommands)', 'data.command == "location-authoring"', 'model bridge v24']:
        if required not in studio_plugin_text:
            report_error(f"m41 Game1Bridge Location integration missing {required}")

    # m42 Location UI polish: structured editor fields, geometry state and action hierarchy.
    location_css_text = location_css_path.read_text(encoding="utf-8") if location_css_path.is_file() else ""
    for required in [
        "location-editor-section",
        "location-field",
        "location-geometry-summary",
        "location-action-zone",
        "location-empty",
    ]:
        if required not in location_js_text or required not in location_css_text:
            report_error(f"m42 Location UI structure missing {required}")
    for required in ["Location details", "Studio contour", "draw in Studio", "registry paths"]:
        if required not in location_js_text:
            report_error(f"m42 Location UI copy missing {required}")
