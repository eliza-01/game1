"""Location Asset texture formats, shared inheritance, and Deco placement (M169)."""

import re
from pathlib import Path
from typing import Callable

from .location_assets import LocationAssetSources


def check_location_asset_variants(root: Path, report_error: Callable[[str], None], *,
                                  sources: LocationAssetSources, host_agent_text: str,
                                  studio_plugin_text: str) -> None:
    """Check M44/M46/M47/M48/M49 invariants in original order."""
    location_asset_store_text = sources.store_text
    index_m43_text = sources.index_text
    deco_assets_js_text = sources.assets_js
    deco_manager_text = sources.manager_text
    deco_placement_text = sources.placement_text
    deco_loader_text = sources.loader_text
    # m44 Location Assets: PNG/JPG source textures with clean extension-aware preparation.
    for required in [
        'TEXTURE_SUFFIXES = (".png", ".jpg", ".jpeg")',
        'canonical_suffix = ".jpg" if source_suffix == ".jpeg" else source_suffix',
        "_retire_replaced_file",
        "PNG or JPG",
    ]:
        if required not in location_asset_store_text:
            report_error(f"m44 LocationAssetStore image format support missing {required}")
    for required in [
        "def choose_location_asset_texture()",
        "*.png;*.jpg;*.jpeg",
    ]:
        if required not in host_agent_text:
            report_error(f"m44 Location Asset texture picker missing {required}")
    if "choose_location_asset_png" in host_agent_text:
        report_error("m44 legacy PNG-only Location Asset picker remains")
    if "PNG/JPG" not in deco_assets_js_text or "PNG/JPG" not in index_m43_text:
        report_error("m44 Location Assets UI does not advertise PNG/JPG texture support")

    # m46 Location Assets: Decorations category + shared registered texture references.
    for required in [
        'SCHEMA_VERSION = 4',
        '"decoration": "Decorations"',
        'texture_reference_slug TEXT NOT NULL DEFAULT',
        'def _resolve_texture_owner',
        'textureReferenceSlug',
        'texture_owner_slug',
        'texture_shared',
        'shared texture owner',
        'texture is reused by location assets',
    ]:
        if required not in location_asset_store_text:
            report_error(f"m46 shared Location Asset texture support missing {required}")
    for required in [
        'id="location-asset-texture-reference"',
        'decorations</span>',
        'atlas variant',
    ]:
        if required not in index_m43_text:
            report_error(f"m46 Location Assets UI missing {required}")
    for required in [
        'textureReferenceSlug',
        'decoAssetRenderTextureReferences',
        'location-asset-texture-reference',
        'reuse a registered texture',
    ]:
        if required not in deco_assets_js_text:
            report_error(f"m46 Location Assets shared-texture UI behavior missing {required}")
    for required in [
        'decoration = "Decorations"',
        'ladder = "Ladders"',
        'flower = "Flowers"',
        'local CATEGORY_ORDER = { "tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building", "prop" }',
        'local row = math.floor((index - 1) / 4)',
    ]:
        if required not in deco_manager_text:
            report_error(f"m46 DecoManager Decorations category missing {required}")
    if 'decoration = "Decorations"' not in deco_placement_text:
        report_error("m46 DecoPlacement Decorations folder mapping is missing")
    if "model bridge v24" not in studio_plugin_text:
        report_error("m46 Studio plugin version marker is stale")


    # m47 DecoManager: transient placement sessions never reuse/destroy the manager template.
    for required in [
        'sourceTemplate = nil',
        'function DecoPlacement:_detachSession()',
        'self.plugin:Activate(true)',
        'ghost.Parent = if camera ~= nil then camera else self.Workspace',
        'local placed = sourceTemplate:Clone()',
        'self.committing = true',
    ]:
        if required not in deco_placement_text:
            report_error(f"m47 DecoPlacement lifecycle hotfix missing {required}")
    if 'self.template:Destroy()' in deco_placement_text:
        report_error("m47 DecoPlacement still destroys a placement-owned template clone")
    for required in [
        'descendant:IsA("AnimationController")',
        'descendant:IsA("Animator")',
        'descendant.Name == "InitialPoses"',
    ]:
        if required not in deco_loader_text:
            report_error(f"m47 static Location Asset sanitization missing {required}")
    if "model bridge v24" not in studio_plugin_text:
        report_error("m47 Studio plugin version marker is stale")


    # m48 DecoManager: preserve the imported FBX/model pivot basis in preview and placement.
    deco_transform_path = root / "system/studio-plugin/modules/DecoTransform.luau"
    if not deco_transform_path.exists():
        report_error("m48 DecoTransform module is missing")
    else:
        deco_transform_text = deco_transform_path.read_text(encoding="utf-8")
        for required in [
            "function DecoTransform.authoredPivotRotation",
            "function DecoTransform.previewPivot",
            "function DecoTransform.supportOffset",
            "function DecoTransform.placementPivot",
            "surfaceFrame(surfaceNormal, cameraLook) * authoredPivotRotation",
        ]:
            if required not in deco_transform_text:
                report_error(f"m48 DecoTransform missing {required}")
    for required in [
        "local DecoTransform = require(script.Parent.DecoTransform)",
        "DecoTransform.supportOffset(template)",
        "DecoTransform.authoredPivotRotation(template)",
        "DecoTransform.placementPivot(",
    ]:
        if required not in deco_placement_text:
            report_error(f"m48 DecoPlacement authored-basis handling missing {required}")
    for removed in ["localSupportOffset", "orientationForSurface"]:
        if removed in deco_placement_text:
            report_error(f"m48 DecoPlacement still contains obsolete transform helper {removed}")
    if "model:PivotTo(DecoTransform.previewPivot(model))" not in deco_manager_text:
        report_error("m48 DecoManager preview still replaces the imported asset basis")
    if '"DecoTransform"' not in (root / "system/studio-plugin/plugin.project.json").read_text(encoding="utf-8"):
        report_error("m48 Studio plugin project does not include DecoTransform")
    if "model bridge v24" not in studio_plugin_text:
        report_error("m48 Studio plugin version marker is stale")


    # m49 DecoManager: placed decoration instances stay unanchored for manual Studio editing.
    if 'descendant.Anchored = false' not in deco_placement_text:
        report_error("m49 DecoPlacement must leave placed decoration BaseParts unanchored")
    prepare_placed_match = re.search(r'local function preparePlaced\(model: Model\)(.*?)\nend', deco_placement_text, re.S)
    if prepare_placed_match is None:
        report_error("m49 DecoPlacement preparePlaced helper is missing")
    elif 'Anchored = true' in prepare_placed_match.group(1):
        report_error("m49 DecoPlacement still anchors placed decoration BaseParts")
