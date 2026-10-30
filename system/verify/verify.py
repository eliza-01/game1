from pathlib import Path
import json
import re
import sys

from validators.actor_runtime import check_actor_runtime_contracts
from validators.deco_studio import check_deco_studio
from validators.environment_bounce import check_environment_bounce
from validators.location_authoring import check_location_authoring
from validators.location_assets import check_location_assets_core
from validators.location_asset_categories import check_location_asset_categories
from validators.location_asset_variants import check_location_asset_variants
from validators.location_texture_sync import check_location_texture_sync
from validators.attack_timelines import check_attack_timelines
from validators.authoring_tooling import check_authoring_tooling
from validators.death_runtime import check_death_runtime
from validators.studio_debug import check_studio_debug
from validators.animations import check_animation_scaling, check_character_animation, check_manual_animation_reimport
from validators.characters import (
    check_character_manifest, check_character_rig, check_character_publication,
    check_character_identity, check_character_starting_stats,
)
from validators.weapons import check_weapon_registration, check_weapon_attack_movement
from validators.combat_contact import check_combat_contact_contracts
from validators.monsters import check_monster_contracts
from validators.project_layout import check_project_identity, check_project_layout
from validators.source_only import check_source_only_contract

ROOT = Path(__file__).resolve().parents[2]
errors = []


def err(message: str) -> None:
    errors.append(message)


# M165: project identity is checked before archetype data for stable diagnostics.
check_project_identity(ROOT, err)

archetypes, active_id = check_character_manifest(ROOT, err)

# M165: project layout, forbidden legacy references, and runtime inventory.
check_project_layout(ROOT, err)

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

character_service_text, rig_text = check_character_rig(ROOT, err)

hitbox_text = (ROOT / "src/server/combat/EntityHitboxService.luau").read_text(encoding="utf-8")
hitbox_geometry_text = (ROOT / "src/server/combat/HitboxMeshGeometryCache.luau").read_text(encoding="utf-8")
hitbox_builder_text = (ROOT / "src/server/combat/HitboxDefinitionBuilder.luau").read_text(encoding="utf-8")
hitbox_frames_text = (ROOT / "src/server/combat/HitboxRuntimeFrames.luau").read_text(encoding="utf-8")
hitbox_queries_text = (ROOT / "src/server/combat/HitboxSpatialQueries.luau").read_text(encoding="utf-8")
hitbox_implementation_text = "\n".join((hitbox_text, hitbox_geometry_text, hitbox_builder_text, hitbox_frames_text, hitbox_queries_text))
head_resolver_text = (ROOT / "src/shared/combat/SkeletonHeadResolver.luau").read_text(encoding="utf-8")
# M99: expensive mesh loading/definition, per-frame transforms and spatial
# queries have distinct owners. Runtime coordination remains in the facade.
for required in (
    'HitboxMeshGeometryCache.Read(meshPart)',
    'HitboxDefinitionBuilder.Resolve(binding)',
    'HitboxSpatialQueries.BoxContact(binding, boxCFrame, boxSize, originPosition, frameSerial)',
    'HitboxSpatialQueries.AimContact(binding, rayOrigin, direction, distanceLimit, frameSerial)',
):
    if required not in hitbox_text:
        err(f"m99 hitbox facade missing delegation {required}")
for forbidden in ('CreateEditableMeshAsync', 'local function obbIntersects(', 'local function buildDefinition(', 'definitionCache ='):
    if forbidden in hitbox_text:
        err(f"m99 facade still owns separate concern: {forbidden}")
for module_name, module_text, required in (
    ("geometry cache", hitbox_geometry_text, ("geometryCache", "CreateEditableMeshAsync", "GetVertexBones")),
    ("definition builder", hitbox_builder_text, ("definitionCache", "buildDefinition", "strongestInfluence")),
    ("frame cache", hitbox_frames_text, ("worldFrameSerial", "TransformedBoneFrame", "Refresh")),
    ("spatial queries", hitbox_queries_text, ("obbIntersects", "rayBoxDistance", "BoxContact", "AimContact")),
):
    for token in required:
        if token not in module_text:
            err(f"m99 {module_name} missing {token}")
for required in [
    "CreateEditableMeshAsync",
    "GetVertexBones",
    "GetVertexBoneWeights",
    "GetBoneCFrame",
    "definitionCache",
    "precomputed_bone_boxes",
    "obbIntersects",
    "strongestInfluence",
    "excludedTargets",
]:
    if required not in hitbox_implementation_text:
        err(f"precomputed combat-hitbox runtime missing {required}")
for forbidden in [
    "triangleBoxIntersectionCentroid",
    "clipAgainstPlane",
    "deformed_mesh_surface",
    "CombatMesh",
    "PoseHitbox",
    "root_fallback",
    "virtual_bone_regions",
    'Instance.new("Part")',
]:
    if forbidden in hitbox_text:
        err(f"obsolete combat-hitbox runtime remains: {forbidden}")
for required in ["Resolve", "TransformedBoneFrame", 'token == "head"', 'token == "face"']:
    if required not in head_resolver_text:
        err(f"head-bone resolver missing {required}")

bridge = ROOT / "system/control-center/studio_bridge.py"
plugin = ROOT / "system/studio-plugin/Game1Bridge.server.luau"
template_module = ROOT / "system/studio-plugin/modules/CharacterTemplate.luau"
if not bridge.is_file() or "run_model_load_bridge" not in bridge.read_text(encoding="utf-8"):
    err("reference-style Studio model load bridge is missing")
plugin_text = plugin.read_text(encoding="utf-8") if plugin.is_file() else ""
# M100: model import and Studio preference contracts reside in packaged modules.
plugin_text += "\n" + "\n".join(
    (ROOT / "system/studio-plugin/modules" / name).read_text(encoding="utf-8")
    for name in ("StudioModelLoadCommands.luau", "StudioActorSpawnCommands.luau", "StudioDebugPreferenceBridge.luau")
)
template_text = template_module.read_text(encoding="utf-8") if template_module.is_file() else ""
for required in ["AssetService:LoadAssetAsync", "ImportedRig", "AnimationController", "Game1CharacterRig", "CharacterTemplate.EnsureCanonicalRoot"]:
    if required not in plugin_text:
        err(f"game1 Studio character bridge missing {required}")
for required in ["ImportedRigRootWeld", "Game1GeneratedCharacterRoot", "Game1TemplateBasisMode", "Game1RigBasisMode", "authored_basis"]:
    if required not in template_text:
        err(f"game1 Studio character template module missing {required}")
for forbidden in [
    "normalizeSkeletonOrientation",
    "resolveSkeletonUp",
    "head_to_feet",
    "spine_to_feet",
    "importedRig:PivotTo(",
]:
    if forbidden in template_text:
        err(f"Studio rig sync must preserve authored FBX basis; forbidden orientation correction remains: {forbidden}")
if 'BRIDGE_URL = "http://127.0.0.1:43137"' not in plugin_text:
    err("game1 Studio bridge must use isolated port 43137")
plugin_project = ROOT / "system/studio-plugin/plugin.project.json"
plugin_project_text = plugin_project.read_text(encoding="utf-8") if plugin_project.is_file() else ""
if '"$path": "modules/CharacterTemplate.luau"' not in plugin_project_text:
    err("game1 Studio plugin project must package the character template module")

host_agent_text = (ROOT / "system/control-center/host_agent.py").read_text(encoding="utf-8") + "\n" + "\n".join(p.read_text(encoding="utf-8") for folder in ("api", "services") for p in (ROOT / "system/control-center" / folder).glob("*.py"))
if "sync_character_to_studio" not in host_agent_text or 'sync_suffix = "/sync"' not in host_agent_text:
    err("character publication must expose reference-style Studio sync")

schema_text, ui, js, character_js_text = check_character_publication(
    ROOT, err, host_agent_text=host_agent_text, plugin_text=plugin_text, archetypes=archetypes,
)


(
    animation_store_text, animation_registry_text, controller_runtime,
    client_init_text, attack_controller_text, movement_runtime, js_text,
) = check_character_animation(
    ROOT, err, schema_text=schema_text, ui=ui, js=js, character_service_text=character_service_text,
)

check_character_identity(ROOT, err, schema_text=schema_text, ui=ui, host_agent_text=host_agent_text, js_text=js_text)

stats_config_text, stats_service_text, movement_config_text = check_weapon_registration(
    ROOT, err, schema_text=schema_text, ui=ui, host_agent_text=host_agent_text,
    plugin_text=plugin_text, rig_text=rig_text, character_service_text=character_service_text,
    attack_text=attack_text, controller_runtime=controller_runtime,
    attack_controller_text=attack_controller_text, client_init_text=client_init_text,
)

server_init_text = check_studio_debug(
    ROOT, err, plugin_text=plugin_text,
    stats_service_text=stats_service_text, client_init_text=client_init_text,
)


# m12 shared animation-speed scaling: gameplay stat -> playback percentage
check_animation_scaling(
    ROOT, err, ui=ui, host_agent_text=host_agent_text, character_js_text=character_js_text,
    animation_registry_text=animation_registry_text, attack_timeline_text=attack_timeline_text,
)


monster_sources = check_monster_contracts(
    ROOT, err, schema_text=schema_text, host_agent_text=host_agent_text,
    plugin_text=plugin_text, ui=ui, server_init_text=server_init_text,
    stats_config_text=stats_config_text, stats_service_text=stats_service_text,
    animation_store_text=animation_store_text,
)

character_service_text = check_death_runtime(
    ROOT, err, animation_store_text=animation_store_text,
    monster_sources=monster_sources, damage_resolver_text=damage_resolver_text,
)

# Every registered attack animation is required to have an authoritative timeline.
for manifest_name in ["character-animations.json", "monster-animations.json"]:
    manifest_path = ROOT / "assets/manifests" / manifest_name
    if not manifest_path.is_file():
        continue
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for binding in manifest.get("bindings") or []:
        if str(binding.get("slot") or "") != "attack":
            continue
        clip_id = str(binding.get("clipId") or binding.get("clip_id") or "")
        if clip_id and f'["{clip_id}"]' not in attack_timeline_data_text:
            err(f"registered attack clip has no authoritative timeline: {clip_id}")

check_character_starting_stats(ROOT, err, character_service_text=character_service_text, stats_service_text=stats_service_text)

studio_plugin_text = check_manual_animation_reimport(
    ROOT, err, animation_store_text=animation_store_text,
    character_js_text=character_js_text, host_agent_text=host_agent_text,
)

check_weapon_attack_movement(ROOT, err, host_agent_text=host_agent_text)

check_actor_runtime_contracts(
    ROOT, err, monster_attributes_text=monster_sources.attributes_text,
    monster_runtime_text=monster_sources.runtime_text,
)

check_combat_contact_contracts(
    ROOT, err, damage_resolver_text=damage_resolver_text,
    hitbox_implementation_text=hitbox_implementation_text,
)

index_m35_text, studio_bridge_m35_text = check_attack_timelines(
    ROOT, err, attack_timeline_text=attack_timeline_text,
    attack_timeline_data_text=attack_timeline_data_text,
    studio_plugin_text=studio_plugin_text, host_agent_text=host_agent_text,
)


check_authoring_tooling(ROOT, err)


check_location_authoring(
    ROOT, err, index_text=index_m35_text, host_agent_text=host_agent_text,
    studio_bridge_text=studio_bridge_m35_text, studio_plugin_text=studio_plugin_text,
)

location_assets = check_location_assets_core(
    ROOT, err, host_agent_text=host_agent_text, studio_plugin_text=studio_plugin_text,
)

check_deco_studio(
    ROOT, err, sources=location_assets, host_agent_text=host_agent_text,
    studio_plugin_text=studio_plugin_text,
)

check_location_asset_variants(
    ROOT, err, sources=location_assets, host_agent_text=host_agent_text,
    studio_plugin_text=studio_plugin_text,
)

environment_asset_service_text, install_plugin_text = check_environment_bounce(
    ROOT, err, sources=location_assets, host_agent_text=host_agent_text,
    studio_plugin_text=studio_plugin_text,
)

check_location_texture_sync(
    ROOT, err, sources=location_assets,
    environment_asset_service_text=environment_asset_service_text,
)

# M164: M52/M53 source-only invariants now live in one read-only validator.
check_source_only_contract(
    ROOT, err,
    location_asset_store_text=location_assets.store_text,
    deco_assets_js_text=location_assets.assets_js,
    host_agent_text=host_agent_text,
    character_js_text=character_js_text,
    ui_html=ui,
)

if errors:
    print("verify failed")
    for item in errors:
        print(" -", item)
    sys.exit(1)

check_location_asset_categories(
    ROOT, err, sources=location_assets, character_js_text=character_js_text,
    studio_plugin_text=studio_plugin_text, install_plugin_text=install_plugin_text,
)

print("verify ok · game1 m55 Buildings + synchronized Location Asset category context passed")
print("registered character archetypes:", len(archetypes))
print("active character archetype:", active_id or "none")
print("race pool: human")
print("gender pool: male, female")
print("canonical place: place/game1.rbxl")
