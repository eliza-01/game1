from pathlib import Path
import json
import re
import sys

from validators.actor_runtime import check_actor_runtime_contracts
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


# m41 Location registration: RobloxLineage polygon authoring flow adapted to game1.
location_manifest_path = ROOT / "assets/manifests/locations.json"
location_store_path = ROOT / "system/control-center/location_store.py"
location_js_path = ROOT / "system/control-center/static/locations.js"
location_css_path = ROOT / "system/control-center/static/location-assets.css"
location_plugin_path = ROOT / "system/studio-plugin/modules/LocationCommands.luau"
location_registry_path = ROOT / "src/shared/world/LocationRegistry.luau"
for path in [location_manifest_path, location_store_path, location_js_path, location_css_path, location_plugin_path, location_registry_path]:
    if not path.is_file():
        err(f"m41 Location authoring file missing: {path.relative_to(ROOT)}")
if location_manifest_path.is_file():
    location_manifest = json.loads(location_manifest_path.read_text(encoding="utf-8"))
    if location_manifest.get("schemaVersion") != 1 or location_manifest.get("project") != "game1" or not isinstance(location_manifest.get("records"), dict):
        err("m41 locations.json schema/project is invalid")
location_store_text = location_store_path.read_text(encoding="utf-8") if location_store_path.is_file() else ""
for required in [
    "class LocationStore",
    "_validate_polygon",
    "must not self-intersect",
    "def draw",
    "def register",
    "def restore",
    "LocationRegistry.luau",
]:
    if required not in location_store_text:
        err(f"m41 LocationStore missing {required}")
location_js_text = location_js_path.read_text(encoding="utf-8") if location_js_path.is_file() else ""
for required in [
    "/api/locations/draw",
    "/api/locations/register",
    "/api/locations/select",
    "/api/locations/restore",
    "/api/locations/delete",
    "/api/locations/validate",
    "click the first point",
]:
    if required not in location_js_text:
        err(f"m41 Locations UI missing {required}")
for required in ['id="nav-locations"', 'id="locations-view"', 'location-assets.css?v=1']:
    if required not in index_m35_text:
        err(f"m41 Asset Manager Locations section missing {required}")
if not re.search(r'locations\.js\?v=\d+', index_m35_text):
    err('m41 Asset Manager Locations section missing versioned locations.js')
for required in [
    '"/api/locations"',
    'path == "/api/locations/draw"',
    'path == "/api/locations/register"',
    'path == "/api/locations/restore"',
]:
    if required not in host_agent_text:
        err(f"m41 host agent Location API missing {required}")
for required in [
    "run_location_authoring_bridge",
    '"command": "location-authoring"',
    '"/location-authoring-result"',
]:
    if required not in studio_bridge_m35_text:
        err(f"m41 Studio Location bridge missing {required}")
location_plugin_text = location_plugin_path.read_text(encoding="utf-8") if location_plugin_path.is_file() else ""
for required in [
    'AUTHORING_ROOT = "Game1Authoring"',
    'LOCATION_FOLDER = "Locations"',
    'Game1LocationMarker',
    'PreviewForLocationId',
    'plugin:Activate(true)',
    'mouse.Button1Down',
    'syncedLocationIds',
]:
    if required not in location_plugin_text:
        err(f"m41 Studio Location authoring module missing {required}")
for required in ['require(script.Parent.modules.LocationCommands)', 'data.command == "location-authoring"', 'model bridge v24']:
    if required not in studio_plugin_text:
        err(f"m41 Game1Bridge Location integration missing {required}")

# m42 Location UI polish: structured editor fields, geometry state and action hierarchy.
location_css_text = location_css_path.read_text(encoding="utf-8") if location_css_path.is_file() else ""
for required in [
    "location-editor-section",
    "location-field",
    "location-geometry-summary",
    "location-action-zone",
    "location-empty",
]:
    if required not in location_js_text or required not in location_css_text:
        err(f"m42 Location UI structure missing {required}")
for required in ["Location details", "Studio contour", "draw in Studio", "registry paths"]:
    if required not in location_js_text:
        err(f"m42 Location UI copy missing {required}")


# m43 Location Assets: weapon-style FBX+PNG publication and modular Studio DecoManager.
location_asset_manifest_path = ROOT / "assets/manifests/location-assets.json"
location_asset_registry_path = ROOT / "src/shared/world/LocationAssetRegistry.luau"
location_asset_store_path = ROOT / "system/control-center/location_asset_store.py"
deco_layout_store_path = ROOT / "system/control-center/deco_layout_store.py"
deco_assets_js_path = ROOT / "system/control-center/static/deco-assets.js"
deco_assets_css_path = ROOT / "system/control-center/static/deco-assets.css"
deco_loader_path = ROOT / "system/studio-plugin/modules/DecoAssetLoader.luau"
deco_manager_path = ROOT / "system/studio-plugin/modules/DecoManager.luau"
deco_placement_path = ROOT / "system/studio-plugin/modules/DecoPlacement.luau"
for path in [
    location_asset_manifest_path,
    location_asset_registry_path,
    location_asset_store_path,
    deco_layout_store_path,
    deco_assets_js_path,
    deco_assets_css_path,
    deco_loader_path,
    deco_manager_path,
    deco_placement_path,
]:
    if not path.is_file():
        err(f"m43 Location Assets / DecoManager file missing: {path.relative_to(ROOT)}")

if location_asset_manifest_path.is_file():
    location_asset_manifest = json.loads(location_asset_manifest_path.read_text(encoding="utf-8"))
    if location_asset_manifest.get("schemaVersion") != 4 or location_asset_manifest.get("project") != "game1":
        err("m43 location-assets.json schema/project is invalid")
    category_ids = [row.get("id") for row in ((location_asset_manifest.get("options") or {}).get("categories") or [])]
    # Generated manifests may still have the previous category set until
    # the first Control Center startup re-exports them from LocationAssetStore.
    expected_categories = ["tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building"]
    if category_ids not in (expected_categories, expected_categories + ["prop"]):
        err("m128 Location Assets manifest categories have invalid canonical order")

location_asset_store_text = location_asset_store_path.read_text(encoding="utf-8") if location_asset_store_path.is_file() else ""
for required in [
    "class LocationAssetStore",
    'CATEGORIES = ("tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building", "prop")',
    "assets/source/location-assets",
    "model_path TEXT NOT NULL DEFAULT ''",
    "texture_path TEXT NOT NULL DEFAULT ''",
    "create_model_asset",
    "update_model_asset",
    "create_image_asset",
    'return "PUBLISHED"',
    "LocationAssetRegistry.luau",
]:
    if required not in location_asset_store_text:
        err(f"m43 LocationAssetStore missing {required}")

deco_layout_store_text = deco_layout_store_path.read_text(encoding="utf-8") if deco_layout_store_path.is_file() else ""
for required in [
    "class DecoLayoutStore",
    "assets/backups/deco-layouts",
    "deco-layout-latest.json",
    '"cframe"',
    '"scale"',
]:
    if required not in deco_layout_store_text:
        err(f"m43 DecoLayoutStore missing {required}")

for required in [
    'path == "/api/location-assets"',
    'path == "/api/files/choose-location-asset-model"',
    'path == "/api/files/choose-location-asset-texture"',
    'path == "/api/location-assets/layout"',
    'location_assets.publish',
    'location_assets.delete',
    'game1-m50-environment-weapon-bounce-001',
]:
    if required not in host_agent_text:
        err(f"m43 host agent Location Assets API missing {required}")

index_m43_text = (ROOT / "system/control-center/static/index.html").read_text(encoding="utf-8")
deco_assets_js_text = deco_assets_js_path.read_text(encoding="utf-8") if deco_assets_js_path.is_file() else ""
deco_assets_css_text = deco_assets_css_path.read_text(encoding="utf-8") if deco_assets_css_path.is_file() else ""
for required in [
    'id="nav-location-assets"',
    'id="location-assets-view"',
    'id="location-asset-category"',
    'id="choose-location-asset-model"',
    'id="choose-location-asset-texture"',
    'id="publish-location-asset"',
    'deco-assets.css?v=',
    'deco-assets.js?v=',
]:
    if required not in index_m43_text:
        err(f"m43 Asset Manager Location Assets section missing {required}")
for required in [
    "/api/location-assets",
    "/api/files/choose-location-asset-model",
    "/api/files/choose-location-asset-texture",
    "decoAssetPublish",
    "window.game1LocationAssetsLoad",
]:
    if required not in deco_assets_js_text:
        err(f"m43 Location Assets UI behavior missing {required}")
for required in ["deco-asset-workflow", "deco-source-pickers", "deco-tree-group"]:
    if required not in deco_assets_css_text:
        err(f"m43 Location Assets UI styling missing {required}")

plugin_project_text = (ROOT / "system/studio-plugin/plugin.project.json").read_text(encoding="utf-8")
for required in ["DecoAssetLoader", "DecoPlacement", "DecoManager"]:
    if required not in plugin_project_text:
        err(f"m43 Studio plugin project is missing module {required}")

deco_loader_text = deco_loader_path.read_text(encoding="utf-8") if deco_loader_path.is_file() else ""
for required in [
    'self.AssetService:LoadAssetAsync(assetId)',
    'row.status or ""',
    'StudioTextureAppearance.Apply(descendant, uri, usesAlpha)',
    'Url = self.agentBaseUrl .. "/api/location-assets"',
]:
    if required not in deco_loader_text:
        err(f"m43 DecoAssetLoader missing {required}")

deco_placement_text = deco_placement_path.read_text(encoding="utf-8") if deco_placement_path.is_file() else ""
for required in [
    'ROOT_NAME = "Game1DecoAssets"',
    'tree = "Trees"',
    'bush = "Bushes"',
    'rock = "Rocks"',
    'light = "Lights"',
    'fence = "Fences"',
    'decoration = "Decorations"',
    'ladder = "Ladders"',
    'flower = "Flowers"',
    "Workspace:Raycast",
    "self.plugin:Activate(true)",
    'placed:SetAttribute("Game1DecoAssetSlug", tostring(row.slug or ""))',
    "function DecoPlacement:serialize()",
    "DecoTransform.supportOffset",
    "DecoTransform.placementPivot",
]:
    if required not in deco_placement_text:
        err(f"m43 DecoPlacement missing {required}")

deco_manager_text = deco_manager_path.read_text(encoding="utf-8") if deco_manager_path.is_file() else ""
for required in [
    'CreateDockWidgetPluginGui("Game1DecoManager_v1"',
    'self.widget.Title = "game1 · DecoManager"',
    'Instance.new("ViewportFrame")',
    'Instance.new("WorldModel")',
    'DecoPreviewWorld',
    '"Save Assets Data"',
    'self.agentBaseUrl .. "/api/location-assets/layout"',
    'local CATEGORY_ORDER = { "tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building", "prop" }',
]:
    if required not in deco_manager_text:
        err(f"m43 DecoManager missing {required}")

for required in [
    'require(script.Parent.modules.DecoManager)',
    'DecoManager.new({',
    'model bridge v24',
]:
    if required not in studio_plugin_text:
        err(f"m43 Game1Bridge DecoManager integration missing {required}")
for forbidden in ["game:SavePlace(", "SavePlace(Enum.SaveFilter", "SavePlaceAsync"]:
    if forbidden in deco_manager_text:
        err(f"m45 obsolete direct place-save path remains in DecoManager: {forbidden}")


# m45 DecoManager hotfix: Studio-native local-place save and strict LMB preview drag.
studio_save_path = ROOT / "system/control-center/studio_save.py"
if not studio_save_path.is_file():
    err("m45 Studio-native save helper is missing")
else:
    studio_save_text = studio_save_path.read_text(encoding="utf-8")
    for required in [
        "request_active_studio_save",
        "studio-native-ctrl-s",
        "Roblox Studio must be the active window",
        "keybd_event(_VK_CONTROL",
    ]:
        if required not in studio_save_text:
            err(f"m45 Studio-native save helper missing {required}")

for required in [
    "from studio_save import request_active_studio_save",
    'control_agent_build = "game1-m50-environment-weapon-bounce-001"',
    'result["studioSave"] = request_active_studio_save()',
]:
    if required not in host_agent_text:
        err(f"m45 host agent save bridge missing {required}")

for required in [
    "self.viewport.MouseLeave:Connect",
    "self.viewport.InputEnded:Connect",
    "self.previewDragging = false",
    "Studio save requested",
]:
    if required not in deco_manager_text:
        err(f"m45 DecoManager drag/save hotfix missing {required}")
if "self.AssetService:SavePlaceAsync" in deco_manager_text:
    err("m45 DecoManager still calls cloud SavePlaceAsync directly")
if "model bridge v24" not in studio_plugin_text:
    err("m45 Studio plugin version marker is stale")

# m44 Location Assets: PNG/JPG source textures with clean extension-aware preparation.
for required in [
    'TEXTURE_SUFFIXES = (".png", ".jpg", ".jpeg")',
    'canonical_suffix = ".jpg" if source_suffix == ".jpeg" else source_suffix',
    "_retire_replaced_file",
    "PNG or JPG",
]:
    if required not in location_asset_store_text:
        err(f"m44 LocationAssetStore image format support missing {required}")
for required in [
    "def choose_location_asset_texture()",
    "*.png;*.jpg;*.jpeg",
]:
    if required not in host_agent_text:
        err(f"m44 Location Asset texture picker missing {required}")
if "choose_location_asset_png" in host_agent_text:
    err("m44 legacy PNG-only Location Asset picker remains")
if "PNG/JPG" not in deco_assets_js_text or "PNG/JPG" not in index_m43_text:
    err("m44 Location Assets UI does not advertise PNG/JPG texture support")

# m46 Location Assets: Decorations category + shared registered texture references.
for required in [
    'SCHEMA_VERSION = 4',
    '"decoration": "Decorations"',
    'texture_reference_slug TEXT NOT NULL DEFAULT',
    'def _resolve_texture_owner',
    'textureReferenceSlug',
    'texture_owner_slug',
    'texture_shared',
    'shared texture owner',
    'texture is reused by location assets',
]:
    if required not in location_asset_store_text:
        err(f"m46 shared Location Asset texture support missing {required}")
for required in [
    'id="location-asset-texture-reference"',
    'decorations</span>',
    'atlas variant',
]:
    if required not in index_m43_text:
        err(f"m46 Location Assets UI missing {required}")
for required in [
    'textureReferenceSlug',
    'decoAssetRenderTextureReferences',
    'location-asset-texture-reference',
    'reuse a registered texture',
]:
    if required not in deco_assets_js_text:
        err(f"m46 Location Assets shared-texture UI behavior missing {required}")
for required in [
    'decoration = "Decorations"',
    'ladder = "Ladders"',
    'flower = "Flowers"',
    'local CATEGORY_ORDER = { "tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building", "prop" }',
    'local row = math.floor((index - 1) / 4)',
]:
    if required not in deco_manager_text:
        err(f"m46 DecoManager Decorations category missing {required}")
if 'decoration = "Decorations"' not in deco_placement_text:
    err("m46 DecoPlacement Decorations folder mapping is missing")
if "model bridge v24" not in studio_plugin_text:
    err("m46 Studio plugin version marker is stale")


# m47 DecoManager: transient placement sessions never reuse/destroy the manager template.
for required in [
    'sourceTemplate = nil',
    'function DecoPlacement:_detachSession()',
    'self.plugin:Activate(true)',
    'ghost.Parent = if camera ~= nil then camera else self.Workspace',
    'local placed = sourceTemplate:Clone()',
    'self.committing = true',
]:
    if required not in deco_placement_text:
        err(f"m47 DecoPlacement lifecycle hotfix missing {required}")
if 'self.template:Destroy()' in deco_placement_text:
    err("m47 DecoPlacement still destroys a placement-owned template clone")
for required in [
    'descendant:IsA("AnimationController")',
    'descendant:IsA("Animator")',
    'descendant.Name == "InitialPoses"',
]:
    if required not in deco_loader_text:
        err(f"m47 static Location Asset sanitization missing {required}")
if "model bridge v24" not in studio_plugin_text:
    err("m47 Studio plugin version marker is stale")


# m48 DecoManager: preserve the imported FBX/model pivot basis in preview and placement.
deco_transform_path = ROOT / "system/studio-plugin/modules/DecoTransform.luau"
if not deco_transform_path.exists():
    err("m48 DecoTransform module is missing")
else:
    deco_transform_text = deco_transform_path.read_text(encoding="utf-8")
    for required in [
        "function DecoTransform.authoredPivotRotation",
        "function DecoTransform.previewPivot",
        "function DecoTransform.supportOffset",
        "function DecoTransform.placementPivot",
        "surfaceFrame(surfaceNormal, cameraLook) * authoredPivotRotation",
    ]:
        if required not in deco_transform_text:
            err(f"m48 DecoTransform missing {required}")
for required in [
    "local DecoTransform = require(script.Parent.DecoTransform)",
    "DecoTransform.supportOffset(template)",
    "DecoTransform.authoredPivotRotation(template)",
    "DecoTransform.placementPivot(",
]:
    if required not in deco_placement_text:
        err(f"m48 DecoPlacement authored-basis handling missing {required}")
for removed in ["localSupportOffset", "orientationForSurface"]:
    if removed in deco_placement_text:
        err(f"m48 DecoPlacement still contains obsolete transform helper {removed}")
if "model:PivotTo(DecoTransform.previewPivot(model))" not in deco_manager_text:
    err("m48 DecoManager preview still replaces the imported asset basis")
if '"DecoTransform"' not in (ROOT / "system/studio-plugin/plugin.project.json").read_text(encoding="utf-8"):
    err("m48 Studio plugin project does not include DecoTransform")
if "model bridge v24" not in studio_plugin_text:
    err("m48 Studio plugin version marker is stale")


# m49 DecoManager: placed decoration instances stay unanchored for manual Studio editing.
if 'descendant.Anchored = false' not in deco_placement_text:
    err("m49 DecoPlacement must leave placed decoration BaseParts unanchored")
prepare_placed_match = re.search(r'local function preparePlaced\(model: Model\)(.*?)\nend', deco_placement_text, re.S)
if prepare_placed_match is None:
    err("m49 DecoPlacement preparePlaced helper is missing")
elif 'Anchored = true' in prepare_placed_match.group(1):
    err("m49 DecoPlacement still anchors placed decoration BaseParts")


# m50 Environment weapon bounce: Location Asset gameplay policy is registry-owned,
# DecoManager stores identity only, and solid environment contact terminates the
# authored damage window before reversing the current attack at 2x speed.
weapon_bounce_config_path = ROOT / "src/shared/combat/WeaponBounceConfig.luau"
environment_asset_service_path = ROOT / "src/server/world/EnvironmentAssetService.luau"
weapon_environment_collision_path = ROOT / "src/server/combat/WeaponEnvironmentCollision.luau"
weapon_bounce_service_path = ROOT / "src/server/combat/WeaponBounceService.luau"
weapon_bounce_controller_path = ROOT / "src/client/combat/WeaponBounceController.luau"
weapon_bounce_effect_pool_path = ROOT / "src/client/combat/effects/WeaponBounceEffectPool.luau"
for path in [
    weapon_bounce_config_path,
    environment_asset_service_path,
    weapon_environment_collision_path,
    weapon_bounce_service_path,
    weapon_bounce_controller_path,
    weapon_bounce_effect_pool_path,
]:
    if not path.is_file():
        err(f"m50 weapon bounce module missing: {path.relative_to(ROOT)}")

if location_asset_manifest_path.is_file():
    location_asset_manifest = json.loads(location_asset_manifest_path.read_text(encoding="utf-8"))
    if location_asset_manifest.get("schemaVersion") != 4:
        err("m52 Location Asset manifest must use schemaVersion 4")
    for row in location_asset_manifest.get("items") or []:
        if not isinstance(row.get("destructible"), bool):
            err(f"m50 Location Asset destructible policy missing/invalid for {row.get('slug')}")

for required in [
    "destructible INTEGER NOT NULL DEFAULT 0",
    'result["destructible"] = bool(result.get("destructible"))',
    'f"\\t\\t\\tdestructible = {str(bool(row.get(\'destructible\'))).lower()},"',
]:
    if required not in location_asset_store_text:
        err(f"m50 LocationAssetStore destructible policy missing {required}")
for required in [
    'id="location-asset-destructible"',
    "solid weapon blocker and causes bounce",
    "weapon contact",
]:
    if required not in index_m43_text:
        err(f"m50 Location Assets destructible UI missing {required}")
for required in [
    "location-asset-destructible",
    "destructible: $('location-asset-destructible').checked",
    "solid · bounce",
]:
    if required not in deco_assets_js_text:
        err(f"m50 Location Assets destructible behavior missing {required}")

# Studio authoring persists only stable identity/editor metadata. Gameplay policy
# is deliberately not copied to placed Instances.
for required in [
    'placed:SetAttribute("Game1DecoInstanceId", instanceId)',
    'placed:SetAttribute("Game1DecoAssetSlug", tostring(row.slug or ""))',
    'locationAssetId = tostring(descendant:GetAttribute("Game1DecoAssetSlug") or "")',
]:
    if required not in deco_placement_text:
        err(f"m50 DecoPlacement identity-only authoring missing {required}")
for forbidden in [
    'SetAttribute("Destructible"',
    'SetAttribute("Game1DecoAsset",',
    'SetAttribute("Game1DecoCategory",',
    'SetAttribute("Game1DecoModelAssetId",',
    'SetAttribute("Game1DecoTextureAssetId",',
]:
    if forbidden in deco_placement_text:
        err(f"m50 DecoPlacement still persists gameplay/redundant metadata: {forbidden}")
for required in ['"schemaVersion": 2', '"locationAssetId": location_asset_id']:
    if required not in deco_layout_store_text:
        err(f"m50 deco backup identity schema missing {required}")

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
            err(f"m50 EnvironmentAssetService missing {required}")
    for forbidden in ['SetAttribute("Destructible"', 'SetAttribute("Game1DecoCategory"']:
        if forbidden in environment_asset_service_text:
            err(f"m50 runtime must resolve policy server-side instead of stamping Attributes: {forbidden}")

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
            err(f"m50 WeaponEnvironmentCollision missing {required}")

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
            err(f"m50 WeaponBounceConfig missing {required}")

if weapon_bounce_service_path.is_file():
    weapon_bounce_service_text = weapon_bounce_service_path.read_text(encoding="utf-8")
    for required in [
        'payload.attackerUserId = attacker.UserId',
        'WeaponBounceConfig.ServerReplicationRadius',
        'remote:FireClient(player, payload)',
    ]:
        if required not in weapon_bounce_service_text:
            err(f"m50 WeaponBounceService replication missing {required}")

if weapon_bounce_controller_path.is_file():
    weapon_bounce_controller_text = weapon_bounce_controller_path.read_text(encoding="utf-8")
    for required in [
        'attackerUserId == Players.LocalPlayer.UserId',
        'WeaponBounceConfig.ClientRenderRadius',
        'effects:Emit(position, normal, camera.CFrame)',
    ]:
        if required not in weapon_bounce_controller_text:
            err(f"m50 WeaponBounceController presentation missing {required}")

attack_service_text = (ROOT / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
attack_session_text = (ROOT / "src/server/combat/AttackSessionStore.luau").read_text(encoding="utf-8")
for required in [
    'WeaponEnvironmentCollision.Query(previousVolume, volume)',
    'AttackSessionStore.BlockForBounce(',
    'WeaponBounceService.Publish(player, {',
    'LastAttackBounced',
]:
    if required not in attack_service_text:
        err(f"m50 AttackService environment-bounce integration missing {required}")
for required in ['session.environmentBlocked = true', 'session.damageWindow = nil', 'session.sweepState = nil']:
    if required not in attack_session_text:
        err(f"m50 AttackSessionStore bounce invalidation missing {required}")
if attack_service_text.find('WeaponEnvironmentCollision.Query(previousVolume, volume)') > attack_service_text.find('hitCount += applyDamageInVolume', attack_service_text.find('local function applyAnimatedWeaponSweep')):
    err("m50 environment collision must resolve before damage in each weapon sweep substep")

upper_composer_text = (ROOT / "src/client/character/animation/AttackUpperBodyComposer.luau").read_text(encoding="utf-8")
character_animation_text = (ROOT / "src/client/character/animation/CharacterAnimationController.luau").read_text(encoding="utf-8")
attack_controller_text = (ROOT / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
client_init_text = (ROOT / "src/client/init.client.luau").read_text(encoding="utf-8")
server_init_text = (ROOT / "src/server/init.server.luau").read_text(encoding="utf-8") + (ROOT / "src/server/bootstrap/ServiceCatalog.luau").read_text(encoding="utf-8")
for required in ['function AttackUpperBodyComposer.SetPlaybackSpeed', 'sourcePlaybackSpeed <= 0', 'exitBlendRequested = false']:
    if required not in upper_composer_text:
        err(f"m50 upper-body reverse playback support missing {required}")
for required in [
    'function CharacterAnimationController.BounceCurrentAttack',
    'track:AdjustSpeed(-reverseSpeed)',
    'AttackUpperBodyComposer.SetPlaybackSpeed(-reverseSpeed)',
    'AnimationAttackBounced',
]:
    if required not in character_animation_text:
        err(f"m50 character attack reverse presentation missing {required}")
for required in ['function AttackController.CancelForBounce', 'activePoseAttackId = 0']:
    if required not in attack_controller_text:
        err(f"m50 attack controller bounce cancellation missing {required}")
for required in ['WeaponBounceController.Start(CharacterAnimationController, AttackController)']:
    if required not in client_init_text:
        err(f"m50 client bounce startup missing {required}")
for required in ['EnvironmentAssetService.Start()', 'WeaponBounceService.Start()']:
    if required not in server_init_text:
        err(f"m50 server environment/bounce startup missing {required}")

if 'control_agent_build = "game1-m50-environment-weapon-bounce-001"' not in host_agent_text:
    err("m50 Control Center build marker is stale")
if "model bridge v24" not in studio_plugin_text:
    err("m51 Studio plugin version marker is stale")
install_plugin_text = (ROOT / "system/studio-plugin/install.ps1").read_text(encoding="utf-8")
if "model bridge v24" not in install_plugin_text:
    err("m51 Studio plugin installer marker is stale")

# m51 Location Assets: changed owned textures get a fresh Roblox Image Asset ID.
deco_placed_sync_path = ROOT / "system/studio-plugin/modules/DecoPlacedAssetSync.luau"
environment_visuals_path = ROOT / "src/server/world/EnvironmentAssetVisuals.luau"
for path in [deco_placed_sync_path, environment_visuals_path]:
    if not path.is_file():
        err(f"m51 texture synchronization module missing: {path.relative_to(ROOT)}")
deco_placed_sync_text = deco_placed_sync_path.read_text(encoding="utf-8") if deco_placed_sync_path.is_file() else ""
environment_visuals_text = environment_visuals_path.read_text(encoding="utf-8") if environment_visuals_path.is_file() else ""
for required in [
    "legacy_texture_updates",
    "COUNT(DISTINCT publication.sha256)>1",
    "texture_replaced =",
    "replacement is identity-changing for Location Assets by design",
    "operation = create_image_asset(",
]:
    if required not in location_asset_store_text:
        err(f"m51 Location Asset replacement publication missing {required}")
if "update_image_asset" in location_asset_store_text:
    err("m51 Location Assets still contain legacy in-place Image Asset updates")
for required in [
    "central atlas reuse never does",
    "texture ${published.texture_asset_id || '—'}",
]:
    if required not in (index_m43_text + deco_assets_js_text):
        err(f"m51 Location Assets UI publication identity missing {required}")
for required in ["Game1DecoAssetSlug", "StudioTextureAppearance.Apply(part, uri, row.textureUsesAlpha)", "RefreshTextures"]:
    if required not in deco_placed_sync_text:
        err(f"m51 DecoManager placed-texture sync missing {required}")
for required in ["DecoPlacedAssetSync.RefreshTextures", "Refresh Deco Asset Textures"]:
    if required not in deco_manager_text:
        err(f"m51 DecoManager registry refresh integration missing {required}")
if '"DecoPlacedAssetSync"' not in plugin_project_text:
    err("m51 Studio plugin project is missing DecoPlacedAssetSync")
# Runtime cannot read/write SurfaceAppearance.ColorMap (Plugin capability).
# The Studio texture adapter alone owns SurfaceAppearance and alpha authoring.
for required in ["textureAssetId", "mesh.TextureID = uri", 'FindFirstChildOfClass("SurfaceAppearance")', "ApplyModel", "ApplyPart"]:
    if required not in environment_visuals_text:
        err(f"m51 runtime environment texture hydration missing {required}")
if "surface.ColorMap" in environment_visuals_text or "surface.AlphaMode" in environment_visuals_text:
    err("m51 runtime environment binder must not access Plugin-only SurfaceAppearance properties")
for required in ["EnvironmentAssetVisuals.ApplyModel", "EnvironmentAssetVisuals.ApplyPart"]:
    if required not in environment_asset_service_text:
        err(f"m51 EnvironmentAssetService visual hydration missing {required}")


# M164: M52/M53 source-only invariants now live in one read-only validator.
check_source_only_contract(
    ROOT, err,
    location_asset_store_text=location_asset_store_text,
    deco_assets_js_text=deco_assets_js_text,
    host_agent_text=host_agent_text,
    character_js_text=character_js_text,
    ui_html=ui,
)

if errors:
    print("verify failed")
    for item in errors:
        print(" -", item)
    sys.exit(1)

# m54 Location Assets UX: create mode, remembered navigation/library category, named Roblox descriptions, new categories.
for required in [
    "ASSET_MANAGER_VIEW_KEY='game1.assetManager.activeSection'",
    "window.addEventListener('load',restoreAssetManagerView)",
    "localStorage.setItem(ASSET_MANAGER_VIEW_KEY,view)",
]:
    if required not in character_js_text:
        err(f"m54 Asset Manager remembered section missing {required}")
for required in [
    "DECO_LIBRARY_CATEGORY_KEY = 'game1.locationAssets.libraryCategory'",
    "DECO_SELECTED_ASSET_KEY = 'game1.locationAssets.selectedAsset'",
    "function decoAssetBeginNew()",
    "new-location-asset-main",
    "location-asset-library-category",
    "save asset changes",
]:
    if required not in deco_assets_js_text and required not in index_m43_text:
        err(f"m54 Location Assets UX missing {required}")
for required in [
    'id="new-location-asset-main"',
    'id="location-asset-library-category"',
    'ladders</span>',
    'flowers</span>',
    'game1 location asset · Oak Tree',
]:
    if required not in index_m43_text:
        err(f"m54 Location Assets markup missing {required}")
for required in [
    '"ladder": "Ladders"',
    '"flower": "Flowers"',
    'description = f"{description} · {asset_name}"',
]:
    if required not in location_asset_store_text:
        err(f"m54 LocationAssetStore missing {required}")
for required in [
    'ladder = "Ladders"',
    'flower = "Flowers"',
    'local CATEGORY_ORDER = { "tree", "bush", "rock", "light", "fence", "decoration", "ladder", "flower", "building", "prop" }',
    'local column = (index - 1) % 4',
]:
    if required not in deco_manager_text:
        err(f"m54 DecoManager category support missing {required}")
for required in ['ladder = "Ladders"', 'flower = "Flowers"']:
    if required not in deco_placement_text:
        err(f"m54 DecoPlacement category folder missing {required}")
if "model bridge v24" not in studio_plugin_text or "model bridge v24" not in install_plugin_text:
    err("m54 Studio plugin version marker must match current bridge")

# m55 Location Assets: Buildings + synchronized editor/library category context.
for required in [
    '"building": "Buildings"',
    'building = "Buildings"',
    'buildings</span>',
    'function decoAssetUseCategory(category',
    "$('location-asset-category').onchange",
]:
    if required not in location_asset_store_text and required not in deco_manager_text and required not in deco_placement_text and required not in index_m43_text and required not in deco_assets_js_text:
        err(f"m55 Buildings/category synchronization missing {required}")
# m128 Props category is backed by the API, browser controls, and DecoManager.
for required, source in [
    ('"prop": "Props"', location_asset_store_text),
    ('prop = "Props"', deco_manager_text),
    ('prop = "Props"', deco_placement_text),
    ('props</span>', index_m43_text),
    ('buildings · props</small>', index_m43_text),
]:
    if required not in source:
        err(f"m128 Location Assets Props integration missing {required}")

if 'category filter<select id="location-asset-library-category"' not in index_m43_text:
    err("m55 library category filter label missing")
if "decoAssetUseCategory($('location-asset-category').value, { updateEditor: false })" not in deco_assets_js_text:
    err("m55 editor category must synchronize library filter")
if "decoAssetUseCategory(category);" not in deco_assets_js_text:
    err("m55 library category must synchronize editor category")
if 'model bridge v24' not in studio_plugin_text or 'model bridge v24' not in install_plugin_text:
    err("m55 Studio plugin version marker must be v24")

print("verify ok · game1 m55 Buildings + synchronized Location Asset category context passed")
print("registered character archetypes:", len(archetypes))
print("active character archetype:", active_id or "none")
print("race pool: human")
print("gender pool: male, female")
print("canonical place: place/game1.rbxl")
