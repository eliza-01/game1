"""Rojo Workspace authoring and Animation Speed UI contracts (M168)."""

import json
from pathlib import Path
from typing import Callable


def check_authoring_tooling(root: Path, report_error: Callable[[str], None]) -> None:
    """Read-only verification of live Rojo ownership and speed UI."""
    # m38 Rojo hotfix: live sync owns runtime code, not authored Workspace scene.
    live_project = json.loads((root / "default.project.json").read_text(encoding="utf-8"))
    workspace_node = ((live_project.get("tree") or {}).get("Workspace") or {})
    if workspace_node.get("$ignoreUnknownInstances") is not True:
        report_error("m38 live Rojo Workspace must preserve unknown/authored Studio instances")
    for forbidden in ["Baseplate", "SpawnLocation"]:
        if forbidden in workspace_node:
            report_error(f"m38 live Rojo must not own authored Workspace child {forbidden}")
    build_place_text = (root / "place/build-place.ps1").read_text(encoding="utf-8")
    for required in [".build-place.project.json", "Add-Member -NotePropertyName 'Baseplate'", "Add-Member -NotePropertyName 'SpawnLocation'", "Live Rojo will preserve authored Workspace children"]:
        if required not in build_place_text:
            report_error(f"m38 seed-place build isolation missing {required}")


    # m40 Asset Manager: Animation Speed is presented as one clear card per animation channel.
    animation_speed_ui_text = (root / "system/control-center/static/animation-speed.js").read_text(encoding="utf-8")
    animation_speed_css_text = (root / "system/control-center/static/asset-manager.css").read_text(encoding="utf-8")
    animation_speed_html_text = (root / "system/control-center/static/index.html").read_text(encoding="utf-8")
    for required in [
        "animation-speed-profile",
        "animation-speed-rule-grid",
        "animation-speed-rule",
        "Gameplay stat",
        "Stat units for +1% playback",
        "Playback formula",
        "Scales independently from Combat Idle",
    ]:
        if required not in animation_speed_ui_text and required not in animation_speed_css_text:
            report_error(f"m40 Animation Speed grouped UI missing {required}")
    for required in ["each animation block is configured independently", "Stat units for +1% playback"]:
        if required not in animation_speed_html_text:
            report_error(f"m40 Animation Speed help copy missing {required}")
