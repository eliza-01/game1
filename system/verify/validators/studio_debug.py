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
    for required in ["TEST LOADOUT", "createDropdown", "createCategorySelector", "LastLoadoutArchetype", "LastLoadoutWeaponSlug", "ACCEPT LOADOUT", "RunService:IsStudio()"]:
        if required not in test_loadout_client:
            report_error(f"Studio Test Loadout client missing {required}")
    for required in ["ATTACK RADIUS: OFF", "Game1AttackRadiusPreview", "createAttackRadiusRing", 'currentCharacter:GetAttribute("AttackRadius")', "RunService.RenderStepped"]:
        if required not in test_loadout_client:
            report_error(f"Studio Test Loadout attack-radius preview missing {required}")
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

    # m20 Studio-native movement debugger: AM-seeded, runtime-editable tuning
    movement_debug_server_path = root / "src/server/dev/MovementDebugService.luau"
    movement_debug_client_path = root / "src/client/dev/MovementDebugController.luau"
    movement_debug_server = movement_debug_server_path.read_text(encoding="utf-8") if movement_debug_server_path.is_file() else ""
    movement_debug_client = movement_debug_client_path.read_text(encoding="utf-8") if movement_debug_client_path.is_file() else ""
    for required in [
        "GetMovementDebugCatalog",
        "ApplyMovementDebug",
        "SetMovementDebugMonsterMode",
        "MovementDebugRunSpeedOverride",
        "applyRuntimeRunSpeed",
        "baseRunSpeed",
        "animationUnitsPerPercent",
        "animationChannel",
        "authoredUnitsPerPercent",
        "animationRules",
        "runSpeedUnitsPerStud",
        "CharacterMovementConfig.RobloxSpeed",
        "model = model",
        "Game1MonsterDebugLocomotionMode",
        "MonsterLocomotionMode",
        "RunService:IsStudio()",
    ]:
        if required not in movement_debug_server:
            report_error(f"Studio movement debugger server missing {required}")
    for required in [
        "MOVEMENT DEBUG",
        "RunSpeed · runtime test value",
        "Run world speed · studs / second",
        "Animation ratio · stat units per 1% playback",
        "RULE: RUN",
        "AM RunSpeed",
        "runtime test",
        "ACTIVE",
        "calculatedPlayback",
        "animationUnitsPerPercent",
        "ApplyMovementDebug",
        "stageSpeedText",
        "stageAnimationText",
        "MONSTER BASE: WALK",
        "MEASURED · last 1.0 s",
        "modelPosition",
        "RunService.Heartbeat:Connect",
        "GetMovementDebugCatalog",
        "SetMovementDebugMonsterMode",
        "CATALOG_POLL_SECONDS",
        "RunService:IsStudio()",
    ]:
        if required not in movement_debug_client:
            report_error(f"Studio movement debugger client missing {required}")
    for forbidden in ["animationSpeedPercent =", "MovementDebugAnimationSpeedPercentOverride"]:
        if forbidden in movement_debug_server or forbidden in movement_debug_client:
            report_error(f"Movement Debug must tune AM ratio, never own an absolute playback-percent override; found {forbidden}")
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
    if "MovementDebugRunSpeedOverride" not in stats_service_text:
        report_error("character stats must preserve the runtime Movement Debug RunSpeed override across stat recomputes")
    if "MovementDebugService.Start()" not in server_init_text:
        report_error("Studio movement debugger service is not started by the server runtime")
    if "MovementDebugController.Start()" not in client_init_text:
        report_error("Studio movement debugger controller is not started by the client runtime")
    return server_init_text
