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
    # m51 Location Assets: changed owned textures get a fresh Roblox Image Asset ID.
    deco_placed_sync_path = root / "system/studio-plugin/modules/DecoPlacedAssetSync.luau"
    environment_visuals_path = root / "src/server/world/EnvironmentAssetVisuals.luau"
    for path in [deco_placed_sync_path, environment_visuals_path]:
        if not path.is_file():
            report_error(f"m51 texture synchronization module missing: {path.relative_to(root)}")
    deco_placed_sync_text = deco_placed_sync_path.read_text(encoding="utf-8") if deco_placed_sync_path.is_file() else ""
    environment_visuals_text = environment_visuals_path.read_text(encoding="utf-8") if environment_visuals_path.is_file() else ""
    for required in [
        "legacy_texture_updates",
        "COUNT(DISTINCT publication.sha256)>1",
        "texture_replaced =",
        "replacement is identity-changing for Location Assets by design",
        "operation = create_image_asset(",
    ]:
        if required not in location_asset_store_text:
            report_error(f"m51 Location Asset replacement publication missing {required}")
    if "update_image_asset" in location_asset_store_text:
        report_error("m51 Location Assets still contain legacy in-place Image Asset updates")
    for required in [
        "central atlas reuse never does",
        "texture ${published.texture_asset_id || '—'}",
    ]:
        if required not in (index_m43_text + deco_assets_js_text):
            report_error(f"m51 Location Assets UI publication identity missing {required}")
    for required in ["Game1DecoAssetSlug", "StudioTextureAppearance.Apply(part, uri, row.textureUsesAlpha)", "RefreshTextures"]:
        if required not in deco_placed_sync_text:
            report_error(f"m51 DecoManager placed-texture sync missing {required}")
    for required in ["DecoPlacedAssetSync.RefreshTextures", "Refresh Deco Asset Textures"]:
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
