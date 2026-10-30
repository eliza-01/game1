"""M167 read-only verification of weapons domain contracts.

All diagnostics are emitted via the provided sink, at the original call site.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


def check_weapon_registration(
    ROOT: Path, err: Callable[[str], None], *, schema_text, ui, host_agent_text, plugin_text, rig_text, character_service_text, attack_text, controller_runtime, attack_controller_text, client_init_text
) -> tuple:
    # m6 weapon registry / stats / attachment contract
    weapon_manifest_path = ROOT / "assets/manifests/weapons.json"
    if not weapon_manifest_path.is_file():
        err(r"weapon manifest is missing; run python .\system\control-center\migrate.py")
        weapon_manifest = {}
    else:
        weapon_manifest = json.loads(weapon_manifest_path.read_text(encoding="utf-8"))
    if weapon_manifest.get("schemaVersion") != 2 or weapon_manifest.get("project") != "game1":
        err("weapon manifest must be game1 schema 2")
    weapon_options = weapon_manifest.get("options") or {}
    if weapon_options.get("weaponTypes") != ["dagger", "sword", "bigsword", "bow"]:
        err("weapon type pool must be dagger, sword, bigsword, bow")
    if weapon_options.get("rarities") != ["common", "uncommon", "rare", "mythical", "legendary", "immortal"]:
        err("weapon rarity pool must be common through immortal")

    weapon_store_path = ROOT / "system/control-center/weapon_store.py"
    weapon_store_text = weapon_store_path.read_text(encoding="utf-8") if weapon_store_path.is_file() else ""
    for required in [
        "class WeaponStore",
        "def slugify_english",
        'WEAPON_TYPES = ("dagger", "sword", "bigsword", "bow")',
        'RARITIES = ("common", "uncommon", "rare", "mythical", "legendary", "immortal")',
        'STAT_KEYS = ("Damage", "AttackSpeed")',
        "weapon_stat_modifiers",
        "weapon_textures",
        "create_model_asset",
        "create_image_asset",
        "update_model_asset",
        "update_image_asset",
        'src/shared/weapon/WeaponRegistry.luau',
    ]:
        if required not in weapon_store_text:
            err(f"weapon store missing {required}")

    for required in ["weapons", "weapon_textures", "weapon_stat_modifiers", "weapon_publications"]:
        if required not in schema_text:
            err(f"control center schema missing {required}")

    opencloud_text = (ROOT / "system/control-center/opencloud_assets.py").read_text(encoding="utf-8")
    for required in ["create_image_asset", "update_image_asset", '"assetType": "Image"']:
        if required not in opencloud_text:
            err(f"open cloud weapon texture publication missing {required}")

    weapon_registry_path = ROOT / "src/shared/weapon/WeaponRegistry.luau"
    weapon_registry_text = weapon_registry_path.read_text(encoding="utf-8") if weapon_registry_path.is_file() else ""
    for required in ["activeWeaponSlug", "weapons = table.freeze"]:
        if required not in weapon_registry_text:
            err(f"generated weapon registry missing {required}")

    weapon_equip_path = ROOT / "src/server/weapon/WeaponEquipService.luau"
    weapon_attach_path = ROOT / "src/client/weapon/WeaponAttachmentController.luau"
    weapon_equip_text = weapon_equip_path.read_text(encoding="utf-8") if weapon_equip_path.is_file() else ""
    weapon_attach_text = weapon_attach_path.read_text(encoding="utf-8") if weapon_attach_path.is_file() else ""
    for required in ["Weapon_R_Bone", "weapon_r", "Weapon_L_Bone", "weapon_l", "AnimationWeaponSet", "statModifiers", "EquipStartup", "GetAvailable", "ListAvailable", "WeaponLoadoutSource", "Game1WeaponGrip", "runtime-canonical-grip-v2", "ensureCanonicalRuntimeGrip", "grip.WorldCFrame:Inverse()"]:
        if required not in weapon_equip_text:
            err(f"weapon equip runtime missing {required}")
    for required in ["Game1WeaponAttachment", "parent.TransformedWorldCFrame * targetBone.CFrame", "weapon:PivotTo", "Game1WeaponGrip", "grip.WorldCFrame:Inverse()"]:
        if required not in weapon_attach_text:
            err(f"weapon attachment runtime missing {required}")
    if "WeaponEquipService.EquipStartup(character)" not in character_service_text:
        err("character spawn does not apply the startup weapon")
    if "WeaponAttachmentController.Start()" not in client_init_text:
        err("weapon attachment controller is not started by the client runtime")

    stats_config_text = (ROOT / "src/shared/character/CharacterStatsConfig.luau").read_text(encoding="utf-8")
    stats_service_text = (ROOT / "src/server/character/CharacterStatsService.luau").read_text(encoding="utf-8")
    movement_config_text = (ROOT / "src/shared/character/CharacterMovementConfig.luau").read_text(encoding="utf-8")
    for required in ["AttackSpeed = 100", "RunSpeed = 50"]:
        if required not in stats_config_text:
            err(f"character baseline stat missing {required}")
    for required in ["SetModifierSource", "modifierSources", 'Service.SetModifierSource(character, "weapon", modifiers)']:
        if required not in stats_service_text:
            err(f"composable stat modifier service missing {required}")
    for required in ["DefaultRunSpeed = 50", "WalkSpeedMultiplier = 0.5", "return runSpeed", "return runSpeed * CharacterMovementConfig.WalkSpeedMultiplier"]:
        if required not in movement_config_text:
            err(f"direct RunSpeed/walk-half movement contract missing {required}")
    if 'character:GetAttribute("RunSpeed")' not in rig_text or 'character:GetAttribute("MoveSpeed")' in rig_text:
        err("character rig initial movement must use RunSpeed directly")
    if 'AnimationSpeedScaling.ResolveForAnimation(character, "attack", descriptor.animationId)' not in attack_text:
        err("server attack timeline does not resolve stat-scaled AttackSpeed playback")
    if 'animationSpeedPercent = animationPlaybackPercent(slot, descriptor.animationId)' not in controller_runtime:
        err("client attack presentation does not use shared stat-scaled playback")
    for required in ['animationController.PlayAction("attack")', "action.durationSeconds", "clipId = action.clipId"]:
        if required not in attack_controller_text:
            err(f"client full-animation attack lock missing {required}")

    if 'id="nav-weapons"' not in ui or 'id="register-weapon"' not in ui or 'id="weapon-stat-attack-speed"' not in ui:
        err("asset manager weapon registration section is missing")
    if 'id="weapon-attack-radius"' not in ui:
        err("weapon registration must expose attack radius in studs")
    if 'id="weapon-test-loadout"' in ui or 'id="save-weapon-test-loadout"' in ui:
        err("studio test loadout must not live in the web asset manager")
    weapon_js_path = ROOT / "system/control-center/static/weapon-assets.js"
    weapon_js_text = weapon_js_path.read_text(encoding="utf-8") if weapon_js_path.is_file() else ""
    for required in ["weaponSlugify", "weaponRegister", "weaponPublish", "weaponSync", "weaponActivate", "attackRadiusStuds", "weapon-attack-radius"]:
        if required not in weapon_js_text:
            err(f"asset manager weapon ui missing {required}")
    for required in ["attack_radius_studs", "ATTACK_RADIUS_DEFAULT", "attackRadiusStuds"]:
        if required not in weapon_store_text:
            err(f"weapon attack-radius storage contract missing {required}")
    if "attack_radius_studs real not null default 7" not in schema_text.lower():
        err("weapon schema is missing attack_radius_studs")
    if "weaponSaveTestLoadout" in weapon_js_text:
        err("obsolete asset-manager test loadout javascript is still present")

    for required in ["WeaponStore", "sync_weapon_to_studio", 'placement_mode="weapon-pivot"', '"/api/weapons"']:
        if required not in host_agent_text:
            err(f"host agent weapon api missing {required}")
    if '"/api/weapons/test-loadout"' in host_agent_text or "def set_test_loadout" in weapon_store_text or "TEST_LOADOUT_KEY" in weapon_store_text:
        err("obsolete web/control-center test loadout path is still active")
    if 'placementMode ~= "weapon-pivot"' not in plugin_text or "placeWeaponModel" not in plugin_text:
        err("studio bridge weapon-pivot placement is missing")
    for required in ["Game1WeaponGrip", "ensureWeaponGrip", "canonicalGripWorld", "referencePart.CFrame:ToObjectSpace"]:
        if required not in plugin_text:
            err(f"studio bridge canonical weapon grip is missing {required}")
    for runtime_name, runtime_text in [("client weapon attachment", weapon_attach_text), ("server weapon equip", weapon_equip_text)]:
        for required in ["WEAPON_EQUIP_ROTATION", "CFrame.Angles(math.rad(-90), 0, 0)", "grip.WorldCFrame:Inverse()"]:
            if required not in runtime_text:
                err(f"{runtime_name} stable global -90deg X weapon basis missing {required}")
        if "CFrame.new(grip.WorldPosition)" in runtime_text and runtime_name == "client weapon attachment":
            err("client weapon attachment must not rebuild a position-only grip frame every render step")
    if "ensureCanonicalRuntimeGrip" not in weapon_equip_text or "weaponReferencePart" not in weapon_equip_text:
        err("server weapon equip must rebuild one canonical runtime grip for every weapon")
    if "legacy-pivot" in weapon_equip_text or "weapon:PivotTo(socketFrame)" in weapon_equip_text:
        err("weapon equip must not keep a legacy Model-pivot alignment path")
    if "weapon:PivotTo(socketFrame)" in weapon_attach_text:
        err("client weapon attachment must not keep a legacy Model-pivot alignment path")
    for required in ['character:SetAttribute("AttackRadius"', "attackRadiusStuds", "AttackConfig.MaxAimDistance"]:
        if required not in weapon_equip_text:
            err(f"weapon equip attack-radius runtime missing {required}")
    for required in ['character:GetAttribute("AttackRadius")', "attackRange", "WeaponAttackVolume.Build"]:
        if required not in attack_text:
            err(f"server-authoritative weapon attack radius missing {required}")

    return stats_config_text, stats_service_text, movement_config_text


def check_weapon_attack_movement(
    ROOT: Path, err: Callable[[str], None], *, host_agent_text
) -> None:
    # m22 weapon gameplay types + adjustable moving-attack locomotion + Test Loadout radius.
    weapon_manifest_path = ROOT / "assets/manifests/weapons.json"
    weapon_manifest_m22 = json.loads(weapon_manifest_path.read_text(encoding="utf-8")) if weapon_manifest_path.is_file() else {}
    weapon_types_m22 = ((weapon_manifest_m22.get("options") or {}).get("weaponTypes") or [])
    if weapon_types_m22 != ["dagger", "sword", "bigsword", "bow"]:
        err(f"canonical weapon types are wrong: {weapon_types_m22}")
    attack_movement_rows = {str(row.get("weaponType") or ""): row for row in weapon_manifest_m22.get("attackMovement") or []}
    for weapon_type in ["dagger", "sword", "bigsword", "bow"]:
        row = attack_movement_rows.get(weapon_type)
        if not row:
            err(f"weapon attack movement rule missing: {weapon_type}")
            continue
        if str(row.get("locomotionMode") or "") not in {"Run", "Walk"}:
            err(f"weapon attack locomotion mode invalid: {weapon_type}")
        multiplier = float(row.get("runSpeedMultiplier") or -1)
        if multiplier < 0 or multiplier > 2:
            err(f"weapon attack RunSpeed multiplier invalid: {weapon_type}")
    if attack_movement_rows.get("dagger", {}).get("runSpeedMultiplier") != 1.0:
        err("dagger default moving attack must start at 100% RunSpeed")
    if attack_movement_rows.get("sword", {}).get("runSpeedMultiplier") != 1.0:
        err("sword default moving attack must start at 100% RunSpeed")
    if attack_movement_rows.get("bigsword", {}).get("runSpeedMultiplier") != 0.75:
        err("bigsword default moving attack must start at 75% RunSpeed")
    if attack_movement_rows.get("bow", {}).get("runSpeedMultiplier") != 0.75:
        err("bow default moving attack must start at 75% RunSpeed")

    weapon_store_m22 = (ROOT / "system/control-center/weapon_store.py").read_text(encoding="utf-8")
    weapon_js_m22 = (ROOT / "system/control-center/static/weapon-assets.js").read_text(encoding="utf-8")
    weapon_host_m22 = host_agent_text
    for required in ["weapon_attack_movement", "update_attack_movement", "dagger", "sword", "bigsword", "bow"]:
        if required not in weapon_store_m22:
            err(f"Asset Manager weapon type/attack movement storage missing {required}")
    for required in ["weaponRenderAttackMovement", "movement · % RunSpeed", "data-mode", "data-percent"]:
        if required not in weapon_js_m22:
            err(f"Asset Manager weapon attack movement UI missing {required}")
    if "/api/weapons/attack-movement" not in weapon_host_m22:
        err("Asset Manager weapon attack movement API missing")

    weapon_attack_movement_path = ROOT / "src/shared/weapon/WeaponAttackMovement.luau"
    weapon_attack_movement_text = weapon_attack_movement_path.read_text(encoding="utf-8") if weapon_attack_movement_path.is_file() else ""
    weapon_equip_m22 = (ROOT / "src/server/weapon/WeaponEquipService.luau").read_text(encoding="utf-8")
    movement_m22 = (ROOT / "src/client/character/MovementController.luau").read_text(encoding="utf-8")
    attack_controller_m22 = (ROOT / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
    animation_controller_m22 = (ROOT / "src/client/character/animation/CharacterAnimationController.luau").read_text(encoding="utf-8")
    movement_config_m22 = (ROOT / "src/shared/character/CharacterMovementConfig.luau").read_text(encoding="utf-8")
    animation_scaling_m22 = (ROOT / "src/shared/animation/AnimationSpeedScaling.luau").read_text(encoding="utf-8")
    for required in ["attackMovementByType", "runSpeedMultiplier", "locomotionMode", "animationSet"]:
        if required not in weapon_attack_movement_text + (ROOT / "src/shared/weapon/WeaponRegistry.luau").read_text(encoding="utf-8"):
            err(f"runtime weapon attack movement registry missing {required}")
    for required in ["AttackMovementLocomotionMode", "AttackMovementRunSpeedMultiplier", "WeaponAttackMovement.Resolve"]:
        if required not in weapon_equip_m22:
            err(f"weapon equip attack movement attributes missing {required}")
    for required in ["BeginAttackMovement", "EndAttackMovement", "RobloxSpeedAtRunMultiplier", "AttackMovementActive"]:
        if required not in movement_m22:
            err(f"moving attack runtime control missing {required}")
    if "movementController.LockMovement(attackDuration)" in attack_controller_m22:
        err("attacks must not hard-lock player movement")
    for required in ["BeginAttackMovement", "movingAtAttackStart", "EndAttackMovement"]:
        if required not in attack_controller_m22:
            err(f"attack controller moving-attack contract missing {required}")
    for required in ["AttackMovementLocomotionMode", "combat_idle", "EquivalentRunSpeedForLocomotion", "ResolveForAnimation", "AnimationAttackLowerBodySlot"]:
        if required not in animation_controller_m22:
            err(f"live lower-body attack locomotion missing {required}")
    for required in ["RobloxSpeedAtRunMultiplier", "EquivalentRunSpeedForLocomotion"]:
        if required not in movement_config_m22:
            err(f"attack movement conversion missing {required}")
    if "ResolveForModelWithStatValue" not in animation_scaling_m22:
        err("animation scaling cannot resolve attack locomotion cadence from actual movement speed")

    test_loadout_server_m22 = (ROOT / "src/server/dev/TestLoadoutService.luau").read_text(encoding="utf-8")
    test_loadout_client_m22 = (ROOT / "src/client/dev/TestLoadoutController.luau").read_text(encoding="utf-8")
    for required in ["SetTestAttackRadius", "Game1TestAttackRadiusOverride", "setTestAttackRadius"]:
        if required not in test_loadout_server_m22:
            err(f"Test Loadout attack radius runtime control missing {required}")
    for required in ["SetTestAttackRadius", "Test attack radius · studs", "radiusBox", "RESET"]:
        if required not in test_loadout_client_m22:
            err(f"Test Loadout attack radius UI missing {required}")
