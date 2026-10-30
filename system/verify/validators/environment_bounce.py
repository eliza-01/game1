"""Registry-owned environment weapon collision and reverse bounce contracts (M169)."""

import json
from pathlib import Path
from typing import Callable

from .location_assets import LocationAssetSources


def check_environment_bounce(root: Path, report_error: Callable[[str], None], *,
                             sources: LocationAssetSources, host_agent_text: str,
                             studio_plugin_text: str) -> tuple[str, str]:
    """Check M50/M51 installer contract; return the text needed by texture sync."""
    location_asset_manifest_path = sources.manifest_path
    location_asset_store_text = sources.store_text
    index_m43_text = sources.index_text
    deco_assets_js_text = sources.assets_js
    deco_layout_store_text = sources.layout_store_text
    deco_placement_text = sources.placement_text
    # m50 Environment weapon bounce: Location Asset gameplay policy is registry-owned,
    # DecoManager stores identity only, and solid environment contact terminates the
    # authored damage window before reversing the current attack at 2x speed.
    weapon_bounce_config_path = root / "src/shared/combat/WeaponBounceConfig.luau"
    environment_asset_service_path = root / "src/server/world/EnvironmentAssetService.luau"
    weapon_environment_collision_path = root / "src/server/combat/WeaponEnvironmentCollision.luau"
    weapon_bounce_service_path = root / "src/server/combat/WeaponBounceService.luau"
    weapon_bounce_controller_path = root / "src/client/combat/WeaponBounceController.luau"
    weapon_bounce_effect_pool_path = root / "src/client/combat/effects/WeaponBounceEffectPool.luau"
    for path in [
        weapon_bounce_config_path,
        environment_asset_service_path,
        weapon_environment_collision_path,
        weapon_bounce_service_path,
        weapon_bounce_controller_path,
        weapon_bounce_effect_pool_path,
    ]:
        if not path.is_file():
            report_error(f"m50 weapon bounce module missing: {path.relative_to(root)}")

    if location_asset_manifest_path.is_file():
        location_asset_manifest = json.loads(location_asset_manifest_path.read_text(encoding="utf-8"))
        if location_asset_manifest.get("schemaVersion") != 4:
            report_error("m52 Location Asset manifest must use schemaVersion 4")
        for row in location_asset_manifest.get("items") or []:
            if not isinstance(row.get("destructible"), bool):
                report_error(f"m50 Location Asset destructible policy missing/invalid for {row.get('slug')}")

    for required in [
        "destructible INTEGER NOT NULL DEFAULT 0",
        'result["destructible"] = bool(result.get("destructible"))',
        'f"\\t\\t\\tdestructible = {str(bool(row.get(\'destructible\'))).lower()},"',
    ]:
        if required not in location_asset_store_text:
            report_error(f"m50 LocationAssetStore destructible policy missing {required}")
    for required in [
        'id="location-asset-destructible"',
        "solid weapon blocker and causes bounce",
        "weapon contact",
    ]:
        if required not in index_m43_text:
            report_error(f"m50 Location Assets destructible UI missing {required}")
    for required in [
        "location-asset-destructible",
        "destructible: $('location-asset-destructible').checked",
        "solid · bounce",
    ]:
        if required not in deco_assets_js_text:
            report_error(f"m50 Location Assets destructible behavior missing {required}")

    # Studio authoring persists only stable identity/editor metadata. Gameplay policy
    # is deliberately not copied to placed Instances.
    for required in [
        'placed:SetAttribute("Game1DecoInstanceId", instanceId)',
        'placed:SetAttribute("Game1DecoAssetSlug", tostring(row.slug or ""))',
        'locationAssetId = tostring(descendant:GetAttribute("Game1DecoAssetSlug") or "")',
    ]:
        if required not in deco_placement_text:
            report_error(f"m50 DecoPlacement identity-only authoring missing {required}")
    for forbidden in [
        'SetAttribute("Destructible"',
        'SetAttribute("Game1DecoAsset",',
        'SetAttribute("Game1DecoCategory",',
        'SetAttribute("Game1DecoModelAssetId",',
        'SetAttribute("Game1DecoTextureAssetId",',
    ]:
        if forbidden in deco_placement_text:
            report_error(f"m50 DecoPlacement still persists gameplay/redundant metadata: {forbidden}")
    for required in ['"schemaVersion": 2', '"locationAssetId": location_asset_id']:
        if required not in deco_layout_store_text:
            report_error(f"m50 deco backup identity schema missing {required}")

    if environment_asset_service_path.is_file():
        environment_asset_service_text = environment_asset_service_path.read_text(encoding="utf-8")
        for required in [
            'LocationAssetRegistry = require',
            'LOCATION_ASSET_ID_ATTRIBUTE = "Game1DecoAssetSlug"',
            'descendant.Anchored = true',
            'function EnvironmentAssetService.GetDefinition',
            'function EnvironmentAssetService.ResolvePart',
            'function EnvironmentAssetService.GetRegisteredSnapshot',
            'registryRevision += 1',
        ]:
            if required not in environment_asset_service_text:
                report_error(f"m50 EnvironmentAssetService missing {required}")
        for forbidden in ['SetAttribute("Destructible"', 'SetAttribute("Game1DecoCategory"']:
            if forbidden in environment_asset_service_text:
                report_error(f"m50 runtime must resolve policy server-side instead of stamping Attributes: {forbidden}")

    if weapon_environment_collision_path.is_file():
        weapon_environment_collision_text = weapon_environment_collision_path.read_text(encoding="utf-8")
        for required in [
            'EnvironmentAssetService.GetRegisteredSnapshot()',
            'Workspace:Blockcast',
            'Workspace:GetPartsInPart',
            'definition.destructible == true',
            'filterRevision',
        ]:
            if required not in weapon_environment_collision_text:
                report_error(f"m50 WeaponEnvironmentCollision missing {required}")

    if weapon_bounce_config_path.is_file():
        weapon_bounce_config_text = weapon_bounce_config_path.read_text(encoding="utf-8")
        for required in [
            'RemoteName = "WeaponBounce"',
            'ReverseSpeedMultiplier = 2',
            'RecoverySeconds = 0.12',
            'ServerReplicationRadius = 160',
            'ClientRenderRadius = 180',
        ]:
            if required not in weapon_bounce_config_text:
                report_error(f"m50 WeaponBounceConfig missing {required}")

    if weapon_bounce_service_path.is_file():
        weapon_bounce_service_text = weapon_bounce_service_path.read_text(encoding="utf-8")
        for required in [
            'payload.attackerUserId = attacker.UserId',
            'WeaponBounceConfig.ServerReplicationRadius',
            'remote:FireClient(player, payload)',
        ]:
            if required not in weapon_bounce_service_text:
                report_error(f"m50 WeaponBounceService replication missing {required}")

    if weapon_bounce_controller_path.is_file():
        weapon_bounce_controller_text = weapon_bounce_controller_path.read_text(encoding="utf-8")
        for required in [
            'attackerUserId == Players.LocalPlayer.UserId',
            'WeaponBounceConfig.ClientRenderRadius',
            'effects:Emit(position, normal, camera.CFrame)',
        ]:
            if required not in weapon_bounce_controller_text:
                report_error(f"m50 WeaponBounceController presentation missing {required}")

    attack_service_text = (root / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
    attack_session_text = (root / "src/server/combat/AttackSessionStore.luau").read_text(encoding="utf-8")
    for required in [
        'WeaponEnvironmentCollision.Query(previousVolume, volume)',
        'AttackSessionStore.BlockForBounce(',
        'WeaponBounceService.Publish(player, {',
        'LastAttackBounced',
    ]:
        if required not in attack_service_text:
            report_error(f"m50 AttackService environment-bounce integration missing {required}")
    for required in ['session.environmentBlocked = true', 'session.damageWindow = nil', 'session.sweepState = nil']:
        if required not in attack_session_text:
            report_error(f"m50 AttackSessionStore bounce invalidation missing {required}")
    if attack_service_text.find('WeaponEnvironmentCollision.Query(previousVolume, volume)') > attack_service_text.find('hitCount += applyDamageInVolume', attack_service_text.find('local function applyAnimatedWeaponSweep')):
        report_error("m50 environment collision must resolve before damage in each weapon sweep substep")

    upper_composer_text = (root / "src/client/character/animation/AttackUpperBodyComposer.luau").read_text(encoding="utf-8")
    character_animation_text = (root / "src/client/character/animation/CharacterAnimationController.luau").read_text(encoding="utf-8")
    attack_controller_text = (root / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
    client_init_text = (root / "src/client/init.client.luau").read_text(encoding="utf-8")
    server_init_text = (root / "src/server/init.server.luau").read_text(encoding="utf-8") + (root / "src/server/bootstrap/ServiceCatalog.luau").read_text(encoding="utf-8")
    for required in ['function AttackUpperBodyComposer.SetPlaybackSpeed', 'sourcePlaybackSpeed <= 0', 'exitBlendRequested = false']:
        if required not in upper_composer_text:
            report_error(f"m50 upper-body reverse playback support missing {required}")
    for required in [
        'function CharacterAnimationController.BounceCurrentAttack',
        'track:AdjustSpeed(-reverseSpeed)',
        'AttackUpperBodyComposer.SetPlaybackSpeed(-reverseSpeed)',
        'AnimationAttackBounced',
    ]:
        if required not in character_animation_text:
            report_error(f"m50 character attack reverse presentation missing {required}")
    for required in ['function AttackController.CancelForBounce', 'activePoseAttackId = 0']:
        if required not in attack_controller_text:
            report_error(f"m50 attack controller bounce cancellation missing {required}")
    for required in ['WeaponBounceController.Start(CharacterAnimationController, AttackController)']:
        if required not in client_init_text:
            report_error(f"m50 client bounce startup missing {required}")
    for required in ['EnvironmentAssetService.Start()', 'WeaponBounceService.Start()']:
        if required not in server_init_text:
            report_error(f"m50 server environment/bounce startup missing {required}")

    if 'control_agent_build = "game1-m50-environment-weapon-bounce-001"' not in host_agent_text:
        report_error("m50 Control Center build marker is stale")
    if "model bridge v24" not in studio_plugin_text:
        report_error("m51 Studio plugin version marker is stale")
    install_plugin_text = (root / "system/studio-plugin/install.ps1").read_text(encoding="utf-8")
    if "model bridge v24" not in install_plugin_text:
        report_error("m51 Studio plugin installer marker is stale")
    return environment_asset_service_text, install_plugin_text
