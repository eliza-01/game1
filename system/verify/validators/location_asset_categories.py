"""Location Asset editor category and remembered navigation checks (M169)."""

from pathlib import Path
from typing import Callable

from .location_assets import LocationAssetSources


def check_location_asset_categories(root: Path, report_error: Callable[[str], None], *,
                                    sources: LocationAssetSources, character_js_text: str,
                                    studio_plugin_text: str, install_plugin_text: str) -> None:
    """Validate M54/M55/M128 editor contracts before the final CLI exit."""
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
        'function decoAssetSaveEdits(',
        "function decoAssetBeginNew()",
        "new-location-asset-main",
        "location-asset-library-category",
        'location-asset-workflow.js?v=',
    ]:
        if required not in deco_assets_js_text and required not in index_m43_text:
            report_error(f"m54 Location Assets UX missing {required}")
    for required in [
        'id="new-location-asset-main"',
        'id="location-asset-library-category"',
        'Flora · tree · bush · flower · rock',
        'Structure · light · fence · ladder · bridge · pillar · post',
        'id="location-asset-editor-panel"',
        'Register new asset',
    ]:
        if required not in index_m43_text:
            report_error(f"m54 Location Assets markup missing {required}")
    # M220: the publication description belongs to the selected existing row,
    # not to an input in a create-only form. Both validations are independently
    # testable and must fail closed when removed.
    if "game1PublicationDescription('Location Asset',row.name_en)" not in deco_assets_js_text:
        report_error('m54 Location Assets publication name policy missing')
    if 'description:game1PublicationDescription(' not in deco_assets_js_text:
        report_error('m54 Location Assets publication payload missing description')
    for required in [
        'CATEGORIES = taxonomy.CATEGORIES',
        'CATEGORY_LABELS = taxonomy.CATEGORY_LABELS',
        "description = f'{description} · {asset_name}'",
    ]:
        if required not in location_asset_store_text:
            report_error(f"m54 LocationAssetStore missing {required}")
    for required in [
        'ladder="Ladder"',
        'flower="Flower"',
        'local CATEGORY_ORDER = { "tree", "bush", "flower", "rock",',
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
        'CATEGORY_LABELS = taxonomy.CATEGORY_LABELS',
        'building="Building"',
        'decoration · building</span>',
        'function decoAssetUseCategory(category',
        "$('location-asset-category').onchange",
    ]:
        if required not in location_asset_store_text and required not in deco_manager_text and required not in deco_placement_text and required not in index_m43_text and required not in deco_assets_js_text:
            report_error(f"m55 Buildings/category synchronization missing {required}")
    # m128 Props category is backed by the API, browser controls, and DecoManager.
    for required, source in [
        ('CATEGORIES = taxonomy.CATEGORIES', location_asset_store_text),
        ('prop="Prop"', deco_manager_text),
        ('prop = "Props"', deco_placement_text),
        ('Prop · prop · decoration · building', index_m43_text),
        ('flora · structure · prop', index_m43_text),
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
