"""Location Asset published image replacement and Studio texture refresh (M169)."""

from pathlib import Path
from typing import Callable

from .location_assets import LocationAssetSources


def check_location_texture_sync(root: Path, report_error: Callable[[str], None], *,
                                sources: LocationAssetSources,
                                environment_asset_service_text: str) -> None:
    """Preserve M51 publication-identity and hydration checks."""
    location_asset_store_text = sources.store_text
    index_m43_text = sources.index_text
    deco_assets_js_text = sources.assets_js
    deco_manager_text = sources.manager_text
    plugin_project_text = sources.plugin_project_text
    # M203: texture replacement/publication belongs to AtlasRegistry, not
    # LocationAssetStore. Studio refresh still consumes published image IDs.
    for required in [
        'self.atlases.ensure_published',
        "self.atlases.binding('location_asset'",
        "'atlasVariantId'",
    ]:
        if required not in location_asset_store_text:
            report_error(f"m203 Location Assets atlas publication delegation missing {required}")
    for forbidden in ('create_image_asset(', 'update_image_asset(', 'retained_textures.retain'):
        if forbidden in location_asset_store_text:
            report_error(f"m203 Location Assets still own image publication: {forbidden}")
    deco_placed_sync_path = root / "system/studio-plugin/modules/DecoPlacedAssetSync.luau"
    environment_visuals_path = root / "src/server/world/EnvironmentAssetVisuals.luau"
    for path in (deco_placed_sync_path, environment_visuals_path):
        if not path.is_file():
            report_error(f"m51 texture synchronization module missing: {path.relative_to(root)}")
    deco_placed_sync_text = deco_placed_sync_path.read_text(encoding='utf-8') if deco_placed_sync_path.is_file() else ''
    environment_visuals_text = environment_visuals_path.read_text(encoding='utf-8') if environment_visuals_path.is_file() else ''
    workflow_file = root / 'system/control-center/static/location-asset-workflow.js'
    workflow = workflow_file.read_text(encoding='utf-8') if workflow_file.is_file() else ''
    shared_atlas = (root/'system/control-center/static/asset-atlas-editor.js').read_text(encoding='utf-8')
    if not ('game1ConsumerAtlasEditor' in workflow and 'Image ID' in shared_atlas and
            'decoAssetPublish' in workflow and 'texture_asset_id' in deco_assets_js_text):
        report_error('m51 published texture feedback missing')
    for required in ["Game1DecoAssetSlug", "StudioTextureAppearance.Apply(change.part, uri, nil, true)", "RefreshIds"]:
        if required not in deco_placed_sync_text:
            report_error(f"m51 DecoManager placed-texture sync missing {required}")
    for required in ["DecoPlacedAssetSync.RefreshIds", "Before Location Asset Model + Atlas Sync", "Location Asset Model + Atlas Sync"]:
        if required not in deco_manager_text:
            report_error(f"m51 DecoManager registry refresh integration missing {required}")
    if '"DecoPlacedAssetSync"' not in plugin_project_text:
        report_error("m51 Studio plugin project is missing DecoPlacedAssetSync")
    # Runtime cannot read/write SurfaceAppearance.ColorMap (Plugin capability).
    # The Studio texture adapter alone owns SurfaceAppearance and alpha authoring.
    for required in ["textureAssetId", "mesh.TextureID = uri", 'FindFirstChildOfClass("SurfaceAppearance")', "ApplyModel", "ApplyPart"]:
        if required not in environment_visuals_text:
            report_error(f"m51 runtime environment texture hydration missing {required}")
    if "surface.ColorMap" in environment_visuals_text or "surface.AlphaMode" in environment_visuals_text:
        report_error("m51 runtime environment binder must not access Plugin-only SurfaceAppearance properties")
    for required in ["EnvironmentAssetVisuals.ApplyModel", "EnvironmentAssetVisuals.ApplyPart"]:
        if required not in environment_asset_service_text:
            report_error(f"m51 EnvironmentAssetService visual hydration missing {required}")
