"""M167 read-only verification of animations domain contracts.

All diagnostics are emitted via the provided sink, at the original call site.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


def check_character_animation(
    ROOT: Path, err: Callable[[str], None], *, schema_text, ui, js, character_service_text
) -> tuple:
    # m5.1 character animation contract
    animation_manifest_path = ROOT / "assets/manifests/character-animations.json"
    if not animation_manifest_path.is_file():
        err(r"character animation manifest is missing; run python .\system\control-center\migrate.py")
        animation_manifest = {}
    else:
        animation_manifest = json.loads(animation_manifest_path.read_text(encoding="utf-8"))
    if animation_manifest.get("schemaVersion") != 2 or animation_manifest.get("project") != "game1":
        err("character animation manifest must be game1 schema 2")
    if animation_manifest.get("weaponSets") != ["hands", "1hs", "2hs", "bow"]:
        err("character animation weapon sets must be hands, 1hs, 2hs and bow")
    for binding in animation_manifest.get("bindings") or []:
        if "playbackSpeedPercent" in binding or "playback_speed_percent" in binding:
            err(f"character animation binding must not own playback speed: {binding.get('id')}")

    animation_store_path = ROOT / "system/control-center/animation_store.py"
    animation_core_dir = ROOT / "system/control-center/animation_core"
    animation_store_text = animation_store_path.read_text(encoding="utf-8") if animation_store_path.is_file() else ""
    if animation_core_dir.is_dir():
        for core_file in sorted(animation_core_dir.glob("*.py")):
            animation_store_text += "\n" + core_file.read_text(encoding="utf-8")
    for required in [
        "class AnimationStore",
        "def scan_folder",
        "def preview_folder",
        "def register_selected",
        "def stage_manual_replacement",
        "def classify_animation",
        'WEAPON_SETS = ("hands", "1hs", "2hs", "bow")',
        "def assign_file",
        "normalize_manual_binding",
        "_strip_character_prefix",
        '"seated.enter"',
        '"seated.loop"',
        '"seated.exit"',
        '"attack"',
        '"variant"',
    ]:
        if required not in animation_store_text:
            err(f"character animation store missing {required}")
    if 'queue = [row for row in rows if row["status"] == "LOCAL_ONLY"]' not in animation_store_text:
        err("publish-missing must never create duplicate assets for changed published animations")
    if "reimport it manually in Roblox Studio" not in animation_store_text or "Check Roblox Assets Animations" not in animation_store_text:
        err("changed animation assets must preserve their permanent id and use manual reimport confirmation")

    animation_registry_path = ROOT / "src/shared/character/CharacterAnimationRegistry.luau"
    animation_registry_text = animation_registry_path.read_text(encoding="utf-8") if animation_registry_path.is_file() else ""
    if "profiles = table.freeze" not in animation_registry_text:
        err("generated character animation runtime registry is missing")

    resolver_path = ROOT / "src/client/character/animation/AnimationResolver.luau"
    controller_path = ROOT / "src/client/character/animation/CharacterAnimationController.luau"
    resolver_runtime = resolver_path.read_text(encoding="utf-8") if resolver_path.is_file() else ""
    controller_runtime = controller_path.read_text(encoding="utf-8") if controller_path.is_file() else ""
    for required in ["ResolveLocomotion", "ResolveAction", "AnimationWeaponSet", "skeletonSignature"]:
        if required not in resolver_runtime:
            err(f"animation resolver missing {required}")
    for required in ["MovementState", "PlayAction", "AnimationResolvedClip", "AnimationTrackCache", "AnimationPlaybackSpeedPercent", "AnimationSpeedScaling"]:
        if required not in controller_runtime:
            err(f"character animation controller missing {required}")
    client_init_text = (ROOT / "src/client/init.client.luau").read_text(encoding="utf-8")
    if "CharacterAnimationController.Start()" not in client_init_text:
        err("character animation controller is not started by the client runtime")
    attack_controller_text = (ROOT / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
    if 'animationController.PlayAction("attack")' not in attack_controller_text:
        err("combat attack input is not connected to the semantic attack animation slot")
    for required in ["BeginAimFacingCompensation", "TorsoYawLimit", "aimPoseController.BeginAttack", "finishPresentation(sequence)"]:
        if required not in attack_controller_text:
            err(f"robloxlineage attack/aim integration missing {required}")
    aim_pose_text = (ROOT / "src/client/combat/AimPoseController.luau").read_text(encoding="utf-8")
    for required in ["RunService.PreSimulation", "spine.001", "AimTorsoYawDegrees", "applyWorldAim", "desiredTransform", "ViewportPointToRay", "Game1AimReticle"]:
        if required not in aim_pose_text:
            err(f"procedural torso aim controller missing {required}")
    movement_runtime = (ROOT / "src/client/character/MovementController.luau").read_text(encoding="utf-8")
    for required in ["BeginAimFacingCompensation", "UpdateAimFacingCompensation", "applyAimFacingCompensation"]:
        if required not in movement_runtime:
            err(f"movement aim-facing compensation missing {required}")
    if "AimPoseController.Start()" not in client_init_text:
        err("procedural torso aim controller is not started by the client runtime")

    # m21+ RobloxLineage upper-body attack presentation contract. Facing/aim are held
    # for the complete attack when stationary; the source clip is sampled on a proxy
    # and only the upper-body bridge subtree is composed over live lower-body locomotion.
    attack_composer_path = ROOT / "src/client/character/animation/AttackUpperBodyComposer.luau"
    attack_composer_text = attack_composer_path.read_text(encoding="utf-8") if attack_composer_path.is_file() else ""
    for required in [
        "__Game1AttackUpperBodyProxy",
        'FindFirstChild("spine.001", true)',
        "buildUpperPairs",
        "sourceArmature",
        "mappedAttackWorld",
        "baseBridgeTransform:Lerp",
        "RunService.PreSimulation:Connect(step)",
        "RunService.PreAnimation:Connect(holdSourceTerminalPose)",
    ]:
        if required not in attack_composer_text:
            err(f"upper-body attack composition missing {required}")
    for required in [
        "attackLowerBodyActive",
        'return "combat_idle"',
        "AttackUpperBodyComposer.Begin(character, descriptor, playbackSpeed)",
        "AnimationAttackUpperBodyComposed",
        "AnimationAttackLowerBodySlot",
        "AttackUpperBodyComposer.BeginExitBlend()",
    ]:
        if required not in controller_runtime:
            err(f"attack lower/upper-body composition contract missing {required}")
    for forbidden in [
        "task.delay(facingDuration",
        "AttackConfig.MovementLockSeconds",
        "AttackConfig.AimPoseSeconds",
    ]:
        if forbidden in attack_controller_text:
            err(f"attack presentation still releases aim/movement early: {forbidden}")
    if "aimPoseController.BeginAttack(target, attackDuration)" not in attack_controller_text:
        err("attack aim pose must stay active for the complete attack duration")
    if "movementController.EndAimFacingCompensation()" not in attack_controller_text.split("local function finishPresentation", 1)[1].split("function AttackController.Start", 1)[0]:
        err("root aim compensation must release only from full-attack presentation cleanup")
    if 'character:SetAttribute("AnimationProfileId", archetype)' not in character_service_text:
        err("character runtime does not expose animation profile identity")
    if 'character:SetAttribute("CharacterSkeletonSignature"' not in character_service_text:
        err("character runtime does not expose skeleton signature to animation resolver")
    if 'character:SetAttribute("AnimationWeaponSet", "hands")' not in character_service_text:
        err("character runtime must default to the canonical hands animation context")

    for required in ["animation_profiles", "animation_clips", "animation_bindings", "animation_publications"]:
        if required not in schema_text:
            err(f"control center schema missing {required}")
    if 'id="nav-animations"' not in ui or 'id="scan-animations"' not in ui or 'id="animation-scan-dialog"' not in ui:
        err("asset manager character animation section is missing")
    js_text = js.read_text(encoding="utf-8") if js.is_file() else ""
    for required in ["filename_rule_catalog", "canonicalFilename", "variantPattern", "filename_prefix"]:
        if required not in animation_store_text:
            err(f"animation filename-rule catalog missing {required}")
    for required in ['id="animation-filename-rules"', 'id="animation-filename-guide"', "all registered states", 'id="animation-show-missing"']:
        if required not in ui:
            err(f"animation filename-rules UI missing {required}")
    if "renderFilenameRules" not in js_text:
        err("animation filename-rules renderer missing")
    for required in ["FILENAME_GUIDE_OPEN_KEY", "localStorage.getItem", "localStorage.setItem", "initFilenameRulesDisclosure"]:
        if required not in js_text:
            err(f"animation filename-rules disclosure persistence missing {required}")
    for required in ["chooseAnimationFolder", "scanAnimations", "animationFilter"]:
        if required not in js_text:
            err(f"asset manager animation ui missing {required}")
    animation_ui = ROOT / "system/control-center/static/character-animation-ui.js"
    animation_ui_text = animation_ui.read_text(encoding="utf-8") if animation_ui.is_file() else ""
    for required in ["renderRules", "renderRows", "registerSelected", "stageReplacement", "checkReplacement", "localStorage.setItem"]:
        if required not in animation_ui_text:
            err(f"character animation reviewed workflow missing {required}")
    for forbidden in ["setAnimationSpeed", "data-speed"]:
        if forbidden in js_text:
            err(f"asset manager character clip table must not expose per-clip speed control: {forbidden}")
    if "<th>speed %</th>" in ui:
        err("asset manager animation clip tables must not expose authored speed percent")
    if 'create_animation_asset' not in (ROOT / "system/control-center/opencloud_assets.py").read_text(encoding="utf-8"):
        err("open cloud animation publication helper is missing")

    return animation_store_text, animation_registry_text, controller_runtime, client_init_text, attack_controller_text, movement_runtime, js_text


def check_animation_scaling(
    ROOT: Path, err: Callable[[str], None], *, ui, host_agent_text, character_js_text, animation_registry_text, attack_timeline_text
) -> None:
    animation_scaling_manifest_path = ROOT / "assets/manifests/animation-speed-scaling.json"
    animation_scaling_runtime_path = ROOT / "src/shared/animation/AnimationSpeedScaling.luau"
    animation_scaling_registry_path = ROOT / "src/shared/animation/AnimationSpeedScalingRegistry.luau"
    animation_scaling_store_path = ROOT / "system/control-center/animation_speed_scaling_store.py"
    animation_scaling_js_path = ROOT / "system/control-center/static/animation-speed.js"
    if not animation_scaling_manifest_path.is_file():
        err("animation speed scaling manifest is missing")
        animation_scaling_manifest = {}
    else:
        animation_scaling_manifest = json.loads(animation_scaling_manifest_path.read_text(encoding="utf-8"))
    if animation_scaling_manifest.get("schemaVersion") != 1 or animation_scaling_manifest.get("project") != "game1":
        err("animation speed scaling manifest must be game1 schema 1")
    expected_scaling = {
        ("humanoid", "all", "run"): "RunSpeed",
        ("humanoid", "all", "walk"): "RunSpeed",
        ("humanoid", "all", "attack"): "AttackSpeed",
        ("humanoid", "all", "combat_idle"): "AttackSpeed",
        ("monster", "gremlin", "run"): "RunSpeed",
    }
    actual_scaling = {}
    for profile in animation_scaling_manifest.get("profiles") or []:
        for rule in profile.get("rules") or []:
            key = (str(profile.get("targetType") or ""), str(profile.get("targetId") or ""), str(rule.get("channel") or ""))
            actual_scaling[key] = (str(rule.get("stat") or ""), float(rule.get("unitsPerPercent") or 0))
    for key, expected_stat in expected_scaling.items():
        actual = actual_scaling.get(key)
        if not actual or actual[0] != expected_stat or actual[1] <= 0:
            err(f"animation speed scaling rule mismatch for {key}: expected positive adjustable {expected_stat} ratio, got {actual}")
    animation_scaling_runtime = animation_scaling_runtime_path.read_text(encoding="utf-8") if animation_scaling_runtime_path.is_file() else ""
    animation_scaling_registry = animation_scaling_registry_path.read_text(encoding="utf-8") if animation_scaling_registry_path.is_file() else ""
    animation_scaling_store = animation_scaling_store_path.read_text(encoding="utf-8") if animation_scaling_store_path.is_file() else ""
    animation_scaling_js = animation_scaling_js_path.read_text(encoding="utf-8") if animation_scaling_js_path.is_file() else ""
    monster_assets_js_early = (ROOT / "system/control-center/static/monster-assets.js").read_text(encoding="utf-8")
    monster_animation_registry_early = (ROOT / "src/shared/monster/MonsterAnimationRegistry.luau").read_text(encoding="utf-8")
    for required in ["ResolveForModel", "ResolveDetailsForModel", "TargetForModel", "unitsPerPercent", "Formula.DetailsPercent", "DebugUnitsPerPercentAttribute", "authoredUnitsPerPercent", "debugUnitsPerPercent"]:
        if required not in animation_scaling_runtime:
            err(f"animation speed scaling runtime missing {required}")
    for owner, required in {
        "AnimationScalingFormula.luau": ["value / unitsPerPercent", "Formula.RulePercent", "Formula.DetailsPercent"],
        "AnimationScalingPolicy.luau": ["Registry.custom", 'return "monster"', 'return "humanoid", "all"'],
        "AnimationScalingDebugOverrides.luau": ["Workspace:GetAttribute", "Overrides.ModelUnits", "Overrides.ClipRule"],
    }.items():
        owner_path = ROOT / "src/shared/animation" / owner
        owner_source = owner_path.read_text(encoding="utf-8") if owner_path.is_file() else ""
        for fragment in required:
            if fragment not in owner_source:
                err(f"animation scaling component {owner} missing {fragment}")
    if "DebugOverrideAttribute" in animation_scaling_runtime or "MovementDebugAnimationSpeedPercentOverride" in animation_scaling_runtime:
        err("animation speed scaling must not support an absolute playback-percent debug override")
    for required in ['["humanoid"]', '["all"]', 'unitsPerPercent = 2.0', '["gremlin"]', 'unitsPerPercent = 0.6']:
        if required not in animation_scaling_registry:
            err(f"generated animation speed scaling registry missing {required}")
    for required in ["AnimationSpeedScalingStore", "unitsPerPercent", "AnimationSpeedScalingRegistry.luau"]:
        if required not in animation_scaling_store:
            err(f"animation speed scaling Asset Manager store missing {required}")
    for required in ["animation speed", "units per 1%", "/api/animation-speed-scaling"]:
        if required not in (ui + animation_scaling_js + host_agent_text).lower():
            err(f"animation speed scaling Asset Manager UI/API missing {required}")
    if "data-speed" in character_js_text or "data-speed" in monster_assets_js_early:
        err("per-animation playback Speed % controls must be removed from Asset Manager clip tables")
    if "/api/animation-bindings/" in host_agent_text and 'endswith("/speed")' in host_agent_text:
        err("character animation binding speed endpoint must be removed")
    if 'monster_binding_prefix) and path.endswith("/speed")' in host_agent_text:
        err("monster animation binding speed endpoint must be removed")
    if "playbackSpeedPercent" in animation_registry_text or "playbackSpeedPercent" in monster_animation_registry_early:
        err("runtime animation registries must not carry per-clip playback speed")
    if "(speedStat /" in attack_timeline_text or "DefaultAttackSpeed" in attack_timeline_text:
        err("attack timeline must consume final stat-scaled playback percent without multiplying AttackSpeed twice")



def check_manual_animation_reimport(
    ROOT: Path, err: Callable[[str], None], *, animation_store_text, character_js_text, host_agent_text
) -> tuple:
    # m18 manual animation reimport verification lives in Asset Manager and mirrors
    # RobloxLineage: scan detects local SHA changes, Studio reimport remains manual,
    # then Open Cloud asset versions confirm a newer Approved version of the same id.
    fingerprint_path = ROOT / "system/control-center/animation_fingerprint.py"
    if fingerprint_path.exists():
        err("Studio content fingerprint checker must be removed; reimport confirmation is Open Cloud version based")
    studio_plugin_text = (ROOT / "system/studio-plugin/Game1Bridge.server.luau").read_text(encoding="utf-8")
    # M101: Timeline source is packaged as independently testable Studio modules.
    studio_plugin_text += "\n" + "\n".join(
        (ROOT / "system/studio-plugin/modules" / (name + ".luau")).read_text(encoding="utf-8")
        for name in (
            "StudioTimelineEditorCommands", "StudioTimelineWidget", "StudioTimelinePreview",
            "StudioTimelinePoseSampler", "StudioTimelineTransport",
        )
    )
    generated_plugin_text = (ROOT / "generated/Game1Bridge.rbxmx").read_text(encoding="utf-8") if (ROOT / "generated/Game1Bridge.rbxmx").is_file() else ""
    for forbidden in ["Game1CheckAnimations", "Check Animations", "Game1CheckRobloxAssetsAnimations", "KeyframeSequenceProvider", "fingerprintKeyframeSequence", "/api/studio/animation-check"]:
        if forbidden in studio_plugin_text or forbidden in generated_plugin_text:
            err(f"Studio animation-check plugin UI/code must be removed: {forbidden}")
    opencloud_text = (ROOT / "system/control-center/opencloud_assets.py").read_text(encoding="utf-8")
    reimport_check_text = (ROOT / "system/control-center/animation_reimport_check.py").read_text(encoding="utf-8")
    character_publication_text = (ROOT / "system/control-center/animation_core/publication.py").read_text(encoding="utf-8")
    monster_store_text_m18 = (ROOT / "system/control-center/monster_animation_store.py").read_text(encoding="utf-8")
    for required in ["ASSET_VERSIONS_URL_TEMPLATE", "def list_asset_versions", "assetVersions"]:
        if required not in opencloud_text:
            err(f"Open Cloud animation-version query missing {required}")
    for required in ["find_confirmed_manual_reimport", "createTime", "published", "Approved", "creationContext", "known_version_ids"]:
        if required not in reimport_check_text:
            err(f"manual animation reimport confirmation missing {required}")
    for required in ["content_updated_at", "asset_version_id", "manual_verified", "check_manual_reimports", "roblox/manual-version-confirmation"]:
        if required not in character_publication_text + animation_store_text + monster_store_text_m18:
            err(f"manual animation publication history missing {required}")
    for required in ["/api/animations/check-roblox-assets", "check_manual_reimports"]:
        if required not in host_agent_text:
            err(f"Asset Manager Roblox animation check API missing {required}")
    for required in ["Check Roblox Assets Animations", "/api/animations/check-roblox-assets", "checkRobloxAnimationAssets"]:
        if required not in character_js_text + (ROOT / "system/control-center/static/index.html").read_text(encoding="utf-8"):
            err(f"Asset Manager animation reimport UI missing {required}")
    if "state.data.activeArchetypeId" not in character_js_text or "autoSelected=true" not in character_js_text:
        err("character Asset Manager must auto-select the active/first archetype so starting stats can be saved")

    return studio_plugin_text
