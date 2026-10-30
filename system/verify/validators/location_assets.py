"""Read-only Location Asset registry, publication and DecoManager base contracts (M169)."""

import json
from pathlib import Path
from typing import Callable, NamedTuple


class LocationAssetSources(NamedTuple):
    manifest_path: Path
    store_text: str
    layout_store_text: str
    index_text: str
    assets_js: str
    assets_css: str
    loader_text: str
    placement_text: str
    manager_text: str
    plugin_project_text: str


def check_location_assets_core(root: Path, report_error: Callable[[str], None], *,
                               host_agent_text: str, studio_plugin_text: str) -> LocationAssetSources:
    """Validate M43 registry / DecoManager and return immutable source snapshot."""
    # m43 Location Assets: weapon-style FBX+PNG publication and modular Studio DecoManager.
    location_asset_manifest_path = root / "assets/manifests/location-assets.json"
    location_asset_registry_path = root / "src/shared/world/LocationAssetRegistry.luau"
    location_asset_store_path = root / "system/control-center/location_asset_store.py"
    deco_layout_store_path = root / "system/control-center/deco_layout_store.py"
    deco_assets_js_path = root / "system/control-center/static/deco-assets.js"
    deco_assets_css_path = root / "system/control-center/static/deco-assets.css"
    deco_loader_path = root / "system/studio-plugin/modules/DecoAssetLoader.luau"
    deco_manager_path = root / "system/studio-plugin/modules/DecoManager.luau"
    deco_placement_path = root / "system/studio-plugin/modules/DecoPlacement.luau"
    for path in [
        location_asset_manifest_path,
        location_asset_registry_path,
        location_asset_store_path,
        deco_layout_store_path,
        deco_assets_js_path,
        deco_assets_css_path,
        deco_loader_path,
        deco_manager_path,
        deco_placement_path,
    ]:
        if not path.is_file():
            report_error(f"m43 Location Assets / DecoManager file missing: {path.relative_to(root)}")

    if location_asset_manifest_path.is_file():
        location_asset_manifest = json.loads(location_asset_manifest_path.read_text(encoding="utf-8"))
        if location_asset_manifest.get("schemaVersion") != 4 or location_asset_manifest.get("project") != "game1":
            report_error("m43 location-assets.json schema/project is invalid")
        category_ids = [row.get("id") for row in ((location_asset_manifest.get("options") or {}).get("categories") or [])]
        # Generated manifests may still have the previous category set until
        # the first Control Center startup re-exports them from LocationAssetStore.
        expected_categories = ["tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building"]
        if category_ids not in (expected_categories, expected_categories + ["prop"]):
            report_error("m128 Location Assets manifest categories have invalid canonical order")

    location_asset_store_text = location_asset_store_path.read_text(encoding="utf-8") if location_asset_store_path.is_file() else ""
    for required in [
        "class LocationAssetStore",
        'CATEGORIES = ("tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building", "prop")',
        "assets/source/location-assets",
        "model_path TEXT NOT NULL DEFAULT ''",
        "texture_path TEXT NOT NULL DEFAULT ''",
        "create_model_asset",
        "update_model_asset",
        "create_image_asset",
        'return "PUBLISHED"',
        "LocationAssetRegistry.luau",
    ]:
        if required not in location_asset_store_text:
            report_error(f"m43 LocationAssetStore missing {required}")

    deco_layout_store_text = deco_layout_store_path.read_text(encoding="utf-8") if deco_layout_store_path.is_file() else ""
    for required in [
        "class DecoLayoutStore",
        "assets/backups/deco-layouts",
        "deco-layout-latest.json",
        '"cframe"',
        '"scale"',
    ]:
        if required not in deco_layout_store_text:
            report_error(f"m43 DecoLayoutStore missing {required}")

    for required in [
        'path == "/api/location-assets"',
        'path == "/api/files/choose-location-asset-model"',
        'path == "/api/files/choose-location-asset-texture"',
        'path == "/api/location-assets/layout"',
        'location_assets.publish',
        'location_assets.delete',
        'game1-m50-environment-weapon-bounce-001',
    ]:
        if required not in host_agent_text:
            report_error(f"m43 host agent Location Assets API missing {required}")

    index_m43_text = (root / "system/control-center/static/index.html").read_text(encoding="utf-8")
    deco_assets_js_text = deco_assets_js_path.read_text(encoding="utf-8") if deco_assets_js_path.is_file() else ""
    deco_assets_css_text = deco_assets_css_path.read_text(encoding="utf-8") if deco_assets_css_path.is_file() else ""
    for required in [
        'id="nav-location-assets"',
        'id="location-assets-view"',
        'id="location-asset-category"',
        'id="choose-location-asset-model"',
        'id="choose-location-asset-texture"',
        'id="publish-location-asset"',
        'deco-assets.css?v=',
        'deco-assets.js?v=',
    ]:
        if required not in index_m43_text:
            report_error(f"m43 Asset Manager Location Assets section missing {required}")
    for required in [
        "/api/location-assets",
        "/api/files/choose-location-asset-model",
        "/api/files/choose-location-asset-texture",
        "decoAssetPublish",
        "window.game1LocationAssetsLoad",
    ]:
        if required not in deco_assets_js_text:
            report_error(f"m43 Location Assets UI behavior missing {required}")
    for required in ["deco-asset-workflow", "deco-source-pickers", "deco-tree-group"]:
        if required not in deco_assets_css_text:
            report_error(f"m43 Location Assets UI styling missing {required}")

    plugin_project_text = (root / "system/studio-plugin/plugin.project.json").read_text(encoding="utf-8")
    for required in ["DecoAssetLoader", "DecoPlacement", "DecoManager"]:
        if required not in plugin_project_text:
            report_error(f"m43 Studio plugin project is missing module {required}")

    deco_loader_text = deco_loader_path.read_text(encoding="utf-8") if deco_loader_path.is_file() else ""
    for required in [
        'self.AssetService:LoadAssetAsync(assetId)',
        'row.status or ""',
        'StudioTextureAppearance.Apply(descendant, uri, usesAlpha)',
        'Url = self.agentBaseUrl .. "/api/location-assets"',
    ]:
        if required not in deco_loader_text:
            report_error(f"m43 DecoAssetLoader missing {required}")

    deco_placement_text = deco_placement_path.read_text(encoding="utf-8") if deco_placement_path.is_file() else ""
    for required in [
        'ROOT_NAME = "Game1DecoAssets"',
        'tree = "Trees"',
        'bush = "Bushes"',
        'rock = "Rocks"',
        'light = "Lights"',
        'fence = "Fences"',
        'decoration = "Decorations"',
        'ladder = "Ladders"',
        'flower = "Flowers"',
        "Workspace:Raycast",
        "self.plugin:Activate(true)",
        'placed:SetAttribute("Game1DecoAssetSlug", tostring(row.slug or ""))',
        "function DecoPlacement:serialize()",
        "DecoTransform.supportOffset",
        "DecoTransform.placementPivot",
    ]:
        if required not in deco_placement_text:
            report_error(f"m43 DecoPlacement missing {required}")

    deco_manager_text = deco_manager_path.read_text(encoding="utf-8") if deco_manager_path.is_file() else ""
    for required in [
        'CreateDockWidgetPluginGui("Game1DecoManager_v1"',
        'self.widget.Title = "game1 · DecoManager"',
        'Instance.new("ViewportFrame")',
        'Instance.new("WorldModel")',
        'DecoPreviewWorld',
        '"Save Assets Data"',
        'self.agentBaseUrl .. "/api/location-assets/layout"',
        'local CATEGORY_ORDER = { "tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building", "prop" }',
    ]:
        if required not in deco_manager_text:
            report_error(f"m43 DecoManager missing {required}")

    for required in [
        'require(script.Parent.modules.DecoManager)',
        'DecoManager.new({',
        'model bridge v24',
    ]:
        if required not in studio_plugin_text:
            report_error(f"m43 Game1Bridge DecoManager integration missing {required}")
    for forbidden in ["game:SavePlace(", "SavePlace(Enum.SaveFilter", "SavePlaceAsync"]:
        if forbidden in deco_manager_text:
            report_error(f"m45 obsolete direct place-save path remains in DecoManager: {forbidden}")

    return LocationAssetSources(
        manifest_path=location_asset_manifest_path,
        store_text=location_asset_store_text,
        layout_store_text=deco_layout_store_text,
        index_text=index_m43_text,
        assets_js=deco_assets_js_text,
        assets_css=deco_assets_css_text,
        loader_text=deco_loader_text,
        placement_text=deco_placement_text,
        manager_text=deco_manager_text,
        plugin_project_text=plugin_project_text,
    )
