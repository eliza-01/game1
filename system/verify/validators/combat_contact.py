"""M166 read-only verification of combat contact contracts.

All diagnostics flow through the injected sink, in legacy source order.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable


def check_combat_contact_contracts(
    root: Path, report_error: Callable[[str], None], *,
    damage_resolver_text: str, hitbox_implementation_text: str
) -> None:
    """Validate weapon sweep, precomputed hitboxes and headshot ray behavior."""
    # m27 animated EquippedWeapon volume + multi-target melee + Test Loadout preview.
    weapon_volume_path_m27 = root / "src/shared/combat/WeaponAttackVolume.luau"
    weapon_volume_m27 = weapon_volume_path_m27.read_text(encoding="utf-8") if weapon_volume_path_m27.is_file() else ""
    for required in [
        "WeaponAttackVolume.StampWeaponBox",
        "WeaponAttackVolume.ReadEquippedWeaponBox",
        "WeaponAttackVolume.Build",
        "distanceToSphereExit",
        "bladeGeometry",
    ]:
        if required not in weapon_volume_m27:
            report_error(f"m27 animated weapon hit-volume contract missing {required}")

    weapon_equip_m27 = (root / "src/server/weapon/WeaponEquipService.luau").read_text(encoding="utf-8")
    if "WeaponAttackVolume.StampWeaponBox(weapon)" not in weapon_equip_m27:
        report_error("m27 equipped weapons must persist their canonical local attack box")

    attack_controller_m27 = (root / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
    for required in [
        'WaitForChild("AttackWeaponPose")',
        "WeaponPoseSampleInterval",
        "publishWeaponPose",
        "clientAttackId = sequence",
    ]:
        if required not in attack_controller_m27:
            report_error(f"m27 client animated weapon-pose sampling missing {required}")

    attack_service_m27 = (root / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
    for required in [
        "applyAnimatedWeaponSweep",
        "animated_weapon_sweep",
        "WeaponAttackVolume.Build",
        'poseEvent.Name = "AttackWeaponPose"',
        "AttackSessionStore.EnsureSweep",
    ]:
        if required not in attack_service_m27:
            report_error(f"m27 server weapon-volume/multi-target contract missing {required}")
    if "hitCount += 1" not in damage_resolver_text:
        report_error("m27 melee contact resolver must count each damageable target")
    if "local best: Model?" in attack_service_m27 or "local best: Model?" in damage_resolver_text:
        report_error("m27 melee damage must not collapse an animated weapon volume to one best target")

    test_loadout_m27 = (root / "src/client/dev/TestLoadoutController.luau").read_text(encoding="utf-8")
    for required in [
        "WEAPON HIT VOLUME: OFF",
        "createWeaponHitVolumePreview",
        "renderWeaponHitVolume",
        "WeaponAttackVolume.Build",
    ]:
        if required not in test_loadout_m27:
            report_error(f"m27 Test Loadout weapon-volume preview missing {required}")

    # m29 contact-driven animated weapon sweep. Damage is no longer gated by one
    # timeline frame; accepted poses are queried continuously with interpolation and
    # one-hit-per-target deduplication. m32 narrows that sweep to the pre-Hit window.
    attack_service_m29 = (root / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
    for required in [
        "AttackSessionStore.HitTargets",
        "applyAnimatedWeaponSweep",
        "animated_weapon_sweep",
        "lastBoxCFrame",
        "previousBoxCFrame:Lerp",
    ]:
        if required not in attack_service_m29:
            report_error(f"m29 continuous weapon-contact sweep missing {required}")

    if "and (not hitTargets or hitTargets[model] ~= true)" not in damage_resolver_text:
        report_error("m29 one-hit-per-target damage deduplication missing")

    attack_config_m29 = (root / "src/shared/combat/AttackConfig.luau").read_text(encoding="utf-8")
    for required in [
        "WeaponPoseSweepLinearStep",
        "WeaponPoseSweepAngularStep",
        "WeaponPoseSweepMaxSubsteps",
    ]:
        if required not in attack_config_m29:
            report_error(f"m29 weapon sweep config missing {required}")

    # m31 precomputed tight hitboxes. Mesh geometry is read only while the rig is
    # loaded; attack-time work is limited to cached bone transforms and OBB tests.
    entity_hitbox_m31 = hitbox_implementation_text
    for required in [
        "definitionCache",
        "buildDefinition",
        "HEAD_BOX_PADDING",
        "BODY_BOX_PADDING",
        "precomputed_bone_boxes",
        "RunService.Heartbeat",
        "excludedTargets",
    ]:
        if required not in entity_hitbox_m31:
            report_error(f"m31 precomputed hitbox contract missing {required}")
    for forbidden in [
        "triangleBoxIntersectionCentroid",
        "clipAgainstPlane",
        "computePose",
        "deformRecord",
        "CombatMeshHeadCutoffY",
        "deformed_mesh_surface",
        "PoseHitboxMode",
        "PoseHitboxCount",
    ]:
        if forbidden in entity_hitbox_m31:
            report_error(f"m31 obsolete runtime hit geometry remains: {forbidden}")

    attack_service_m31 = (root / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
    attack_damage_m31 = (root / "src/server/combat/AttackDamageResolver.luau").read_text(encoding="utf-8")
    for required in [
        "HeadshotDamageMultiplier",
        'SetAttribute("LastHeadshot"',
        'SetAttribute("LastAttackHeadshot"',
        "QueryDamageablesInBox(character, boxCFrame, boxSize, hitTargets)",
    ]:
        if required not in attack_damage_m31:
            report_error(f"m31 combat-hitbox integration missing {required}")
    for forbidden in ["fallbackAimVolume", "unarmed_fallback"]:
        if forbidden in attack_service_m31:
            report_error(f"m31 obsolete melee fallback remains: {forbidden}")

    attack_config_m31 = (root / "src/shared/combat/AttackConfig.luau").read_text(encoding="utf-8")
    if "HeadshotDamageMultiplier = 2" not in attack_config_m31:
        report_error("m31 default headshot multiplier must stay explicit and tunable")
    if "BoxWidth" in attack_config_m31 or "BoxHeight" in attack_config_m31:
        report_error("m31 obsolete aim-volume dimensions must be removed")

    dummy_m31 = (root / "src/server/dev/TrainingDummyService.luau").read_text(encoding="utf-8")
    for required in ["EntityHitboxService.Attach(model, visual)", "combat hitboxes attached"]:
        if required not in dummy_m31:
            report_error(f"m31 Training Dummy hitbox binding missing {required}")
    if "fallback dummy" in dummy_m31:
        report_error("m31 Training Dummy must not create a non-mesh fallback target")

    test_loadout_m31 = (root / "src/client/dev/TestLoadoutController.luau").read_text(encoding="utf-8")
    for required in [
        "TARGET HITBOXES: OFF",
        "Game1TargetHitboxPreview",
        "CombatHitboxDebugData",
        "precomputed_bone_boxes",
    ]:
        if required not in test_loadout_m31:
            report_error(f"m31 Test Loadout hitbox preview missing {required}")
    for forbidden in ["TARGET MESH REGIONS", "CombatMeshBodyBoxCFrame", "CombatMeshHeadCutoffY"]:
        if forbidden in test_loadout_m31:
            report_error(f"m31 obsolete mesh-classifier preview remains: {forbidden}")

    monster_m31 = (root / "src/server/monster/MonsterSpawnerService.luau").read_text(encoding="utf-8")
    if "PoseHitboxCount" in monster_m31:
        report_error("m31 monster runtime still publishes obsolete PoseHitboxCount")
    if 'SetAttribute("CombatHitboxCount", hitbox.count)' not in monster_m31:
        report_error("m31 monster runtime must publish CombatHitboxCount")


    # m32 terminal Hit window + blade-side weapon volume. Continuous contact is
    # allowed only through the authored Hit event; imported handle geometry behind
    # the character weapon bone is never part of the attacking OBB.
    weapon_volume_m32 = (root / "src/shared/combat/WeaponAttackVolume.luau").read_text(encoding="utf-8")
    for required in [
        'BONE_BOX_LOCAL_ATTRIBUTE = "WeaponAttackBoneBoxLocalPosition"',
        "bladeGeometry",
        "ReadWeaponBoneBoxLocalPosition",
        "weaponBonePosition",
        "bladeLength + extension",
    ]:
        if required not in weapon_volume_m32:
            report_error(f"m32 bone-to-blade volume contract missing {required}")
    for forbidden in ["ReadGripBoxLocalPosition", "outwardDirection"]:
        if forbidden in weapon_volume_m32:
            report_error(f"m32 obsolete handle-inclusive weapon-volume path remains: {forbidden}")

    attack_service_m32 = (root / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
    if "ReadWeaponBoneBoxLocalPosition" not in attack_service_m32:
        report_error("m32 server weapon sweep must use the weapon-bone cutoff")

    test_loadout_m32 = (root / "src/client/dev/TestLoadoutController.luau").read_text(encoding="utf-8")
    if "ReadWeaponBoneBoxLocalPosition" not in test_loadout_m32:
        report_error("m32 Test Loadout weapon-volume preview must use the weapon-bone cutoff")
    if "ReadGripBoxLocalPosition" in test_loadout_m32:
        report_error("m32 Test Loadout still uses obsolete grip/handle volume origin")



    # m33 reticle-ray headshot policy. Weapon contact remains multi-target and uses
    # the same precomputed hitboxes, but headshot classification is independent:
    # the center-screen aim segment is clamped to AttackRadius and may upgrade only
    # the one nearest combat region under the reticle, at most once per attack.
    aim_pose_m33 = (root / "src/client/combat/AimPoseController.luau").read_text(encoding="utf-8")
    for required in [
        "function AimPoseController.GetAimRay()",
        "ViewportPointToRay",
        "return ray.Origin, direction.Unit",
    ]:
        if required not in aim_pose_m33:
            report_error(f"m33 center-screen aim-ray source missing {required}")

    attack_controller_m33 = (root / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
    for required in [
        "aimPoseController.GetAimRay",
        "aimOrigin = aimOrigin",
        "aimDirection = aimDirection",
    ]:
        if required not in attack_controller_m33:
            report_error(f"m33 weapon-pose aim sampling missing {required}")
    if "aim = target" in attack_controller_m33:
        report_error("m33 obsolete one-shot AttackIntent aim payload remains")

    entity_hitbox_m33 = hitbox_implementation_text
    for required in [
        "rayBoxDistance",
        "raySegmentNearSphere",
        "function HitboxSpatialQueries.AimContact(",
        "EntityHitboxService.RaycastAimRegions",
        'geometryRole = "head"',
        'geometryRole = "body"',
    ]:
        if required not in entity_hitbox_m33:
            report_error(f"m33 finite aim-region ray query missing {required}")
    for forbidden in ['hitZone = "head"', 'hitZone = "body"']:
        if forbidden in entity_hitbox_m33:
            report_error(f"m33 weapon contact still classifies headshot directly: {forbidden}")

    attack_service_m33 = (root / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
    attack_damage_m33 = (root / "src/server/combat/AttackDamageResolver.luau").read_text(encoding="utf-8")
    attack_aim_m33 = (root / "src/shared/combat/AttackAimGeometry.luau").read_text(encoding="utf-8")
    for required in [
        "AttackSessionStore.HeadshotTarget",
        "sampledAimOrigin",
        "sampledAimDirection",
        "lastAimOrigin",
        "lastAimDirection",
        "AttackAimGeometry.Normalize",
        "AttackDamageResolver.Apply",
    ]:
        if required not in attack_service_m33:
            report_error(f"m33 attack-session aim orchestration missing {required}")
    for required in [
        "function AttackAimGeometry.Normalize",
        "function AttackAimGeometry.HeadshotSegment",
        "function AttackAimGeometry.InterpolateDirection",
        "HeadshotAimOriginMaxDistance",
    ]:
        if required not in attack_aim_m33:
            report_error(f"m33 server aim geometry missing {required}")
    for required in [
        "RaycastAimRegions",
        'aimedRegion.zone == "head"',
        "aimedRegion.model == model",
        "damageMultiplier = if isHeadshot",
    ]:
        if required not in attack_damage_m33:
            report_error(f"m33 reticle-gated damage resolution missing {required}")
    if "hit.hitZone" in attack_damage_m33:
        report_error("m33 headshot must not come from weapon-contact hitZone")

    attack_config_m33 = (root / "src/shared/combat/AttackConfig.luau").read_text(encoding="utf-8")
    for required in ["HeadshotDamageMultiplier = 2", "HeadshotAimOriginMaxDistance"]:
        if required not in attack_config_m33:
            report_error(f"m33 headshot config missing {required}")
