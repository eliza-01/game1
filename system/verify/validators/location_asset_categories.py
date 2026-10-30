"""Location Asset editor category and remembered navigation checks (M169)."""

from pathlib import Path
from typing import Callable

from .location_assets import LocationAssetSources


def check_location_asset_categories(root: Path, report_error: Callable[[str], None], *,
                                    sources: LocationAssetSources, character_js_text: str,
                                    studio_plugin_text: str, install_plugin_text: str) -> None:
    """Check M54/M55/M128 after the historical first error-exit boundary."""
    location_asset_store_text = sources.store_text
    index_m43_text = sources.index_text
    deco_assets_js_text = sources.assets_js
    deco_manager_text = sources.manager_text
    deco_placement_text = sources.placement_text
    # m54 Location Assets UX: create mode, remembered navigation/library category, named Roblox descriptions, new categories.
    for required in [
        "ASSET_MANAGER_VIEW_KEY='game1.assetManager.activeSection'",
        "window.addEventListener('load',restoreAssetManagerView)",
        "localStorage.setItem(ASSET_MANAGER_VIEW_KEY,view)",
    ]:
        if required not in character_js_text:
            report_error(f"m54 Asset Manager remembered section missing {required}")
    for required in [
        "DECO_LIBRARY_CATEGORY_KEY = 'game1.locationAssets.libraryCategory'",
        "DECO_SELECTED_ASSET_KEY = 'game1.locationAssets.selectedAsset'",
        "function decoAssetBeginNew()",
        "new-location-asset-main",
        "location-asset-library-category",
        "save asset changes",
    ]:
        if required not in deco_assets_js_text and required not in index_m43_text:
            report_error(f"m54 Location Assets UX missing {required}")
    for required in [
        'id="new-location-asset-main"',
        'id="location-asset-library-category"',
        'ladders</span>',
        'flowers</span>',
        'game1 location asset · Oak Tree',
    ]:
        if required not in index_m43_text:
            report_error(f"m54 Location Assets markup missing {required}")
    for required in [
        '"ladder": "Ladders"',
        '"flower": "Flowers"',
        'description = f"{description} · {asset_name}"',
    ]:
        if required not in location_asset_store_text:
            report_error(f"m54 LocationAssetStore missing {required}")
    for required in [
        'ladder = "Ladders"',
        'flower = "Flowers"',
        'local CATEGORY_ORDER = { "tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building", "prop" }',
        'local column = (index - 1) % 4',
    ]:
        if required not in deco_manager_text:
            report_error(f"m54 DecoManager category support missing {required}")
    for required in ['ladder = "Ladders"', 'flower = "Flowers"']:
        if required not in deco_placement_text:
            report_error(f"m54 DecoPlacement category folder missing {required}")
    if "model bridge v24" not in studio_plugin_text or "model bridge v24" not in install_plugin_text:
        report_error("m54 Studio plugin version marker must match current bridge")

    # m55 Location Assets: Buildings + synchronized editor/library category context.
    for required in [
        '"building": "Buildings"',
        'building = "Buildings"',
        'buildings</span>',
        'function decoAssetUseCategory(category',
        "$('location-asset-category').onchange",
    ]:
        if required not in location_asset_store_text and required not in deco_manager_text and required not in deco_placement_text and required not in index_m43_text and required not in deco_assets_js_text:
            report_error(f"m55 Buildings/category synchronization missing {required}")
    # m128 Props category is backed by the API, browser controls, and DecoManager.
    for required, source in [
        ('"prop": "Props"', location_asset_store_text),
        ('prop = "Props"', deco_manager_text),
        ('prop = "Props"', deco_placement_text),
        ('props</span>', index_m43_text),
        ('buildings · props</small>', index_m43_text),
    ]:
        if required not in source:
            report_error(f"m128 Location Assets Props integration missing {required}")

    if 'category filter<select id="location-asset-library-category"' not in index_m43_text:
        report_error("m55 library category filter label missing")
    if "decoAssetUseCategory($('location-asset-category').value, { updateEditor: false })" not in deco_assets_js_text:
        report_error("m55 editor category must synchronize library filter")
    if "decoAssetUseCategory(category);" not in deco_assets_js_text:
        report_error("m55 library category must synchronize editor category")
    if 'model bridge v24' not in studio_plugin_text or 'model bridge v24' not in install_plugin_text:
        report_error("m55 Studio plugin version marker must be v24")
