"""Read-only contracts for Studio Test Loadout and Movement Debug (M168)."""

from pathlib import Path
from typing import Callable


def check_studio_debug(root: Path, report_error: Callable[[str], None], *,
                       plugin_text: str, stats_service_text: str,
                       client_init_text: str) -> str:
    """Check developer tooling and return the shared server bootstrap text."""
    # m6.2 Studio-native Test Loadout (ported from the reference architecture)
    test_loadout_server_path = root / "src/server/dev/TestLoadoutService.luau"
    test_loadout_client_path = root / "src/client/dev/TestLoadoutController.luau"
    test_loadout_server = test_loadout_server_path.read_text(encoding="utf-8") if test_loadout_server_path.is_file() else ""
    test_loadout_client = test_loadout_client_path.read_text(encoding="utf-8") if test_loadout_client_path.is_file() else ""
    for required in ["GetTestLoadoutCatalog", "ApplyTestLoadout", "CharacterService.Respawn", "WeaponEquipService.Equip", "Game1TestLoadoutActive"]:
        if required not in test_loadout_server:
            report_error(f"Studio Test Loadout server missing {required}")
    for required in ["TEST LOADOUT", "createDropdown", "createCategorySelector", "LastLoadoutArchetype", "LastLoadoutWeaponSlug", "ACCEPT LOADOUT", "PublishedDebugAccess.ClientAllowed()"]:
        if required not in test_loadout_client:
            report_error(f"Studio Test Loadout client missing {required}")
    for required in ["ATTACK RADIUS: OFF", "MeleeArcPreview.new()", "ringPreview:SetVisible(ringVisible)", 'currentCharacter:GetAttribute("AttackRadius")']:
        if required not in test_loadout_client:
            report_error(f"Studio Test Loadout attack-radius preview missing {required}")
    preview_path = root / "src/client/dev/MeleeArcPreview.luau"
    preview = preview_path.read_text(encoding="utf-8") if preview_path.is_file() else ""
    for required in ["Game1AttackRadiusPreview", "RootCollider", "MeleeArcDebugAnchor", "Beam", "CanQuery = false", "SetVisible", "Destroy"]:
        if required not in preview:
            report_error(f"Studio Melee Arc preview module missing {required}")
    if "attackRadiusStuds" not in test_loadout_server:
        report_error("Studio Test Loadout catalog must expose the registered weapon attack radius")
    server_init_text = (root / "src/server/init.server.luau").read_text(encoding="utf-8") + (root / "src/server/bootstrap/ServiceCatalog.luau").read_text(encoding="utf-8")
    if "TestLoadoutService.Start()" not in server_init_text:
        report_error("Studio Test Loadout service is not started by the server runtime")
    if "TestLoadoutController.Start()" not in client_init_text:
        report_error("Studio Test Loadout controller is not started by the client runtime")
    for required in ["Game1StudioDebugPreferences_v1", "Game1StudioPreferences", "plugin:GetSetting", "plugin:SetSetting", "LastLoadoutArchetype", "LastLoadoutWeaponSlug", "ClientPreferencesReady"]:
        if required not in plugin_text:
            report_error(f"game1 Studio plugin loadout preference bridge missing {required}")
    if (root / "src/shared/dev/TestLoadoutConfig.luau").exists():
        report_error("obsolete generated TestLoadoutConfig must be removed")

    # M558: retired runtime-only debug panels must not ship.
    for name in ("MovementDebug", "MonsterDebug"):
        for side, suffix in (("server", "Service"), ("client", "Controller")):
            path = root / f"src/{side}/dev/{name}{suffix}.luau"
            if path.exists():
                report_error(f"retired debug module still exists: {name}{suffix}")
        if name in server_init_text or name in client_init_text:
            report_error(f"retired debug startup: {name}")
    movement_config_text = (root / "src/shared/character/CharacterMovementConfig.luau").read_text(encoding="utf-8")
    for required in [
        "RunSpeedUnitsPerStud = 10",
        "WalkSpeedMultiplier = 0.5",
        "function CharacterMovementConfig.RobloxSpeed",
        "/ CharacterMovementConfig.RunSpeedUnitsPerStud",
        "function CharacterMovementConfig.RunSpeedFromStudsPerSecond",
    ]:
        if required not in movement_config_text:
            report_error(f"game-speed/world-distance conversion contract missing {required}")
    return server_init_text
