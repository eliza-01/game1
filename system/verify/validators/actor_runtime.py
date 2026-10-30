"""M166 read-only verification of actor runtime contracts.

All diagnostics flow through the injected sink, in legacy source order.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


def check_actor_runtime_contracts(
    root: Path, report_error: Callable[[str], None], *,
    monster_attributes_text: str, monster_runtime_text: str
) -> None:
    """Validate monster combat, shared pursuit, life states and options."""
    # m23 global UI input guard + monster behavior/debug + RobloxLineage combat AI + damage feedback.
    ui_guard_m23 = (root / "src/client/UiInputGuard.luau").read_text(encoding="utf-8")
    attack_controller_m23 = (root / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
    camera_controller_m23 = (root / "src/client/character/CameraController.luau").read_text(encoding="utf-8")
    movement_controller_m23 = (root / "src/client/character/MovementController.luau").read_text(encoding="utf-8")
    aim_pose_m23 = (root / "src/client/combat/AimPoseController.luau").read_text(encoding="utf-8")
    for required in ["GetGuiObjectsAtPosition", "WorldInputPassthrough", "GetFocusedTextBox", "BlocksWorldInput"]:
        if required not in ui_guard_m23:
            report_error(f"global UI world-input guard missing {required}")
    for text, label in [(attack_controller_m23, "attack"), (camera_controller_m23, "camera"), (movement_controller_m23, "movement")]:
        if "UiInputGuard" not in text:
            report_error(f"{label} controller does not use global UI input guard")
    if 'WorldInputPassthrough", true' not in aim_pose_m23:
        report_error("aim reticle must be an explicit UI world-input passthrough")

    monster_manifest_m23 = json.loads((root / "assets/manifests/monsters.json").read_text(encoding="utf-8"))
    for monster in monster_manifest_m23.get("items") or []:
        behavior = monster.get("behavior") or {}
        for key in ["aggressive", "aggroRadiusStuds", "attackRadiusStuds"]:
            if key not in behavior:
                report_error(f"monster behavior manifest missing {monster.get('slug')}:{key}")
    monster_store_m23 = (root / "system/control-center/monster_store.py").read_text(encoding="utf-8")
    monster_js_m23 = (root / "system/control-center/static/monster-assets.js").read_text(encoding="utf-8")
    monster_html_m23 = (root / "system/control-center/static/index.html").read_text(encoding="utf-8")
    for required in ["monster_behavior", "aggroRadiusStuds", "attackRadiusStuds", "aggressive"]:
        if required not in monster_store_m23:
            report_error(f"Asset Manager monster behavior storage missing {required}")
    for required in ["monster-behavior-aggressive", "monster-behavior-aggro-radius", "monster-behavior-attack-radius"]:
        if required not in monster_js_m23 + monster_html_m23:
            report_error(f"Asset Manager monster behavior UI missing {required}")

    monster_debug_server_m23 = (root / "src/server/dev/MonsterDebugService.luau").read_text(encoding="utf-8")
    monster_debug_client_m23 = (root / "src/client/dev/MonsterDebugController.luau").read_text(encoding="utf-8")
    for required in ["GetMonsterDebugCatalog", "ApplyMonsterDebug", "MonsterAggressive", "MonsterAggroRadius", "MonsterAttackRadius"]:
        if required not in monster_debug_server_m23:
            report_error(f"Monster Debug server contract missing {required}")
    for required in ["☑ AGGRESSIVE", "☐ PASSIVE", "AGGRO RADIUS", "ATTACK RADIUS", "RESET FROM ASSET MANAGER", "Game1MonsterAggroRadiusPreview", "Game1MonsterAttackRadiusPreview"]:
        if required not in monster_debug_client_m23:
            report_error(f"Monster Debug client UI missing {required}")

    monster_ai_m23 = (root / "src/server/monster/MonsterAIService.luau").read_text(encoding="utf-8")
    monster_chase_navigation_m104 = (root / "src/server/monster/MonsterChaseNavigation.luau").read_text(encoding="utf-8")
    monster_agent_lifecycle_m105 = (root / "src/server/monster/MonsterAgentLifecycle.luau").read_text(encoding="utf-8")
    spawner_m23 = (root / "src/server/monster/MonsterSpawnerService.luau").read_text(encoding="utf-8")
    monster_target_policy_m102 = (root / "src/server/monster/MonsterTargetPolicy.luau").read_text(encoding="utf-8")
    monster_state_m102 = (root / "src/server/monster/MonsterCombatState.luau").read_text(encoding="utf-8")
    monster_attack_m103 = (root / "src/server/monster/MonsterAttackExecutor.luau").read_text(encoding="utf-8")
    monster_presentation_m103 = (root / "src/server/monster/MonsterCombatPresentation.luau").read_text(encoding="utf-8")
    for required in ['require(script.Parent:WaitForChild("MonsterChaseNavigation"))', "CombatState.Decide", 'AttackExecutor.Begin(agent, target, AttackMovement, random)', "MonsterAttackExecutor"]:
        if required not in monster_ai_m23:
            report_error(f"RobloxLineage monster AI coordinator missing {required}")
    for required in ["PathfindingService:CreatePath", "path:ComputeAsync", "path.Blocked:Connect", "issueDirectMove(agent, destination, speed)", "MonsterChaseNavigation.Initialize"]:
        if required not in monster_chase_navigation_m104:
            report_error(f"M104 chase navigation contract missing {required}")
    if "PathfindingService" in monster_ai_m23:
        report_error("M104: MonsterAIService must delegate Pathfinding to MonsterChaseNavigation")
    for required in ['require(script.Parent:WaitForChild("MonsterAgentLifecycle"))', 'Lifecycle.Start(runAgent, random)', 'Lifecycle.Release(agent)']:
        if required not in monster_ai_m23:
            report_error(f"M105: MonsterAIService must delegate lifecycle: {required}")
    for required in ['pending[model] = true', 'model:GetAttributeChangedSignal("LifeState")', 'model.Destroying:Connect(',
                     'model.AncestryChanged:Connect(', 'Navigation.Initialize(agent)', 'Presentation.Initialize(agent, runRow, random',
                     'CombatState.ClearTarget(agent)', 'Navigation.ClearPath(agent)', 'connection:Disconnect()',
                     'xpcall(runAgent, debug.traceback, agent)']:
        if required not in monster_agent_lifecycle_m105:
            report_error(f"M105: MonsterAgentLifecycle contract missing {required}")
    if 'if not agent.active then return end' not in monster_chase_navigation_m104:
        report_error("M105: cancelled ComputeAsync must not reconnect Path.Blocked")

    for required in ["pursueDirectlyDuringAttack", "MonsterAttackPursuitActive", "AttackTimelineConfig.ResolveRuntime", "TargetPolicy.AttackStillConnects", "DamageService.Apply("]:
        if required not in monster_attack_m103:
            report_error(f"MonsterAttackExecutor contract missing {required}")
    for required in ["MonsterCombatPresentation.PlayAttack", "MonsterCombatPresentation.PlayRun", "MonsterCombatPresentation.PlayCombatIdle"]:
        if required not in monster_presentation_m103:
            report_error(f"MonsterCombatPresentation contract missing {required}")
    for required in ['local function attackStillConnects(', 'local function acquireNearestTarget(', 'Workspace:Raycast(']:
        if required not in monster_target_policy_m102:
            report_error(f"Monster target policy contract missing {required}")
    for required in ['setState(agent, "Aggro")', 'setState(agent, "Idle")', 'HostilePursuitRegistry.SetTarget(agent.model, target)', 'HostilePursuitRegistry.Clear(agent.model)']:
        if required not in monster_state_m102:
            report_error(f"Monster state contract missing {required}")
    for required in ["MonsterAuthoredAggressive", "MonsterAuthoredAggroRadius", "MonsterAuthoredAttackRadius", "MonsterCombatActive"]:
        if required not in (spawner_m23 + monster_attributes_text):
            report_error(f"monster spawner behavior bridge missing {required}")
    monster_locomotion_m23 = (root / "src/client/monster/MonsterAttackLocomotionController.luau").read_text(encoding="utf-8")
    for required in ["MonsterAttackPursuitActive", "MonsterAttackPursuitPlaybackSpeed", "lowerPaths", "PreSimulation"]:
        if required not in monster_locomotion_m23:
            report_error(f"monster attack lower-body composition missing {required}")

    feedback_server_m23 = (root / "src/server/combat/CombatFeedbackService.luau").read_text(encoding="utf-8")
    feedback_client_m23 = (root / "src/client/combat/CombatFeedbackController.luau").read_text(encoding="utf-8")
    feedback_visuals_m39_path = root / "src/client/combat/CombatFloatingText.luau"
    feedback_visuals_m39 = feedback_visuals_m39_path.read_text(encoding="utf-8") if feedback_visuals_m39_path.is_file() else ""
    damage_m23 = (root / "src/server/combat/DamageService.luau").read_text(encoding="utf-8")
    for required in ["outgoing", "incoming", "PublishDamage"]:
        if required not in feedback_server_m23:
            report_error(f"damage feedback server missing {required}")
    for required in ["IncomingDamageNumber", "Color3.fromRGB(255, 82, 82)", "CombatDamageNumber"]:
        if required not in feedback_visuals_m39:
            report_error(f"damage feedback visuals missing {required}")
    for required in ['WaitForChild("CombatFloatingText")', "ShowDamage", "ShowCritical", "if critical then"]:
        if required not in feedback_client_m23:
            report_error(f"m39 combat feedback controller missing {required}")
    for required in ['gui.Name = "CriticalBillboard"', 'label.Text = "Critical!"', "CRITICAL_LIFETIME", "CRITICAL_RISE_STUDS"]:
        if required not in feedback_visuals_m39:
            report_error(f"m39 Critical! world feedback missing {required}")
    if "CombatFeedbackService.PublishDamage" not in damage_m23:
        report_error("DamageService does not publish authoritative damage feedback")

    # m25 / m73: continuous attack pursuit is now shared by monsters and NPCs.
    monster_ai_m25 = (root / "src/server/monster/MonsterAttackExecutor.luau").read_text(encoding="utf-8")
    actor_pursuit_m73 = (root / "src/server/actor/ActorAttackPursuit.luau").read_text(encoding="utf-8")
    for required in [
        'RunService.Heartbeat:Wait()',
        'agent.attackPursuit:Step(',
        'AttackPursuit.new(root, humanoid)',
    ]:
        if required not in monster_ai_m25:
            report_error(f"monster continuous attack pursuit missing {required}")
    for required in [
        'self.humanoid:Move(direction, false)',
        'targetRoot.AssemblyLinearVelocity',
        'FOLLOW_GAIN',
        'MAX_ACCELERATION',
    ]:
        if required not in actor_pursuit_m73:
            report_error(f"shared continuous attack pursuit missing {required}")
    pursuit_body_m25 = monster_ai_m25.split('local function pursueDirectlyDuringAttack', 1)[-1].split('local function maintainAttackPursuit', 1)[0]
    if 'MoveTo(' in pursuit_body_m25:
        report_error("active-attack pursuit must not stream MoveTo destinations")

    monster_sampler_m25 = (root / "src/client/actor/ActorLocomotionSampler.luau").read_text(encoding="utf-8")
    monster_compositor_m25 = (root / "src/client/monster/MonsterAttackLocomotionController.luau").read_text(encoding="utf-8")
    for required in ['SetPlaybackSpeed', 'AdjustSpeed(speed)']:
        if required not in monster_sampler_m25:
            report_error(f"monster pursuit sampler live-speed contract missing {required}")
    for required in ['suppressHorizontalAttackRootMotion', 'Game1RuntimeAnimationRoot', 'transform.Position.Y', 'entry.sampler:SetPlaybackSpeed']:
        if required not in monster_compositor_m25:
            report_error(f"monster pursuit visual stabilization missing {required}")
    if 'releaseSampler(entry)\n\t\t\tif model:GetAttribute("MonsterAttackPursuitActive")' in monster_compositor_m25:
        report_error("pursuit playback changes must not rebuild the locomotion sampler")

    character_service_m25 = (root / "src/server/character/CharacterService.luau").read_text(encoding="utf-8")
    death_respawn_path_m25 = root / "src/client/character/DeathRespawnController.luau"
    death_respawn_m25 = death_respawn_path_m25.read_text(encoding="utf-8") if death_respawn_path_m25.is_file() else ""
    character_animation_m25 = (root / "src/client/character/animation/CharacterAnimationController.luau").read_text(encoding="utf-8")
    for required in ["ReturnToTownAvailable", "CharacterService.ReturnToTown", 'RemoteFunction', 'returnToTown.OnServerInvoke']:
        if required not in character_service_m25:
            report_error(f"return-to-town server contract missing {required}")
    if 'createCharacter(player, tostring(player:GetAttribute("SelectedCharacterArchetype") or ""))' in character_service_m25.split('local function beginPlayerDeathIdle', 1)[-1].split('createCharacter = function', 1)[0]:
        report_error("player death lifecycle must not auto-respawn after DeathIdle")
    for required in ["Game1DeathRespawn", "В город", "ReturnToTown", 'LifeState") or "") == "DeathIdle"']:
        if required not in death_respawn_m25:
            report_error(f"return-to-town client UI missing {required}")
    for required in ['reviveOnSpawn', 'LifeState", "Reviving"', 'RevivePending', 'ReviveAnimationFinished', 'createCharacter(player, requested, true)']:
        if required not in character_service_m25:
            report_error(f"return-to-town revive server contract missing {required}")
    for required in ['current == "Reviving"', 'playBaseLifeAction("revive"', 'notifyReviveAnimationFinished', 'lastLifeState == "Reviving"']:
        if required not in character_animation_m25:
            report_error(f"return-to-town revive animation contract missing {required}")
    client_init_m25 = (root / "src/client/init.client.luau").read_text(encoding="utf-8")
    if "DeathRespawnController.Start()" not in client_init_m25:
        report_error("death respawn controller is not started")

    # m26 common Options + authoritative combat-state idle + global character death/revive playback.
    options_manifest_path_m26 = root / "assets/manifests/options.json"
    if not options_manifest_path_m26.is_file():
        report_error("m26 Options manifest is missing")
        options_manifest_m26 = {}
    else:
        options_manifest_m26 = json.loads(options_manifest_path_m26.read_text(encoding="utf-8"))
    combat_options_m26 = options_manifest_m26.get("combat") or {}
    life_options_m26 = options_manifest_m26.get("characterAnimations") or {}
    if float(combat_options_m26.get("stateDurationSeconds") or -1) != 6.0:
        report_error("m26 combat state default duration must be 6 seconds")
    for key in ["deathPlaybackPercent", "revivePlaybackPercent"]:
        value = float(life_options_m26.get(key) or 0)
        if value < 1 or value > 400:
            report_error(f"m26 character life playback option invalid: {key}")

    options_store_m26 = (root / "system/control-center/options_store.py").read_text(encoding="utf-8")
    options_html_m26 = (root / "system/control-center/static/index.html").read_text(encoding="utf-8")
    options_js_m26 = (root / "system/control-center/static/options.js").read_text(encoding="utf-8")
    host_agent_m26 = (root / "system/control-center/host_agent.py").read_text(encoding="utf-8")
    for required in ["stateDurationSeconds", "deathPlaybackPercent", "revivePlaybackPercent", "GameOptionsRegistry.luau"]:
        if required not in options_store_m26:
            report_error(f"m26 Options storage missing {required}")
    for required in ["nav-options", "options-view", "combat state duration", "death playback %", "revive playback %"]:
        if required not in options_html_m26:
            report_error(f"m26 Options UI missing {required}")
    for required in ["/api/options", "save-combat-options", "save-character-life-options"]:
        if required not in options_js_m26 + host_agent_m26:
            report_error(f"m26 Options API/UI missing {required}")

    combat_state_service_m26 = (root / "src/server/combat/CombatStateService.luau").read_text(encoding="utf-8")
    damage_service_m26 = (root / "src/server/combat/DamageService.luau").read_text(encoding="utf-8")
    for required in ["GameOptions.CombatStateDurationSeconds", 'SetAttribute("InCombat", true)', 'SetAttribute("CombatState", "Combat")', "CombatUntilServerTime", "ActivatePair"]:
        if required not in combat_state_service_m26:
            report_error(f"m26 combat-state service missing {required}")
    if "CombatStateService.ActivatePair(attacker, target)" not in damage_service_m26:
        report_error("m26 DamageService must activate combat state for damage dealer and receiver")

    character_animation_m26 = (root / "src/client/character/animation/CharacterAnimationController.luau").read_text(encoding="utf-8")
    for required in ['GetAttribute("InCombat") == true', 'return "combat_idle"', "GameOptions.CharacterLifePlaybackPercent"]:
        if required not in character_animation_m26:
            report_error(f"m26 character combat/life animation contract missing {required}")
    monster_spawner_m26 = monster_runtime_text
    for required in ["playCombatIdleState", "combatIdleTrack", 'GetAttribute("InCombat")', 'MonsterAnimationState", "combat_idle"']:
        if required not in monster_spawner_m26:
            report_error(f"m26 monster combat-idle contract missing {required}")

    game_options_m26 = (root / "src/shared/GameOptions.luau").read_text(encoding="utf-8")
    game_options_registry_m26 = (root / "src/shared/GameOptionsRegistry.luau").read_text(encoding="utf-8")
    for required in ["CombatStateDurationSeconds", "CharacterLifePlaybackPercent"]:
        if required not in game_options_m26:
            report_error(f"m26 shared GameOptions missing {required}")
    for required in ["stateDurationSeconds", "deathPlaybackPercent", "revivePlaybackPercent"]:
        if required not in game_options_registry_m26:
            report_error(f"m26 generated options registry missing {required}")
