"""Death terminal-frame, life-state, and hit VFX contracts (M168)."""

import json
from pathlib import Path
from typing import Callable


def check_death_runtime(root: Path, report_error: Callable[[str], None], *,
                        animation_store_text: str, monster_sources,
                        damage_resolver_text: str) -> str:
    """Check death animation/lifecycle and hit effects in original order."""
    character_animation_manifest_path = root / "assets/manifests/character-animations.json"
    if character_animation_manifest_path.is_file():
        character_animation_manifest = json.loads(character_animation_manifest_path.read_text(encoding="utf-8"))
        obsolete_character_bindings = [
            row for row in (character_animation_manifest.get("bindings") or [])
            if str(row.get("slot") or "") in {"equip", "unequip"}
        ]
        if obsolete_character_bindings:
            report_error("character animation manifest still contains equip/unequip bindings")
    if '"slot": "death_wait"' in animation_store_text:
        report_error("character animation catalog must not expose death_wait; DeathIdle holds the final death frame")
    death_policy_path = root / "src/shared/combat/DeathAnimationPolicy.luau"
    death_policy_text = death_policy_path.read_text(encoding="utf-8") if death_policy_path.is_file() else ""
    for required in [
        "function DeathAnimationPolicy.Start",
        "function DeathAnimationPolicy.LatchVisibleTerminalPose",
        "TerminalSafetySeconds = 0.02",
        "terminalTime = math.max(0, length -",
        "track.Looped = true",
        "track.TimePosition = terminalTime",
        "track:AdjustWeight(1, 0)",
        "track:AdjustSpeed(0)",
        "startedSpeed",
        "expectedElapsed",
        "elapsed < expectedElapsed",
        "return true, terminalTime",
    ]:
        if required not in death_policy_text:
            report_error(f"deterministic death terminal-hold policy missing {required}")

    for forbidden in [
        "AdvanceToFinalKey",
        "track.TimePosition = finalKeyTime",
        "EndEpsilonSeconds",
    ]:
        if forbidden in death_policy_text:
            report_error(f"death terminal hold contains legacy path: {forbidden}")

    for required in [
        "maintainDeathTerminalPose",
        "DeathAnimationPolicy.Start",
        "DeathAnimationPolicy.LatchVisibleTerminalPose",
        'MonsterAnimationState", "death_idle"',
        "DeathLifecycleService.BeginDeathIdle",
        "RunService.PreAnimation:Connect",
        "deathPoseHeld",
    ]:
        if required not in monster_sources.runtime_text:
            report_error(f"monster death terminal-pose lifecycle missing {required}")

    for required in [
        "ensureRuntimeAnimationRoot",
        'animationRoot.Name = "RootBone"',
        "animationRoot.CFrame = CFrame.identity",
        "bone.Parent = animationRoot",
        "RuntimeAnimationRootBridgeCount",
    ]:
        if required not in monster_sources.runtime_text:
            report_error(f"monster root-bone animation bridge missing {required}")

    character_animation_text = (root / "src/client/character/animation/CharacterAnimationController.luau").read_text(encoding="utf-8")
    for required in [
        "playDeath",
        "maintainDeathTerminalPose",
        "DeathAnimationPolicy.Start",
        "DeathAnimationPolicy.LatchVisibleTerminalPose",
        "DeathTerminalReached",
        "RunService.PreAnimation:Connect(maintainDeathPose)",
        "maintainDeathTerminalPose(deltaTimeSim)",
        "DeathTerminalPoseHeld",
    ]:
        if required not in character_animation_text:
            report_error(f"character death terminal-pose lifecycle missing {required}")

    character_service_text = (root / "src/server/character/CharacterService.luau").read_text(encoding="utf-8")
    for required in ["beginPlayerDeathIdle", "DeathTerminalReached", "DeathLifecycleService.BeginDeathIdle"]:
        if required not in character_service_text:
            report_error(f"character death server handoff missing {required}")

    legacy_death_tokens = [
        "playDeathToTerminalPose",
        "holdDeathTerminalPose",
        "DeathAnimationNaturalStopObserved",
        "DeathAnimationStoppedTimePosition",
        "DeathAnimationFinished",
        "DeathPlaybackSafetySeconds",
        "DeathTrackLoadTimeoutSeconds",
        "CharacterDeathReadyFallbackSeconds",
        "DeathTerminalFrameEpsilonSeconds",
        "track:Play(0, 0, 0)",
    ]
    if "RobloxBakedAnimationRate = 24" in death_policy_text or "TerminalFrameSeconds" in death_policy_text:
        report_error("death playback must not use baked-FPS truncation")

    combined_death_runtime = "\n".join([
        monster_sources.spawner_text,
        character_animation_text,
        character_service_text,
        (root / "src/shared/combat/EntityLifecycleConfig.luau").read_text(encoding="utf-8"),
    ])
    for forbidden in legacy_death_tokens:
        if forbidden in combined_death_runtime:
            report_error(f"legacy/fallback death playback path must be removed: found {forbidden}")

    damage_service_text = (root / "src/server/combat/DamageService.luau").read_text(encoding="utf-8")
    for required in ['SetAttribute("LifeState", "Dying")', 'SetAttribute("Damageable", false)', 'SetAttribute("DeathStartedAt"']:
        if required not in damage_service_text:
            report_error(f"HP=0 death edge missing {required}")

    hit_effect_server = (root / "src/server/combat/HitEffectService.luau").read_text(encoding="utf-8") if (root / "src/server/combat/HitEffectService.luau").is_file() else ""
    hit_effect_client = (root / "src/client/combat/HitEffectController.luau").read_text(encoding="utf-8") if (root / "src/client/combat/HitEffectController.luau").is_file() else ""
    hit_sparks = (root / "src/client/combat/effects/HitSparkBurst.luau").read_text(encoding="utf-8") if (root / "src/client/combat/effects/HitSparkBurst.luau").is_file() else ""
    for required in ["UnreliableRemoteEvent", "ServerReplicationRadius", "FireClient"]:
        if required not in hit_effect_server:
            report_error(f"server hit-effect bridge missing {required}")
    for required in ["HitEffectPool", "BurstCapacity", "OnClientEvent"]:
        if required not in hit_effect_client:
            report_error(f"client hit-effect controller missing {required}")
    for required in ["ImpactSpark", "Beam", "NormalSparkCount", "CriticalSparkCount"]:
        if required not in hit_sparks:
            report_error(f"pooled hit sparks missing {required}")
    if "HitEffectService.Publish" not in damage_resolver_text:
        report_error("confirmed melee hits do not publish hit sparks")
    return character_service_text
