"""Read-only project identity, namespace, and source layout checks.

Checks run in two phases because the character archetype manifest is validated
between them by the legacy verifier.  Keeping both call sites in place retains
strictly the same error order and compatibility contract.
"""

import json
from pathlib import Path
from typing import Callable


REQUIRED_RUNTIME_MODULES = (
    "src/server/character/CharacterService.luau",
    "src/server/character/CharacterRigService.luau",
    "src/server/character/CharacterStatsService.luau",
    "src/server/combat/AttackService.luau",
    "src/server/combat/DamageService.luau",
    "src/server/combat/EntityHitboxService.luau",
    "src/server/dev/TrainingDummyService.luau",
    "src/server/dev/MovementDebugService.luau",
    "src/server/monster/MonsterSpawnerService.luau",
    "src/server/monster/MonsterPopulationController.luau",
    "src/server/monster/MonsterRigBuilder.luau",
    "src/server/monster/MonsterSpawnGeometry.luau",
    "src/server/monster/MonsterAnimationTrackFactory.luau",
    "src/server/monster/MonsterInitialAttributes.luau",
    "src/server/monster/MonsterSpawnRegistry.luau",
    "src/client/character/MovementController.luau",
    "src/client/character/CameraController.luau",
    "src/client/character/PlayerStatusController.luau",
    "src/client/character/animation/AnimationResolver.luau",
    "src/client/character/animation/AnimationTrackCache.luau",
    "src/client/character/animation/AttackUpperBodyComposer.luau",
    "src/client/character/animation/CharacterAnimationController.luau",
    "src/client/combat/AttackController.luau",
    "src/client/combat/AimPoseController.luau",
    "src/client/dev/MovementDebugController.luau",
    "src/shared/character/CharacterConfig.luau",
    "src/shared/character/CharacterMovementConfig.luau",
    "src/shared/character/CharacterRegistry.luau",
    "src/shared/character/CharacterAnimationRegistry.luau",
    "src/shared/character/CharacterStatsConfig.luau",
    "src/shared/animation/AnimationSpeedScaling.luau",
    "src/shared/animation/AnimationScalingFormula.luau",
    "src/shared/animation/AnimationScalingPolicy.luau",
    "src/shared/animation/AnimationScalingDebugOverrides.luau",
    "src/shared/animation/AnimationSpeedScalingRegistry.luau",
    "src/shared/combat/AttackConfig.luau",
    "src/shared/combat/AttackTimelineConfig.luau",
    "src/shared/combat/CharacterAttackWindow.luau",
    "src/shared/combat/SkeletonHeadResolver.luau",
)


LEGACY_RUNTIME_MODULES = (
    "src/server/CharacterService.luau",
    "src/server/AttackService.luau",
    "src/server/DamageService.luau",
    "src/server/TrainingDummyService.luau",
    "src/shared/CharacterRegistry.luau",
    "src/shared/CharacterConfig.luau",
    "src/shared/AttackConfig.luau",
)


def check_project_identity(root: Path, report_error: Callable[[str], None]) -> None:
    """Validate the isolated game1 project identity and Rojo tree."""
    if "robloxlineage" in str(root).lower():
        report_error("game1 root is inside/a descendant of a robloxlineage path")

    project = json.loads((root / "default.project.json").read_text(encoding="utf-8"))
    if project.get("name") != "game1":
        report_error("default.project.json project name must be game1")

    tree = project.get("tree", {})
    try:
        if "Game1Shared" not in tree["ReplicatedStorage"]:
            report_error("Game1Shared namespace missing")
        if "Game1Server" not in tree["ServerScriptService"]:
            report_error("Game1Server namespace missing")
        if "Game1Client" not in tree["StarterPlayer"]["StarterPlayerScripts"]:
            report_error("Game1Client namespace missing")
    except (KeyError, TypeError):
        report_error("default.project.json namespace tree is malformed")


def check_project_layout(root: Path, report_error: Callable[[str], None]) -> None:
    """Validate author-owned place, namespace isolation, ports, and runtime paths."""
    if (root / "place/current.rbxl").exists():
        report_error("place/current.rbxl is forbidden in game1; canonical file is place/game1.rbxl")

    scan = [
        root / "src",
        root / "assets/manifests",
        root / "system/control-center",
        root / "system/asset-manager",
        root / "config",
    ]
    for base in scan:
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".luau", ".lua", ".py", ".json", ".yaml", ".yml"}:
                text = path.read_text(encoding="utf-8", errors="ignore")
                for token in [
                    "RobloxLineageShared",
                    "RobloxLineageServer",
                    "RobloxLineageClient",
                    "NewPlaceShared",
                    "NewPlaceServer",
                    "NewPlaceClient",
                    "Interlude",
                    "CombatV2",
                ]:
                    if token in text:
                        report_error(f"{path.relative_to(root)} contains forbidden token {token}")

    cfg = json.loads((root / "config/project.json").read_text(encoding="utf-8"))
    if cfg.get("name") != "game1" or cfg.get("slug") != "game1":
        report_error("config/project.json identity must be game1")
    expected_namespaces = {"shared": "Game1Shared", "server": "Game1Server", "client": "Game1Client", "remotes": "Game1Remotes"}
    if cfg.get("namespaces") != expected_namespaces:
        report_error("config/project.json namespaces do not match game1 contract")
    ports = cfg.get("ports", {})
    old = {43720, 43721, 34872, 43127}
    if old & set(ports.values()):
        report_error("port collision with robloxlineage baseline")
    if ports.get("rojo") != 34882:
        report_error("game1 rojo port must be 34882")


    for relative in REQUIRED_RUNTIME_MODULES:
        if not (root / relative).is_file():
            report_error(f"runtime module missing: {relative}")

    for legacy in LEGACY_RUNTIME_MODULES:
        if (root / legacy).exists():
            report_error(f"legacy flat runtime module must be removed: {legacy}")
