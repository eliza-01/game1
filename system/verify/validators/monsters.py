"""M166 read-only verification of monsters contracts.

All diagnostics flow through the injected sink, in legacy source order.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class MonsterSources:
    """Read-only source snapshots consumed by later cross-domain checks."""
    spawner_text: str
    runtime_text: str
    attributes_text: str


def check_monster_contracts(
    root: Path, report_error: Callable[[str], None], *,
    schema_text: str, host_agent_text: str, plugin_text: str, ui: str,
    server_init_text: str, stats_config_text: str, stats_service_text: str,
    animation_store_text: str
) -> MonsterSources:
    """Validate authored monster data, UI contracts and bounded spawn runtime."""
    # m7 monster registry / animation / character life + critical contract
    monster_manifest_path = root / "assets/manifests/monsters.json"
    if not monster_manifest_path.is_file():
        report_error(r"monster manifest is missing; run python .\system\control-center\migrate.py")
        monster_manifest = {}
    else:
        monster_manifest = json.loads(monster_manifest_path.read_text(encoding="utf-8"))
    if monster_manifest.get("schemaVersion") != 1 or monster_manifest.get("project") != "game1":
        report_error("monster manifest must be game1 schema 1")
    monster_options = monster_manifest.get("options") or {}
    if monster_options.get("statKeys") != ["MaxHP", "Damage", "AttackSpeed", "RunSpeed", "CritChance"]:
        report_error("monster stat keys must be HP, attack, attack speed, run speed and crit chance")

    monster_store_path = root / "system/control-center/monster_store.py"
    monster_store_text = monster_store_path.read_text(encoding="utf-8") if monster_store_path.is_file() else ""
    for required in [
        "class MonsterStore",
        'STAT_KEYS = ("MaxHP", "Damage", "AttackSpeed", "RunSpeed", "CritChance")',
        "analyze_character_fbx",
        "prepare_character_publication_fbx",
        "create_model_asset",
        "update_model_asset",
        "create_image_asset",
        "update_image_asset",
        'src/shared/monster/MonsterRegistry.luau',
    ]:
        if required not in monster_store_text:
            report_error(f"monster store missing {required}")
    for required in ["monsters", "monster_textures", "monster_stats", "monster_publications"]:
        if required not in schema_text:
            report_error(f"control center schema missing {required}")

    monster_registry_path = root / "src/shared/monster/MonsterRegistry.luau"
    monster_registry_text = monster_registry_path.read_text(encoding="utf-8") if monster_registry_path.is_file() else ""
    if "monsters = table.freeze" not in monster_registry_text:
        report_error("generated monster registry is missing")

    monster_animation_manifest_path = root / "assets/manifests/monster-animations.json"
    if not monster_animation_manifest_path.is_file():
        report_error(r"monster animation manifest is missing; run python .\system\control-center\migrate.py")
        monster_animation_manifest = {}
    else:
        monster_animation_manifest = json.loads(monster_animation_manifest_path.read_text(encoding="utf-8"))
    if monster_animation_manifest.get("schemaVersion") != 1 or monster_animation_manifest.get("project") != "game1":
        report_error("monster animation manifest must be game1 schema 1")
    for binding in monster_animation_manifest.get("bindings") or []:
        if "playbackSpeedPercent" in binding or "playback_speed_percent" in binding:
            report_error(f"monster animation binding must not own playback speed: {binding.get('id')}")
    monster_slot_catalog = monster_animation_manifest.get("slotCatalog") or []
    monster_slots = [row.get("slot") for row in monster_slot_catalog]
    if monster_slots != ["idle", "idle_special", "walk", "run", "combat_idle", "attack", "death"]:
        report_error("monster animation storage slots must use combat_idle and must not expose attack_wait")
    monster_states = [row.get("state") for row in monster_slot_catalog]
    if monster_states != ["idle", "idle", "walk", "run", "combat_idle", "attack", "death"]:
        report_error("monster idle_special must stay inside idle and combat waiting must be combat_idle")
    monster_assets_js_path = root / "system/control-center/static/monster-assets.js"
    monster_assets_js_text = monster_assets_js_path.read_text(encoding="utf-8") if monster_assets_js_path.is_file() else ""
    monster_index_text = (root / "system/control-center/static/index.html").read_text(encoding="utf-8")
    for required in ["animationMonster", "monster-animation-monster", "monsterSelectAnimationTarget", "MONSTER_ANIMATION_TARGET_KEY"]:
        if required not in monster_assets_js_text and required not in monster_index_text:
            report_error(f"monster animation UI missing explicit target selector contract: {required}")
    if "semantic monster profile" in monster_index_text:
        report_error("monster animation UI must not expose obsolete semantic monster profile jargon")

    monster_animation_store_path = root / "system/control-center/monster_animation_store.py"
    monster_animation_store_text = monster_animation_store_path.read_text(encoding="utf-8") if monster_animation_store_path.is_file() else ""
    for required in [
        "class MonsterAnimationStore", "def scan_folder", "def assign_file", "def publish_missing",
        '"slot": "idle"', '"slot": "idle_special"', '"state": "idle"', '"role": "special"', '"slot": "combat_idle"', '"variants": True', "canonicalFilename",
        '"sourceSlot": internal_slot', 'profile["slots"].setdefault(state', 'src/shared/monster/MonsterAnimationRegistry.luau',
    ]:
        if required not in monster_animation_store_text:
            report_error(f"monster animation store missing {required}")
    for required in ["monster_animation_profiles", "monster_animation_clips", "monster_animation_bindings", "monster_animation_publications"]:
        if required not in schema_text:
            report_error(f"control center schema missing {required}")
    monster_animation_registry_path = root / "src/shared/monster/MonsterAnimationRegistry.luau"
    monster_animation_registry_text = monster_animation_registry_path.read_text(encoding="utf-8") if monster_animation_registry_path.is_file() else ""
    if "profiles = table.freeze" not in monster_animation_registry_text:
        report_error("generated monster animation registry is missing")

    monster_js_path = root / "system/control-center/static/monster-assets.js"
    monster_js_text = monster_js_path.read_text(encoding="utf-8") if monster_js_path.is_file() else ""
    for required in ['id="nav-monsters"', 'id="monsters-view"', 'id="register-monster"', 'id="monster-stat-hp"', 'id="monster-stat-damage"', 'id="monster-stat-attack-speed"', 'id="monster-stat-run-speed"', 'id="monster-stat-crit-chance"', 'id="monster-animation-filename-guide"']:
        if required not in ui:
            report_error(f"asset manager monster UI missing {required}")
    for required in ["monsterRegister", "monsterPublish", "monsterSync", "monsterScanAnimations", "monsterPublishMissingAnimations", "MONSTER_FILENAME_GUIDE_KEY", "MONSTER_ANIMATION_FOLDER_KEY", "initMonsterAnimationFolderExplorer", "row.state||row.slot", "rule.state"]:
        if required not in monster_js_text:
            report_error(f"asset manager monster javascript missing {required}")
    for forbidden in ["monsterSetAnimationSpeed", "data-speed"]:
        if forbidden in monster_js_text:
            report_error(f"asset manager monster clip table must not expose per-clip speed control: {forbidden}")
    for required in ['id="monster-animation-folder-path"', 'id="choose-monster-animation-folder"', 'id="scan-monster-animations"']:
        if required not in ui:
            report_error(f"monster animation folder explorer missing {required}")
    for required in ["GAME1_ANIMATION_PICKER_INITIAL_PATH", "choose_animation_folder(initial_path", '"initialPath"']:
        if required not in host_agent_text:
            report_error(f"host agent animation folder explorer missing {required}")
    for required in ["MonsterStore", "MonsterAnimationStore", "sync_monster_to_studio", 'placement_mode="monster-rig"', '"/api/monsters"', '"/api/monster-animations"']:
        if required not in host_agent_text:
            report_error(f"host agent monster API missing {required}")
    for required in ["monster-rig", "placeMonsterRig", "Game1MonsterRig", "MonsterSlug", "applyWeaponTextures(importedRig"]:
        if required not in plugin_text:
            report_error(f"studio bridge monster-rig placement missing {required}")

    # m7 monster spawn authoring/runtime contract
    monster_spawn_manifest_path = root / "assets/manifests/monster-spawns.json"
    if not monster_spawn_manifest_path.is_file():
        report_error("monster spawn manifest is missing")
        monster_spawn_manifest = {}
    else:
        monster_spawn_manifest = json.loads(monster_spawn_manifest_path.read_text(encoding="utf-8"))
    if monster_spawn_manifest.get("schemaVersion") != 1 or monster_spawn_manifest.get("project") != "game1":
        report_error("monster spawn manifest must be game1 schema 1")
    if not isinstance(monster_spawn_manifest.get("records"), dict):
        report_error("monster spawn manifest records must be an object")

    spawn_store_path = root / "system/control-center/monster_spawn_store.py"
    spawn_store_text = spawn_store_path.read_text(encoding="utf-8") if spawn_store_path.is_file() else ""
    for required in ["class MonsterSpawnStore", "respawnSeconds", "spawnRadius", "maxAlive", "monster_usage", "MonsterSpawnRegistry.luau"]:
        if required not in spawn_store_text:
            report_error(f"monster spawn store missing {required}")

    monster_spawn_js_path = root / "system/control-center/static/monster-spawns.js"
    monster_spawn_js_text = monster_spawn_js_path.read_text(encoding="utf-8") if monster_spawn_js_path.is_file() else ""
    for required in ['id="monster-spawn-monster"', 'id="monster-spawn-place"', 'id="monster-spawn-register"', 'id="monster-spawn-radius"', 'id="monster-spawn-max-alive"']:
        if required not in ui:
            report_error(f"monster spawn UI missing {required}")
    for required in ["/api/monster-spawns/place", "/api/monster-spawns/register", "restore", "validate"]:
        if required not in monster_spawn_js_text:
            report_error(f"monster spawn UI javascript missing {required}")
    for required in ['"/api/monster-spawns"', '"/api/monster-spawns/place"', '"/api/monster-spawns/register"', "MonsterSpawnStore", "run_monster_spawn_bridge"]:
        if required not in host_agent_text:
            report_error(f"host agent monster spawn API missing {required}")
    for required in ["monster-spawn", "Game1MonsterSpawnMarker", "Game1Authoring", "MonsterSpawns", "monsterSpawnPlacementResult", "Selection:Set"]:
        if required not in plugin_text:
            report_error(f"Studio monster spawn authoring missing {required}")

    monster_spawner_path = root / "src/server/monster/MonsterSpawnerService.luau"
    monster_spawner_text = monster_spawner_path.read_text(encoding="utf-8") if monster_spawner_path.is_file() else ""
    # M90: validate the monster runtime as several bounded modules rather than
    # assuming every implementation detail remains inside the orchestrator.
    monster_rig_text = (root / "src/server/monster/MonsterRigBuilder.luau").read_text(encoding="utf-8")
    monster_geometry_text = (root / "src/server/monster/MonsterSpawnGeometry.luau").read_text(encoding="utf-8")
    monster_track_factory_text = (root / "src/server/monster/MonsterAnimationTrackFactory.luau").read_text(encoding="utf-8")
    monster_attributes_text = (root / "src/server/monster/MonsterInitialAttributes.luau").read_text(encoding="utf-8")
    # M91: wander / death implementations moved out of the population coordinator.
    monster_wander_text = (root / "src/server/monster/MonsterWanderController.luau").read_text(encoding="utf-8")
    monster_death_text = (root / "src/server/monster/MonsterDeathLifecycle.luau").read_text(encoding="utf-8")
    # M92: idle/combat-idle presentation, native track callbacks and idle RNG moved out of spawner.
    monster_idle_presentation_text = (root / "src/server/monster/MonsterIdlePresentation.luau").read_text(encoding="utf-8")
    # M93: slot accounting and respawn scheduling live in a separate population controller.
    monster_population_text = (root / "src/server/monster/MonsterPopulationController.luau").read_text(encoding="utf-8")
    monster_runtime_text = "\n".join((monster_spawner_text, monster_rig_text, monster_geometry_text, monster_track_factory_text, monster_attributes_text, monster_wander_text, monster_death_text, monster_idle_presentation_text, monster_population_text))
    if 'finite(stats.RunSpeed, CharacterMovementConfig.DefaultRunSpeed)' not in monster_runtime_text:
        report_error("monster RunSpeed fallback must use the shared direct-speed contract")
    for required in ["MonsterSpawnRegistry", "MonsterRegistry", "MonsterAnimationRegistry", "spawnRadius", "maxAlive", "respawnSeconds", "math.sqrt", "Workspace:Raycast", "EntityHitboxService.Attach", 'GetAttributeChangedSignal("LifeState")', '== "Dying"', 'publishedRows(profile, "idle")', 'weightedIdleChoice', 'MonsterAnimationState', 'MonsterIdleVariant', 'idleTrack.DidLoop', 'choice.track.Ended', 'playBaseIdle']:
        if required not in monster_runtime_text:
            report_error(f"monster runtime spawner missing {required}")
    for required in ["HumanoidRootPart", 'Instance.new("Humanoid")', "humanoid:MoveTo", "MoveToFinished", "WANDER_PAUSE_MIN_SECONDS", "WANDER_PAUSE_MAX_SECONDS", "WANDER_MOVE_REFRESH_SECONDS", "CharacterMovementConfig.RobloxSpeed", 'firstPublishedTrack(profile, "walk")', "MonsterWanderEnabled"]:
        if required not in monster_runtime_text:
            report_error(f"monster random-wander runtime missing {required}")
    for required in [
        'firstPublishedTrack(profile, "run")',
        'GetAttributeChangedSignal("RunSpeed")',
        'GetAttributeChangedSignal("MonsterLocomotionMode")',
        "refreshWanderLocomotion",
        "locomotionSpeedFor",
        "runTrack",
        "Game1MonsterDebugLocomotionMode",
        "AnimationPlaybackSpeedPercent",
        "AnimationSpeedScaling",
    ]:
        if required not in monster_runtime_text:
            report_error(f"monster live movement-debug locomotion missing {required}")
    for required in ['VisualRootWeld', 'animatorFor(runtimeModel, visual)', 'controller.Parent = visual']:
        if required not in monster_runtime_text:
            report_error(f"monster animated-navigation bridge missing {required}")
    if "Game1MonsterVisualWeld" in monster_runtime_text:
        report_error("monster navigation must never rigid-weld every visual BasePart; weld only the rig root")
    for required in ['Workspace:FindFirstChild("Game1Authoring")', 'authoring:FindFirstChild("MonsterSpawns")', "monsterSpawns:Destroy()", "removeAuthoringVisualsFromSimulation"]:
        if required not in monster_runtime_text:
            report_error(f"Play/Run monster-spawn authoring-visual cleanup missing {required}")
    if "RunService.Heartbeat" in monster_runtime_text:
        report_error("monster spawn/wander runtime must not use a permanent Heartbeat loop")
    if "MonsterSpawnerService.Start()" not in server_init_text:
        report_error("monster spawner is not started by the server runtime")

    if "unicodedata.normalize" not in monster_store_text or "CYRILLIC_SLUG_MAP" not in monster_store_text:
        report_error("monster slug generation must normalize/transliterate English-name input robustly")
    if "normalize('NFKD')" not in monster_js_text:
        report_error("monster slug preview must normalize unicode names")

    for required in ["CritChance = 0"]:
        if required not in stats_config_text:
            report_error(f"character critical stat missing {required}")
    if 'setBase(character, "CritChance", value("CritChance"))' not in stats_service_text:
        report_error("character critical chance is not initialized from archetype starting stats")
    for required in ['"slot": "death"', '"slot": "revive"']:
        if required not in animation_store_text:
            report_error(f"character life animation catalog missing {required}")
    if '"slot": "equip"' in animation_store_text or '"slot": "unequip"' in animation_store_text:
        report_error("character animation catalog must not expose equip/unequip states")

    return MonsterSources(
        spawner_text=monster_spawner_text,
        runtime_text=monster_runtime_text,
        attributes_text=monster_attributes_text,
    )
