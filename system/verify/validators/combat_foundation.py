"""Read-only critical damage, attack and timeline foundation contracts (M170)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, NamedTuple


class CombatFoundationSources(NamedTuple):
    attack_text: str
    damage_resolver_text: str
    attack_timeline_text: str
    attack_timeline_data_text: str


def check_combat_foundation(ROOT: Path, err: Callable[[str], None]):
    damage_text = (ROOT / "src/server/combat/DamageService.luau").read_text(encoding="utf-8")
    for required in ["CritChance", "CRITICAL_DAMAGE_MULTIPLIER = 2", "criticalRandom:NextNumber", "damageBeforeDefense"]:
        if required not in damage_text:
            err(f"critical damage contract missing {required}")

    attack_text = (ROOT / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
    dummy_text = (ROOT / "src/server/dev/TrainingDummyService.luau").read_text(encoding="utf-8")
    damage_resolver_text = (ROOT / "src/server/combat/AttackDamageResolver.luau").read_text(encoding="utf-8")
    if "[game1][attack] hit" not in damage_resolver_text or "[game1][attack] miss" not in attack_text:
        err("attack smoke-test logging contract missing")
    if "EntityHitboxService.QueryDamageablesInBox" not in damage_resolver_text:
        err("attack service must resolve melee damage through authoritative target hitboxes")
    attack_timeline_path = ROOT / "src/shared/combat/AttackTimelineConfig.luau"
    attack_timeline_text = attack_timeline_path.read_text(encoding="utf-8") if attack_timeline_path.is_file() else ""
    attack_timeline_data_path = ROOT / "src/shared/combat/AttackTimelineData.luau"
    attack_timeline_data_text = attack_timeline_data_path.read_text(encoding="utf-8") if attack_timeline_data_path.is_file() else ""
    for required in [
        "AttackTimelineConfig.EventNames",
        "function AttackTimelineConfig.ResolveRuntime",
        "EndGuardSeconds = 0.03",
        "normalizedTime",
        "playbackDuration",
        "playbackSpeed",
        "animationSpeedPercent",
        "speedPercent",
    ]:
        if required not in attack_timeline_text:
            err(f"attack animation timeline config missing {required}")
    for forbidden in ["ResultTypes", "melee_damage", "runtimeTailDuration"]:
        if forbidden in attack_timeline_text:
            err(f"obsolete attack timeline runtime field remains: {forbidden}")
    for required in [
        "AttackTimelineConfig.ResolveRuntime",
        "CharacterAttackWindow.Resolve",
        "allowedAttackDescriptor",
        "AnimationSpeedScaling.ResolveForAnimation",
        "AttackSessionStore.IsCoolingDown",
        'character:SetAttribute("AttackEndsAt"',
    ]:
        if required not in attack_text:
            err(f"server attack timeline contract missing {required}")
    if "BillboardGui" not in dummy_text or "HP %d/%d" not in dummy_text:
        err("training dummy visible hp contract missing")

    return CombatFoundationSources(attack_text, damage_resolver_text, attack_timeline_text, attack_timeline_data_text)
