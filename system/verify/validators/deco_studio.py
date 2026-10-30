"""Studio-native DecoManager save and preview interaction validation (M169)."""

from pathlib import Path
from typing import Callable

from .location_assets import LocationAssetSources


def check_deco_studio(root: Path, report_error: Callable[[str], None], *,
                      sources: LocationAssetSources, host_agent_text: str,
                      studio_plugin_text: str) -> None:
    """Preserve M45 save/preview diagnostics at their original position."""
    deco_manager_text = sources.manager_text
    # m45 DecoManager hotfix: Studio-native local-place save and strict LMB preview drag.
    studio_save_path = root / "system/control-center/studio_save.py"
    if not studio_save_path.is_file():
        report_error("m45 Studio-native save helper is missing")
    else:
        studio_save_text = studio_save_path.read_text(encoding="utf-8")
        for required in [
            "request_active_studio_save",
            "studio-native-ctrl-s",
            "Roblox Studio must be the active window",
            "keybd_event(_VK_CONTROL",
        ]:
            if required not in studio_save_text:
                report_error(f"m45 Studio-native save helper missing {required}")

    for required in [
        "from studio_save import request_active_studio_save",
        'control_agent_build = "game1-m50-environment-weapon-bounce-001"',
        'result["studioSave"] = request_active_studio_save()',
    ]:
        if required not in host_agent_text:
            report_error(f"m45 host agent save bridge missing {required}")

    for required in [
        "self.viewport.MouseLeave:Connect",
        "self.viewport.InputEnded:Connect",
        "self.previewDragging = false",
        "Studio save requested",
    ]:
        if required not in deco_manager_text:
            report_error(f"m45 DecoManager drag/save hotfix missing {required}")
    if "self.AssetService:SavePlaceAsync" in deco_manager_text:
        report_error("m45 DecoManager still calls cloud SavePlaceAsync directly")
    if "model bridge v24" not in studio_plugin_text:
        report_error("m45 Studio plugin version marker is stale")
