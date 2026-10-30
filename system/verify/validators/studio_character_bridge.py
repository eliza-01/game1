"""Read-only Studio character import, authored basis and sync bridge contracts (M170)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, NamedTuple


class StudioCharacterBridgeSources(NamedTuple):
    plugin_text: str
    host_agent_text: str


def check_studio_character_bridge(ROOT: Path, err: Callable[[str], None]):
    bridge = ROOT / "system/control-center/studio_bridge.py"
    plugin = ROOT / "system/studio-plugin/Game1Bridge.server.luau"
    template_module = ROOT / "system/studio-plugin/modules/CharacterTemplate.luau"
    if not bridge.is_file() or "run_model_load_bridge" not in bridge.read_text(encoding="utf-8"):
        err("reference-style Studio model load bridge is missing")
    plugin_text = plugin.read_text(encoding="utf-8") if plugin.is_file() else ""
    # M100: model import and Studio preference contracts reside in packaged modules.
    plugin_text += "\n" + "\n".join(
        (ROOT / "system/studio-plugin/modules" / name).read_text(encoding="utf-8")
        for name in ("StudioModelLoadCommands.luau", "StudioActorSpawnCommands.luau", "StudioDebugPreferenceBridge.luau")
    )
    template_text = template_module.read_text(encoding="utf-8") if template_module.is_file() else ""
    for required in ["AssetService:LoadAssetAsync", "ImportedRig", "AnimationController", "Game1CharacterRig", "CharacterTemplate.EnsureCanonicalRoot"]:
        if required not in plugin_text:
            err(f"game1 Studio character bridge missing {required}")
    for required in ["ImportedRigRootWeld", "Game1GeneratedCharacterRoot", "Game1TemplateBasisMode", "Game1RigBasisMode", "authored_basis"]:
        if required not in template_text:
            err(f"game1 Studio character template module missing {required}")
    for forbidden in [
        "normalizeSkeletonOrientation",
        "resolveSkeletonUp",
        "head_to_feet",
        "spine_to_feet",
        "importedRig:PivotTo(",
    ]:
        if forbidden in template_text:
            err(f"Studio rig sync must preserve authored FBX basis; forbidden orientation correction remains: {forbidden}")
    if 'BRIDGE_URL = "http://127.0.0.1:43137"' not in plugin_text:
        err("game1 Studio bridge must use isolated port 43137")
    plugin_project = ROOT / "system/studio-plugin/plugin.project.json"
    plugin_project_text = plugin_project.read_text(encoding="utf-8") if plugin_project.is_file() else ""
    if '"$path": "modules/CharacterTemplate.luau"' not in plugin_project_text:
        err("game1 Studio plugin project must package the character template module")

    host_agent_text = (ROOT / "system/control-center/host_agent.py").read_text(encoding="utf-8") + "\n" + "\n".join(p.read_text(encoding="utf-8") for folder in ("api", "services") for p in (ROOT / "system/control-center" / folder).glob("*.py"))
    if "sync_character_to_studio" not in host_agent_text or 'sync_suffix = "/sync"' not in host_agent_text:
        err("character publication must expose reference-style Studio sync")

    return StudioCharacterBridgeSources(plugin_text, host_agent_text)
