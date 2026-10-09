from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
errors = []


def err(message: str) -> None:
    errors.append(message)


if "robloxlineage" in str(ROOT).lower():
    err("game1 root is inside/a descendant of a robloxlineage path")

project = json.loads((ROOT / "default.project.json").read_text(encoding="utf-8"))
if project.get("name") != "game1":
    err("default.project.json project name must be game1")

tree = project.get("tree", {})
try:
    if "Game1Shared" not in tree["ReplicatedStorage"]:
        err("Game1Shared namespace missing")
    if "Game1Server" not in tree["ServerScriptService"]:
        err("Game1Server namespace missing")
    if "Game1Client" not in tree["StarterPlayer"]["StarterPlayerScripts"]:
        err("Game1Client namespace missing")
except (KeyError, TypeError):
    err("default.project.json namespace tree is malformed")

manifest = json.loads((ROOT / "assets/manifests/character-archetypes.json").read_text(encoding="utf-8"))
if manifest.get("project") != "game1":
    err("character manifest identity must be game1")
if manifest.get("schemaVersion") != 5:
    err("character manifest schema must be 5; run python .\\system\\control-center\\migrate.py")
if manifest.get("racePool") != ["human"]:
    err("character race pool must start with human only")
if manifest.get("genderPool") != ["male", "female"]:
    err("character gender pool must be male/female")

archetypes = manifest.get("archetypes", [])
if not isinstance(archetypes, list):
    err("character archetypes must be a list")
    archetypes = []

ids = {str(row.get("id", "")) for row in archetypes if isinstance(row, dict)}
active_id = manifest.get("activeArchetypeId")
if active_id is not None and active_id not in ids:
    err("active character archetype must exist in the manifest")

identities = set()
for row in archetypes:
    if not isinstance(row, dict):
        err("character archetype row must be an object")
        continue
    race = str(row.get("race") or "")
    gender = str(row.get("gender") or "")
    incomplete = str(row.get("status") or "") == "INCOMPLETE"
    if not incomplete or race or gender:
        if race != "human":
            err(f"character archetype {row.get('id')} has an unregistered race: {race}")
        if gender not in {"male", "female"}:
            err(f"character archetype {row.get('id')} has invalid gender: {gender}")
        identity = (race, gender)
        if identity in identities:
            err(f"duplicate character identity: {race}/{gender}")
        identities.add(identity)
    model = row.get("model")
    skeleton = row.get("skeleton")
    if not isinstance(model, dict):
        err(f"character archetype {row.get('id')} must have one model object")
    if not isinstance(skeleton, dict):
        err(f"character archetype {row.get('id')} must have skeleton metadata")
    elif row.get("status") != "INCOMPLETE":
        if int(skeleton.get("boneCount") or 0) <= 0:
            err(f"character archetype {row.get('id')} has no analyzed bones")
        if not str(skeleton.get("signature") or ""):
            err(f"character archetype {row.get('id')} has no skeleton signature")

if (ROOT / "place/current.rbxl").exists():
    err("place/current.rbxl is forbidden in game1; canonical file is place/game1.rbxl")

scan = [
    ROOT / "src",
    ROOT / "assets/manifests",
    ROOT / "system/control-center",
    ROOT / "system/asset-manager",
    ROOT / "config",
]
for base in scan:
    for path in base.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".luau", ".lua", ".py", ".json", ".yaml", ".yml"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in [
                "RobloxLineageShared",
                "RobloxLineageServer",
                "RobloxLineageClient",
                "NewPlaceShared",
                "NewPlaceServer",
                "NewPlaceClient",
                "Interlude",
                "CombatV2",
            ]:
                if token in text:
                    err(f"{path.relative_to(ROOT)} contains forbidden token {token}")

cfg = json.loads((ROOT / "config/project.json").read_text(encoding="utf-8"))
if cfg.get("name") != "game1" or cfg.get("slug") != "game1":
    err("config/project.json identity must be game1")
expected_namespaces = {"shared": "Game1Shared", "server": "Game1Server", "client": "Game1Client", "remotes": "Game1Remotes"}
if cfg.get("namespaces") != expected_namespaces:
    err("config/project.json namespaces do not match game1 contract")
ports = cfg.get("ports", {})
old = {43720, 43721, 34872, 43127}
if old & set(ports.values()):
    err("port collision with robloxlineage baseline")
if ports.get("rojo") != 34882:
    err("game1 rojo port must be 34882")


required_runtime = [
    "src/server/character/CharacterService.luau",
    "src/server/character/CharacterRigService.luau",
    "src/server/character/CharacterStatsService.luau",
    "src/server/combat/AttackService.luau",
    "src/server/combat/DamageService.luau",
    "src/server/combat/EntityHitboxService.luau",
    "src/server/dev/TrainingDummyService.luau",
    "src/server/dev/MovementDebugService.luau",
    "src/server/monster/MonsterSpawnerService.luau",
    "src/server/monster/MonsterSpawnRegistry.luau",
    "src/client/character/MovementController.luau",
    "src/client/character/CameraController.luau",
    "src/client/character/PlayerStatusController.luau",
    "src/client/character/animation/AnimationResolver.luau",
    "src/client/character/animation/AnimationTrackCache.luau",
    "src/client/character/animation/AttackUpperBodyComposer.luau",
    "src/client/character/animation/CharacterAnimationController.luau",
    "src/client/combat/AttackController.luau",
    "src/client/combat/AimPoseController.luau",
    "src/client/dev/MovementDebugController.luau",
    "src/shared/character/CharacterConfig.luau",
    "src/shared/character/CharacterMovementConfig.luau",
    "src/shared/character/CharacterRegistry.luau",
    "src/shared/character/CharacterAnimationRegistry.luau",
    "src/shared/character/CharacterStatsConfig.luau",
    "src/shared/animation/AnimationSpeedScaling.luau",
    "src/shared/animation/AnimationSpeedScalingRegistry.luau",
    "src/shared/combat/AttackConfig.luau",
    "src/shared/combat/AttackTimelineConfig.luau",
    "src/shared/combat/CharacterAttackWindow.luau",
    "src/shared/combat/SkeletonHeadResolver.luau",
]
for relative in required_runtime:
    if not (ROOT / relative).is_file():
        err(f"runtime module missing: {relative}")

for legacy in [
    "src/server/CharacterService.luau",
    "src/server/AttackService.luau",
    "src/server/DamageService.luau",
    "src/server/TrainingDummyService.luau",
    "src/shared/CharacterRegistry.luau",
    "src/shared/CharacterConfig.luau",
    "src/shared/AttackConfig.luau",
]:
    if (ROOT / legacy).exists():
        err(f"legacy flat runtime module must be removed: {legacy}")

damage_text = (ROOT / "src/server/combat/DamageService.luau").read_text(encoding="utf-8")
for required in ["CritChance", "CRITICAL_DAMAGE_MULTIPLIER = 2", "criticalRandom:NextNumber", "damageBeforeDefense"]:
    if required not in damage_text:
        err(f"critical damage contract missing {required}")

attack_text = (ROOT / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
dummy_text = (ROOT / "src/server/dev/TrainingDummyService.luau").read_text(encoding="utf-8")
if "[game1][attack] hit" not in attack_text or "[game1][attack] miss" not in attack_text:
    err("attack smoke-test logging contract missing")
if "EntityHitboxService.QueryDamageablesInBox" not in attack_text:
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
for forbidden in ["ResultTypes", "melee_damage", "runtimeTailDuration", "_duplicateFirstFrameAtEnd"]:
    if forbidden in attack_timeline_text:
        err(f"obsolete attack timeline runtime field remains: {forbidden}")
for required in [
    "AttackTimelineConfig.ResolveRuntime",
    "CharacterAttackWindow.Resolve",
    "allowedAttackDescriptor",
    "AnimationSpeedScaling.ResolveForModel",
    "activeUntil",
    'character:SetAttribute("AttackEndsAt"',
]:
    if required not in attack_text:
        err(f"server attack timeline contract missing {required}")
if "BillboardGui" not in dummy_text or "HP %d/%d" not in dummy_text:
    err("training dummy visible hp contract missing")

character_service_text = (ROOT / "src/server/character/CharacterService.luau").read_text(encoding="utf-8")
rig_text = (ROOT / "src/server/character/CharacterRigService.luau").read_text(encoding="utf-8")
for required in [
    'root.Name = "RootCollider"',
    'navigationRoot.Name = "NavigationRoot"',
    'controllerManager.Name = "ControllerManager"',
    'sensorPart.Name = "GroundSensorPart"',
    'sensor.Name = "GroundSensor"',
    'cloned.Name = "ImportedRig"',
    'weld.Name = "VisualRootWeld"',
]:
    if required not in rig_text:
        err(f"canonical character rig contract missing: {required}")
if 'object:IsA("MeshPart") and object:FindFirstChildWhichIsA("Bone"' in rig_text:
    err("skinned MeshPart must not be selected as the character root anchor")
if "Game1BootstrapCompatibilityRoot" not in rig_text:
    err("bootstrap placeholder compatibility must stay isolated from registered characters")
if "registered character template is missing ImportedRig/RootPart" not in rig_text:
    err("registered characters must require the canonical Studio-authored RootPart")
if "lowestVisibleGeometryY" not in rig_text or 'object ~= visualRootPart' not in rig_text:
    err("registered character visual must ground-align from visible geometry, excluding RootPart")
if 'VisualFootContactSource' not in rig_text or '"visible_geometry"' not in rig_text:
    err("character visual ground-contact diagnostics are missing")
if "row == nil" not in character_service_text:
    err("runtime compatibility root must be allowed only for the bootstrap placeholder")
if "findRegisteredTemplate" not in character_service_text or '"characters"' not in character_service_text:
    err("registered character runtime must resolve managed ServerStorage templates")
if "getAssetTemplate" not in character_service_text:
    err("published registered character fallback is missing")

hitbox_text = (ROOT / "src/server/combat/EntityHitboxService.luau").read_text(encoding="utf-8")
head_resolver_text = (ROOT / "src/shared/combat/SkeletonHeadResolver.luau").read_text(encoding="utf-8")
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
    if required not in hitbox_text:
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

host_agent_text = (ROOT / "system/control-center/host_agent.py").read_text(encoding="utf-8")
if "sync_character_to_studio" not in host_agent_text or 'sync_suffix = "/sync"' not in host_agent_text:
    err("character publication must expose reference-style Studio sync")

registry_path = ROOT / "src/shared/character/CharacterRegistry.luau"
registry_text = registry_path.read_text(encoding="utf-8") if registry_path.is_file() else ""
if "activeArchetypeId" not in registry_text:
    err("generated character registry has no active archetype field")
if archetypes and ("race =" not in registry_text or "gender =" not in registry_text):
    err("generated character registry does not expose race/gender")

schema_text = (ROOT / "system/control-center/schema.sql").read_text(encoding="utf-8")
for required in ["project_settings", "character_publications", "race text", "gender text", "skeleton_signature", "model_replacement_pending", "publication_pipeline"]:
    if required not in schema_text:
        err(f"control center schema missing {required}")

store_text = (ROOT / "system/control-center/character_store.py").read_text(encoding="utf-8")
if 'RACES = ("human",)' not in store_text or 'GENDERS = ("male", "female")' not in store_text:
    err("character identity pools are missing")
if "analyze_character_fbx" not in store_text:
    err("character armature analysis is not wired into registration")
if "prepare_character_fbx" not in store_text:
    err("character FBX preparation is not wired into registration")
if "create_model_asset" not in store_text:
    err("character model publication contract is missing")
if "update_model_asset" in store_text:
    err("character model publication must create a new asset id instead of updating an existing Roblox model asset")
if "current_sha == published_sha" not in store_text:
    err("unchanged character model publication must be a no-op")
if 'CHARACTER_PUBLICATION_PIPELINE = "roblox-open-cloud-bone-survival-v2-scale-safe"' not in store_text:
    err("character publication pipeline version is missing")
if "published_pipeline == CHARACTER_PUBLICATION_PIPELINE" not in store_text:
    err("old character publications must be republished when the bone-safe pipeline changes")
if 'src/shared/character/CharacterRegistry.luau' not in store_text:
    err("character registry generator must target the character shared domain")

ui = (ROOT / "system/control-center/static/index.html").read_text(encoding="utf-8")
css = ROOT / "system/control-center/static/asset-manager.css"
js = ROOT / "system/control-center/static/character-assets.js"
if not css.is_file() or not js.is_file():
    err("character asset manager css/js files are missing")
if 'id="race"' not in ui or 'id="gender"' not in ui or 'id="publish-character"' not in ui:
    err("character asset manager race/gender/publication controls are missing")
if 'id="character-model-source"' in ui:
    err("character edit UI must not reassign/reuse another archetype's existing Roblox model asset id")
character_js_text = js.read_text(encoding="utf-8") if js.is_file() else ""
for required in ['id="animation-folder-path"', 'id="choose-animation-folder"', 'id="scan-animations"']:
    if required not in ui:
        err(f"character animation folder explorer missing {required}")
for required in ["ANIMATION_FOLDER_KEY", "initAnimationFolderExplorer", "initialPath", "localStorage.setItem(ANIMATION_FOLDER_KEY"]:
    if required not in character_js_text:
        err(f"character animation folder persistence missing {required}")
if "/replace-model" not in host_agent_text:
    err("character edit UI needs an explicit replace-model endpoint")

analyzer = ROOT / "system/asset-manager/analyze_character_fbx.py"
if not analyzer.is_file() or "FBX contains no armature" not in analyzer.read_text(encoding="utf-8"):
    err("deterministic character fbx armature analyzer is missing")
analysis_text = (ROOT / "system/control-center/character_analysis.py").read_text(encoding="utf-8")
if "shutil.copy2(source, output)" not in analysis_text or "preserve-source-bytes" not in analysis_text:
    err("character prepared FBX must preserve authored source bytes")
preparer = ROOT / "system/asset-manager/prepare_character_fbx.py"
if preparer.is_file() and "transform_apply" in preparer.read_text(encoding="utf-8"):
    err("character FBX preparer must not rebake authored rotation/scale")

publication_preparer = ROOT / "system/asset-manager/prepare_character_publication_fbx.py"
publication_preparer_text = publication_preparer.read_text(encoding="utf-8") if publication_preparer.is_file() else ""
for required in [
    "SURVIVAL_WEIGHT = 0.05",
    "ROBLOX_MAX_INFLUENCES = 4",
    "assert_rest_unchanged",
    "use_armature_deform_only=False",
    "global_scale=1.0",
    'apply_scale_options="FBX_SCALE_UNITS"',
    "restTransformsChanged",
    "fbxScaleMode",
]:
    if required not in publication_preparer_text:
        err(f"Roblox-safe character publication preparer missing {required}")
if "transform_apply" in publication_preparer_text:
    err("Roblox-safe publication preparation must never apply/move character bone transforms")
for required in ["prepare_character_publication_fbx", "_assert_publication_skeleton_matches"]:
    if required not in analysis_text + store_text:
        err(f"character publication skeleton safety missing {required}")
if "boneNames" not in plugin_text or "Roblox publication stripped" not in host_agent_text:
    err("Studio character sync must report exact bones stripped by Roblox publication")

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
if 'id="nav-animations"' not in ui or 'id="scan-animations"' not in ui or 'id="publish-missing-animations"' not in ui:
    err("asset manager character animation section is missing")
js_text = js.read_text(encoding="utf-8") if js.is_file() else ""
for required in ["filename_rule_catalog", "canonicalFilename", "variantPattern", "filename_prefix"]:
    if required not in animation_store_text:
        err(f"animation filename-rule catalog missing {required}")
for required in ['id="animation-filename-rules"', 'id="animation-filename-guide"', "all registered states", "selected archetype id"]:
    if required not in ui:
        err(f"animation filename-rules UI missing {required}")
if "renderFilenameRules" not in js_text:
    err("animation filename-rules renderer missing")
for required in ["FILENAME_GUIDE_OPEN_KEY", "localStorage.getItem", "localStorage.setItem", "initFilenameRulesDisclosure"]:
    if required not in js_text:
        err(f"animation filename-rules disclosure persistence missing {required}")
for required in ["chooseAnimationFolder", "scanAnimations", "publishMissingAnimations", "animationFilter", "assignUnassignedAnimation", "manualSlotCatalog"]:
    if required not in js_text:
        err(f"asset manager animation ui missing {required}")
for forbidden in ["setAnimationSpeed", "data-speed"]:
    if forbidden in js_text:
        err(f"asset manager character clip table must not expose per-clip speed control: {forbidden}")
if "<th>speed %</th>" in ui:
    err("asset manager animation clip tables must not expose authored speed percent")
if 'create_animation_asset' not in (ROOT / "system/control-center/opencloud_assets.py").read_text(encoding="utf-8"):
    err("open cloud animation publication helper is missing")

# m5.2 archetype identity editing contract
identity_service = ROOT / "system/control-center/character_core/identity.py"
identity_text = identity_service.read_text(encoding="utf-8") if identity_service.is_file() else ""
for required in [
    "class CharacterIdentityService",
    "def update",
    "UPDATE character_publications SET character_id",
    "UPDATE animation_profiles SET character_id",
    "UPDATE animation_publications SET clip_id",
    "UPDATE animation_clips",
    "UPDATE animation_bindings",
    "migratedAnimationClips",
]:
    if required not in identity_text:
        err(f"archetype identity migration missing {required}")
if 'identity_suffix = "/identity"' not in host_agent_text or "character_identity.update" not in host_agent_text:
    err("host agent does not expose archetype identity editing")
if 'id="save-archetype"' not in ui or 'id="character-id" autocomplete="off"' not in ui:
    err("asset manager archetype edit controls are missing")
for required in ["saveArchetype", "save archetype identity first", "/identity"]:
    if required not in js_text:
        err(f"asset manager archetype editing ui missing {required}")

# m6.2 archetype registration safety + immutable character model replacement
character_store_text = (ROOT / "system/control-center/character_store.py").read_text(encoding="utf-8")
for required in ["existingId", "archetype {character_id} already exists", "def assign_model", "character_model_assignments"]:
    if required not in character_store_text:
        err(f"character registration/model reassignment contract missing {required}")
if "character_model_assignments" not in schema_text:
    err("control center schema missing character_model_assignments audit table")
if 'replace_model_suffix = "/replace-model"' not in host_agent_text or "store.publish(character_id, credentials)" not in host_agent_text:
    err("host agent does not expose sequential character model replacement")
if '"forceReplacement": True' not in host_agent_text:
    err("explicit character Replace must force a new immutable Roblox asset id")
if "and not replacement_pending" not in character_store_text:
    err("unchanged-content no-op must never swallow an explicit character replacement")
if "replace model did not create a new Roblox asset id" not in host_agent_text:
    err("replace-model endpoint must reject accidental reuse of the old Roblox asset id")
if 'id="character-model-source"' in ui:
    err("asset manager must not offer cross-archetype Roblox asset id reuse")
for required in ["replace model · publish new asset", "/replace-model", "existingId:row?.id||''"]:
    if required not in js_text:
        err(f"asset manager archetype model replacement ui missing {required}")
if 'source.get("model_asset_id")' in character_store_text:
    err("character model reassignment must not copy another archetype's Roblox asset id")


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
if 'AnimationSpeedScaling.ResolveForModel(character, "attack")' not in attack_text:
    err("server attack timeline does not resolve stat-scaled AttackSpeed playback")
if 'animationSpeedPercent = animationPlaybackPercent(slot)' not in controller_runtime:
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

# m6.2 Studio-native Test Loadout (ported from the reference architecture)
test_loadout_server_path = ROOT / "src/server/dev/TestLoadoutService.luau"
test_loadout_client_path = ROOT / "src/client/dev/TestLoadoutController.luau"
test_loadout_server = test_loadout_server_path.read_text(encoding="utf-8") if test_loadout_server_path.is_file() else ""
test_loadout_client = test_loadout_client_path.read_text(encoding="utf-8") if test_loadout_client_path.is_file() else ""
for required in ["GetTestLoadoutCatalog", "ApplyTestLoadout", "CharacterService.Respawn", "WeaponEquipService.Equip", "Game1TestLoadoutActive"]:
    if required not in test_loadout_server:
        err(f"Studio Test Loadout server missing {required}")
for required in ["TEST LOADOUT", "createDropdown", "createCategorySelector", "LastLoadoutArchetype", "LastLoadoutWeaponSlug", "ACCEPT LOADOUT", "RunService:IsStudio()"]:
    if required not in test_loadout_client:
        err(f"Studio Test Loadout client missing {required}")
for required in ["ATTACK RADIUS: OFF", "Game1AttackRadiusPreview", "createAttackRadiusRing", 'currentCharacter:GetAttribute("AttackRadius")', "RunService.RenderStepped"]:
    if required not in test_loadout_client:
        err(f"Studio Test Loadout attack-radius preview missing {required}")
if "attackRadiusStuds" not in test_loadout_server:
    err("Studio Test Loadout catalog must expose the registered weapon attack radius")
server_init_text = (ROOT / "src/server/init.server.luau").read_text(encoding="utf-8")
if "TestLoadoutService.Start()" not in server_init_text:
    err("Studio Test Loadout service is not started by the server runtime")
if "TestLoadoutController.Start()" not in client_init_text:
    err("Studio Test Loadout controller is not started by the client runtime")
for required in ["Game1StudioDebugPreferences_v1", "Game1StudioPreferences", "plugin:GetSetting", "plugin:SetSetting", "LastLoadoutArchetype", "LastLoadoutWeaponSlug", "ClientPreferencesReady"]:
    if required not in plugin_text:
        err(f"game1 Studio plugin loadout preference bridge missing {required}")
if (ROOT / "src/shared/dev/TestLoadoutConfig.luau").exists():
    err("obsolete generated TestLoadoutConfig must be removed")

# m20 Studio-native movement debugger: AM-seeded, runtime-editable tuning
movement_debug_server_path = ROOT / "src/server/dev/MovementDebugService.luau"
movement_debug_client_path = ROOT / "src/client/dev/MovementDebugController.luau"
movement_debug_server = movement_debug_server_path.read_text(encoding="utf-8") if movement_debug_server_path.is_file() else ""
movement_debug_client = movement_debug_client_path.read_text(encoding="utf-8") if movement_debug_client_path.is_file() else ""
for required in [
    "GetMovementDebugCatalog",
    "ApplyMovementDebug",
    "SetMovementDebugMonsterMode",
    "MovementDebugRunSpeedOverride",
    "applyRuntimeRunSpeed",
    "baseRunSpeed",
    "animationUnitsPerPercent",
    "animationChannel",
    "authoredUnitsPerPercent",
    "animationRules",
    "runSpeedUnitsPerStud",
    "CharacterMovementConfig.RobloxSpeed",
    "model = model",
    "Game1MonsterDebugLocomotionMode",
    "MonsterLocomotionMode",
    "RunService:IsStudio()",
]:
    if required not in movement_debug_server:
        err(f"Studio movement debugger server missing {required}")
for required in [
    "MOVEMENT DEBUG",
    "RunSpeed · runtime test value",
    "Run world speed · studs / second",
    "Animation ratio · stat units per 1% playback",
    "RULE: RUN",
    "AM RunSpeed",
    "runtime test",
    "ACTIVE",
    "calculatedPlayback",
    "animationUnitsPerPercent",
    "ApplyMovementDebug",
    "stageSpeedText",
    "stageAnimationText",
    "MONSTER BASE: WALK",
    "MEASURED · last 1.0 s",
    "modelPosition",
    "RunService.Heartbeat:Connect",
    "GetMovementDebugCatalog",
    "SetMovementDebugMonsterMode",
    "CATALOG_POLL_SECONDS",
    "RunService:IsStudio()",
]:
    if required not in movement_debug_client:
        err(f"Studio movement debugger client missing {required}")
for forbidden in ["animationSpeedPercent =", "MovementDebugAnimationSpeedPercentOverride"]:
    if forbidden in movement_debug_server or forbidden in movement_debug_client:
        err(f"Movement Debug must tune AM ratio, never own an absolute playback-percent override; found {forbidden}")
movement_config_text = (ROOT / "src/shared/character/CharacterMovementConfig.luau").read_text(encoding="utf-8")
for required in [
    "RunSpeedUnitsPerStud = 10",
    "WalkSpeedMultiplier = 0.5",
    "function CharacterMovementConfig.RobloxSpeed",
    "/ CharacterMovementConfig.RunSpeedUnitsPerStud",
    "function CharacterMovementConfig.RunSpeedFromStudsPerSecond",
]:
    if required not in movement_config_text:
        err(f"game-speed/world-distance conversion contract missing {required}")
if "MovementDebugRunSpeedOverride" not in stats_service_text:
    err("character stats must preserve the runtime Movement Debug RunSpeed override across stat recomputes")
if "MovementDebugService.Start()" not in server_init_text:
    err("Studio movement debugger service is not started by the server runtime")
if "MovementDebugController.Start()" not in client_init_text:
    err("Studio movement debugger controller is not started by the client runtime")


# m12 shared animation-speed scaling: gameplay stat -> playback percentage
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
    ("character", "human_female", "run"): "RunSpeed",
    ("character", "human_female", "walk"): "RunSpeed",
    ("character", "human_female", "attack"): "AttackSpeed",
    ("character", "human_female", "combat_idle"): "AttackSpeed",
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
for required in ["ResolveForModel", "ResolveDetailsForModel", "TargetForModel", "unitsPerPercent", "value / unitsPerPercent", "DebugUnitsPerPercentAttribute", "authoredUnitsPerPercent", "debugUnitsPerPercent"]:
    if required not in animation_scaling_runtime:
        err(f"animation speed scaling runtime missing {required}")
if "DebugOverrideAttribute" in animation_scaling_runtime or "MovementDebugAnimationSpeedPercentOverride" in animation_scaling_runtime:
    err("animation speed scaling must not support an absolute playback-percent debug override")
for required in ['["human_female"]', 'unitsPerPercent = 2.0', '["gremlin"]', 'unitsPerPercent = 0.6']:
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


# m7 monster registry / animation / character life + critical contract
monster_manifest_path = ROOT / "assets/manifests/monsters.json"
if not monster_manifest_path.is_file():
    err(r"monster manifest is missing; run python .\system\control-center\migrate.py")
    monster_manifest = {}
else:
    monster_manifest = json.loads(monster_manifest_path.read_text(encoding="utf-8"))
if monster_manifest.get("schemaVersion") != 1 or monster_manifest.get("project") != "game1":
    err("monster manifest must be game1 schema 1")
monster_options = monster_manifest.get("options") or {}
if monster_options.get("statKeys") != ["MaxHP", "Damage", "AttackSpeed", "RunSpeed", "CritChance"]:
    err("monster stat keys must be HP, attack, attack speed, run speed and crit chance")

monster_store_path = ROOT / "system/control-center/monster_store.py"
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
        err(f"monster store missing {required}")
for required in ["monsters", "monster_textures", "monster_stats", "monster_publications"]:
    if required not in schema_text:
        err(f"control center schema missing {required}")

monster_registry_path = ROOT / "src/shared/monster/MonsterRegistry.luau"
monster_registry_text = monster_registry_path.read_text(encoding="utf-8") if monster_registry_path.is_file() else ""
if "monsters = table.freeze" not in monster_registry_text:
    err("generated monster registry is missing")

monster_animation_manifest_path = ROOT / "assets/manifests/monster-animations.json"
if not monster_animation_manifest_path.is_file():
    err(r"monster animation manifest is missing; run python .\system\control-center\migrate.py")
    monster_animation_manifest = {}
else:
    monster_animation_manifest = json.loads(monster_animation_manifest_path.read_text(encoding="utf-8"))
if monster_animation_manifest.get("schemaVersion") != 1 or monster_animation_manifest.get("project") != "game1":
    err("monster animation manifest must be game1 schema 1")
for binding in monster_animation_manifest.get("bindings") or []:
    if "playbackSpeedPercent" in binding or "playback_speed_percent" in binding:
        err(f"monster animation binding must not own playback speed: {binding.get('id')}")
monster_slot_catalog = monster_animation_manifest.get("slotCatalog") or []
monster_slots = [row.get("slot") for row in monster_slot_catalog]
if monster_slots != ["idle", "idle_special", "walk", "run", "combat_idle", "attack", "death"]:
    err("monster animation storage slots must use combat_idle and must not expose attack_wait")
monster_states = [row.get("state") for row in monster_slot_catalog]
if monster_states != ["idle", "idle", "walk", "run", "combat_idle", "attack", "death"]:
    err("monster idle_special must stay inside idle and combat waiting must be combat_idle")
monster_assets_js_path = ROOT / "system/control-center/static/monster-assets.js"
monster_assets_js_text = monster_assets_js_path.read_text(encoding="utf-8") if monster_assets_js_path.is_file() else ""
monster_index_text = (ROOT / "system/control-center/static/index.html").read_text(encoding="utf-8")
for required in ["animationMonster", "monster-animation-monster", "monsterSelectAnimationTarget", "MONSTER_ANIMATION_TARGET_KEY"]:
    if required not in monster_assets_js_text and required not in monster_index_text:
        err(f"monster animation UI missing explicit target selector contract: {required}")
if "semantic monster profile" in monster_index_text:
    err("monster animation UI must not expose obsolete semantic monster profile jargon")

monster_animation_store_path = ROOT / "system/control-center/monster_animation_store.py"
monster_animation_store_text = monster_animation_store_path.read_text(encoding="utf-8") if monster_animation_store_path.is_file() else ""
for required in [
    "class MonsterAnimationStore", "def scan_folder", "def assign_file", "def publish_missing",
    '"slot": "idle"', '"slot": "idle_special"', '"state": "idle"', '"role": "special"', '"slot": "combat_idle"', '"variants": True', "canonicalFilename",
    '"sourceSlot": internal_slot', 'profile["slots"].setdefault(state', 'src/shared/monster/MonsterAnimationRegistry.luau',
]:
    if required not in monster_animation_store_text:
        err(f"monster animation store missing {required}")
for required in ["monster_animation_profiles", "monster_animation_clips", "monster_animation_bindings", "monster_animation_publications"]:
    if required not in schema_text:
        err(f"control center schema missing {required}")
monster_animation_registry_path = ROOT / "src/shared/monster/MonsterAnimationRegistry.luau"
monster_animation_registry_text = monster_animation_registry_path.read_text(encoding="utf-8") if monster_animation_registry_path.is_file() else ""
if "profiles = table.freeze" not in monster_animation_registry_text:
    err("generated monster animation registry is missing")

monster_js_path = ROOT / "system/control-center/static/monster-assets.js"
monster_js_text = monster_js_path.read_text(encoding="utf-8") if monster_js_path.is_file() else ""
for required in ['id="nav-monsters"', 'id="monsters-view"', 'id="register-monster"', 'id="monster-stat-hp"', 'id="monster-stat-damage"', 'id="monster-stat-attack-speed"', 'id="monster-stat-run-speed"', 'id="monster-stat-crit-chance"', 'id="monster-animation-filename-guide"']:
    if required not in ui:
        err(f"asset manager monster UI missing {required}")
for required in ["monsterRegister", "monsterPublish", "monsterSync", "monsterScanAnimations", "monsterPublishMissingAnimations", "MONSTER_FILENAME_GUIDE_KEY", "MONSTER_ANIMATION_FOLDER_KEY", "initMonsterAnimationFolderExplorer", "row.state||row.slot", "rule.state"]:
    if required not in monster_js_text:
        err(f"asset manager monster javascript missing {required}")
for forbidden in ["monsterSetAnimationSpeed", "data-speed"]:
    if forbidden in monster_js_text:
        err(f"asset manager monster clip table must not expose per-clip speed control: {forbidden}")
for required in ['id="monster-animation-folder-path"', 'id="choose-monster-animation-folder"', 'id="scan-monster-animations"']:
    if required not in ui:
        err(f"monster animation folder explorer missing {required}")
for required in ["GAME1_ANIMATION_PICKER_INITIAL_PATH", "choose_animation_folder(initial_path", '"initialPath"']:
    if required not in host_agent_text:
        err(f"host agent animation folder explorer missing {required}")
for required in ["MonsterStore", "MonsterAnimationStore", "sync_monster_to_studio", 'placement_mode="monster-rig"', '"/api/monsters"', '"/api/monster-animations"']:
    if required not in host_agent_text:
        err(f"host agent monster API missing {required}")
for required in ["monster-rig", "placeMonsterRig", "Game1MonsterRig", "MonsterSlug", "applyWeaponTextures(importedRig"]:
    if required not in plugin_text:
        err(f"studio bridge monster-rig placement missing {required}")

# m7 monster spawn authoring/runtime contract
monster_spawn_manifest_path = ROOT / "assets/manifests/monster-spawns.json"
if not monster_spawn_manifest_path.is_file():
    err("monster spawn manifest is missing")
    monster_spawn_manifest = {}
else:
    monster_spawn_manifest = json.loads(monster_spawn_manifest_path.read_text(encoding="utf-8"))
if monster_spawn_manifest.get("schemaVersion") != 1 or monster_spawn_manifest.get("project") != "game1":
    err("monster spawn manifest must be game1 schema 1")
if not isinstance(monster_spawn_manifest.get("records"), dict):
    err("monster spawn manifest records must be an object")

spawn_store_path = ROOT / "system/control-center/monster_spawn_store.py"
spawn_store_text = spawn_store_path.read_text(encoding="utf-8") if spawn_store_path.is_file() else ""
for required in ["class MonsterSpawnStore", "respawnSeconds", "spawnRadius", "maxAlive", "monster_usage", "MonsterSpawnRegistry.luau"]:
    if required not in spawn_store_text:
        err(f"monster spawn store missing {required}")

monster_spawn_js_path = ROOT / "system/control-center/static/monster-spawns.js"
monster_spawn_js_text = monster_spawn_js_path.read_text(encoding="utf-8") if monster_spawn_js_path.is_file() else ""
for required in ['id="monster-spawn-monster"', 'id="monster-spawn-place"', 'id="monster-spawn-register"', 'id="monster-spawn-radius"', 'id="monster-spawn-max-alive"']:
    if required not in ui:
        err(f"monster spawn UI missing {required}")
for required in ["/api/monster-spawns/place", "/api/monster-spawns/register", "restore", "validate"]:
    if required not in monster_spawn_js_text:
        err(f"monster spawn UI javascript missing {required}")
for required in ['"/api/monster-spawns"', '"/api/monster-spawns/place"', '"/api/monster-spawns/register"', "MonsterSpawnStore", "run_monster_spawn_bridge"]:
    if required not in host_agent_text:
        err(f"host agent monster spawn API missing {required}")
for required in ["monster-spawn", "Game1MonsterSpawnMarker", "Game1Authoring", "MonsterSpawns", "monsterSpawnPlacementResult", "Selection:Set"]:
    if required not in plugin_text:
        err(f"Studio monster spawn authoring missing {required}")

monster_spawner_path = ROOT / "src/server/monster/MonsterSpawnerService.luau"
monster_spawner_text = monster_spawner_path.read_text(encoding="utf-8") if monster_spawner_path.is_file() else ""
if 'finite(stats.RunSpeed, CharacterMovementConfig.DefaultRunSpeed)' not in monster_spawner_text:
    err("monster RunSpeed fallback must use the shared direct-speed contract")
for required in ["MonsterSpawnRegistry", "MonsterRegistry", "MonsterAnimationRegistry", "spawnRadius", "maxAlive", "respawnSeconds", "math.sqrt", "Workspace:Raycast", "EntityHitboxService.Attach", 'GetAttributeChangedSignal("LifeState")', '== "Dying"', 'publishedRows(profile, "idle")', 'weightedIdleChoice', 'MonsterAnimationState', 'MonsterIdleVariant', 'idleTrack.DidLoop', 'choice.track.Ended', 'playBaseIdle']:
    if required not in monster_spawner_text:
        err(f"monster runtime spawner missing {required}")
for required in ["HumanoidRootPart", 'Instance.new("Humanoid")', "humanoid:MoveTo", "MoveToFinished", "WANDER_PAUSE_MIN_SECONDS", "WANDER_PAUSE_MAX_SECONDS", "WANDER_MOVE_REFRESH_SECONDS", "CharacterMovementConfig.RobloxSpeed", 'firstPublishedTrack(profile, "walk")', "MonsterWanderEnabled"]:
    if required not in monster_spawner_text:
        err(f"monster random-wander runtime missing {required}")
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
    if required not in monster_spawner_text:
        err(f"monster live movement-debug locomotion missing {required}")
for required in ['VisualRootWeld', 'animatorFor(model, visual)', 'controller.Parent = visual']:
    if required not in monster_spawner_text:
        err(f"monster animated-navigation bridge missing {required}")
if "Game1MonsterVisualWeld" in monster_spawner_text:
    err("monster navigation must never rigid-weld every visual BasePart; weld only the rig root")
for required in ['Workspace:FindFirstChild("Game1Authoring")', 'authoring:FindFirstChild("MonsterSpawns")', "monsterSpawns:Destroy()", "removeAuthoringVisualsFromSimulation"]:
    if required not in monster_spawner_text:
        err(f"Play/Run monster-spawn authoring-visual cleanup missing {required}")
if "RunService.Heartbeat" in monster_spawner_text:
    err("monster spawn/wander runtime must not use a permanent Heartbeat loop")
if "MonsterSpawnerService.Start()" not in server_init_text:
    err("monster spawner is not started by the server runtime")

if "unicodedata.normalize" not in monster_store_text or "CYRILLIC_SLUG_MAP" not in monster_store_text:
    err("monster slug generation must normalize/transliterate English-name input robustly")
if "normalize('NFKD')" not in monster_js_text:
    err("monster slug preview must normalize unicode names")

for required in ["CritChance = 0"]:
    if required not in stats_config_text:
        err(f"character critical stat missing {required}")
if 'setBase(character, "CritChance", value("CritChance"))' not in stats_service_text:
    err("character critical chance is not initialized from archetype starting stats")
for required in ['"slot": "death"', '"slot": "revive"']:
    if required not in animation_store_text:
        err(f"character life animation catalog missing {required}")
if '"slot": "equip"' in animation_store_text or '"slot": "unequip"' in animation_store_text:
    err("character animation catalog must not expose equip/unequip states")
character_animation_manifest_path = ROOT / "assets/manifests/character-animations.json"
if character_animation_manifest_path.is_file():
    character_animation_manifest = json.loads(character_animation_manifest_path.read_text(encoding="utf-8"))
    obsolete_character_bindings = [
        row for row in (character_animation_manifest.get("bindings") or [])
        if str(row.get("slot") or "") in {"equip", "unequip"}
    ]
    if obsolete_character_bindings:
        err("character animation manifest still contains equip/unequip bindings")
if '"slot": "death_wait"' in animation_store_text:
    err("character animation catalog must not expose death_wait; DeathIdle holds the final death frame")
death_policy_path = ROOT / "src/shared/combat/DeathAnimationPolicy.luau"
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
        err(f"deterministic death terminal-hold policy missing {required}")

for forbidden in [
    "AdvanceToFinalKey",
    "track.TimePosition = finalKeyTime",
    "EndEpsilonSeconds",
]:
    if forbidden in death_policy_text:
        err(f"death terminal hold contains legacy path: {forbidden}")

for required in [
    "maintainDeathTerminalPose",
    "DeathAnimationPolicy.Start",
    "DeathAnimationPolicy.LatchVisibleTerminalPose",
    'MonsterAnimationState", "death_idle"',
    "DeathLifecycleService.BeginDeathIdle",
    "RunService.PreAnimation:Connect",
    "deathPoseHeld",
]:
    if required not in monster_spawner_text:
        err(f"monster death terminal-pose lifecycle missing {required}")

for required in [
    "ensureRuntimeAnimationRoot",
    'animationRoot.Name = "RootBone"',
    "animationRoot.CFrame = CFrame.identity",
    "bone.Parent = animationRoot",
    "RuntimeAnimationRootBridgeCount",
]:
    if required not in monster_spawner_text:
        err(f"monster root-bone animation bridge missing {required}")

character_animation_text = (ROOT / "src/client/character/animation/CharacterAnimationController.luau").read_text(encoding="utf-8")
for required in [
    "playDeath",
    "maintainDeathTerminalPose",
    "DeathAnimationPolicy.Start",
    "DeathAnimationPolicy.LatchVisibleTerminalPose",
    "DeathTerminalReached",
    "RunService.PreAnimation:Connect(maintainRuntimeAnimationTails)",
    "maintainDeathTerminalPose(deltaTimeSim)",
    "DeathTerminalPoseHeld",
]:
    if required not in character_animation_text:
        err(f"character death terminal-pose lifecycle missing {required}")

character_service_text = (ROOT / "src/server/character/CharacterService.luau").read_text(encoding="utf-8")
for required in ["beginPlayerDeathIdle", "DeathTerminalReached", "DeathLifecycleService.BeginDeathIdle"]:
    if required not in character_service_text:
        err(f"character death server handoff missing {required}")

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
    err("death playback must not use baked-FPS truncation")

combined_death_runtime = "\n".join([
    monster_spawner_text,
    character_animation_text,
    character_service_text,
    (ROOT / "src/shared/combat/EntityLifecycleConfig.luau").read_text(encoding="utf-8"),
])
for forbidden in legacy_death_tokens:
    if forbidden in combined_death_runtime:
        err(f"legacy/fallback death playback path must be removed: found {forbidden}")

damage_service_text = (ROOT / "src/server/combat/DamageService.luau").read_text(encoding="utf-8")
for required in ['SetAttribute("LifeState", "Dying")', 'SetAttribute("Damageable", false)', 'SetAttribute("DeathStartedAt"']:
    if required not in damage_service_text:
        err(f"HP=0 death edge missing {required}")

hit_effect_server = (ROOT / "src/server/combat/HitEffectService.luau").read_text(encoding="utf-8") if (ROOT / "src/server/combat/HitEffectService.luau").is_file() else ""
hit_effect_client = (ROOT / "src/client/combat/HitEffectController.luau").read_text(encoding="utf-8") if (ROOT / "src/client/combat/HitEffectController.luau").is_file() else ""
hit_sparks = (ROOT / "src/client/combat/effects/HitSparkBurst.luau").read_text(encoding="utf-8") if (ROOT / "src/client/combat/effects/HitSparkBurst.luau").is_file() else ""
for required in ["UnreliableRemoteEvent", "ServerReplicationRadius", "FireClient"]:
    if required not in hit_effect_server:
        err(f"server hit-effect bridge missing {required}")
for required in ["HitEffectPool", "BurstCapacity", "OnClientEvent"]:
    if required not in hit_effect_client:
        err(f"client hit-effect controller missing {required}")
for required in ["ImpactSpark", "Beam", "NormalSparkCount", "CriticalSparkCount"]:
    if required not in hit_sparks:
        err(f"pooled hit sparks missing {required}")
if "HitEffectService.Publish" not in (ROOT / "src/server/combat/AttackService.luau").read_text(encoding="utf-8"):
    err("confirmed melee hits do not publish hit sparks")

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

# m13+ starting stats; m15 runtime-only first-frame seam contract.
character_manifest = json.loads((ROOT / "assets/manifests/character-archetypes.json").read_text(encoding="utf-8"))
character_options = character_manifest.get("archetypes") or []
for row in character_options:
    stats = row.get("stats") or {}
    for key in ["Level", "MaxHP", "Damage", "Defense", "AttackSpeed", "RunSpeed", "CritChance"]:
        if key not in stats:
            err(f"character archetype starting stat missing {key}: {row.get('id')}")
character_store_m13 = (ROOT / "system/control-center/character_store.py").read_text(encoding="utf-8")
for required in ["character_stats", "set_stats", "defaultStats", '"stats": row.get("stats")']:
    if required not in character_store_m13:
        err(f"character starting-stat Asset Manager contract missing {required}")
for required in ["row.stats", 'value("RunSpeed")', 'value("AttackSpeed")']:
    if required not in (stats_service_text + character_service_text):
        err(f"character runtime starting-stat contract missing {required}")

# The first->end checkbox is metadata only. It must never rewrite an .rbxm,
# change publication checksums, revisions, or permanent asset ids.
transform_path = ROOT / "system/control-center/animation_keyframe_transform.py"
if transform_path.exists():
    err("legacy physical animation_keyframe_transform.py must be removed; first-frame seam is runtime-only")
for store_file in [ROOT / "system/control-center/animation_core/storage.py", ROOT / "system/control-center/monster_animation_store.py"]:
    text = store_file.read_text(encoding="utf-8") if store_file.is_file() else ""
    for required in ["source_sha256", "duplicate_first_frame_at_end", "set_duplicate_first_frame", "_normalize_source_only_files", "shutil.copy2"]:
        if required not in text:
            err(f"runtime animation seam storage contract missing {required} in {store_file.name}")
    if "prepare_animation_file" in text or "animation_keyframe_transform" in text:
        err(f"physical animation seam transformer is still referenced by {store_file.name}")
    setter = text.split("def set_duplicate_first_frame", 1)[1].split("def ", 1)[0] if "def set_duplicate_first_frame" in text else ""
    for forbidden in ["sha256=?", "source_sha256=?", "revision=?", "copy2(", "prepare_animation_file"]:
        if forbidden in setter:
            err(f"first-frame checkbox mutates animation content/revision in {store_file.name}: {forbidden}")
for required in ["duplicate-first-frame", "set_duplicate_first_frame"]:
    if required not in host_agent_text:
        err(f"animation seam API missing {required}")
for required in ["data-duplicate", "setAnimationDuplicate", "runtime first-frame tail"]:
    if required not in character_js_text:
        err(f"character animation seam UI missing {required}")
if "data-duplicate" not in monster_assets_js_early or "monsterSetAnimationDuplicate" not in monster_assets_js_early or "runtime first-frame tail" not in monster_assets_js_early:
    err("monster animation seam UI is missing/runtime wording is stale")

runtime_seam_path = ROOT / "src/shared/animation/AnimationFirstFrameSeam.luau"
runtime_seam_text = runtime_seam_path.read_text(encoding="utf-8") if runtime_seam_path.is_file() else ""
for required in ["SourceFrameSeconds", "companion", "AdjustWeight", "TimePosition = 0", "completedLoopCycle", "self.primary.Looped = self.looped", "self.primary:AdjustSpeed(self.speed)", "self.primary:AdjustWeight(1 - alpha, 0)", "current + 1e-5 < self.previousTime"]:
    if required not in runtime_seam_text:
        err(f"runtime first-frame seam policy missing {required}")
for forbidden in ["RuntimeTailSeconds", "_beginTail", "projected =", "self.primary:AdjustSpeed(0)"]:
    if forbidden in runtime_seam_text:
        err(f"runtime first-frame seam must not stall/restart the primary timeline: {forbidden}")
character_animation_controller_text = (ROOT / "src/client/character/animation/CharacterAnimationController.luau").read_text(encoding="utf-8")
character_track_cache_text = (ROOT / "src/client/character/animation/AnimationTrackCache.luau").read_text(encoding="utf-8")
monster_spawner_text_m15 = (ROOT / "src/server/monster/MonsterSpawnerService.luau").read_text(encoding="utf-8")
for required in ["AnimationFirstFrameSeam", "GetSeamCompanion", "duplicateFirstFrameAtEnd"]:
    if required not in (character_animation_controller_text + character_track_cache_text):
        err(f"character runtime seam integration missing {required}")
for required in ["AnimationFirstFrameSeam", "createRuntimeSeam", "maintainRuntimeAnimationSeams", "duplicateFirstFrameAtEnd"]:
    if required not in monster_spawner_text_m15:
        err(f"monster runtime seam integration missing {required}")
attack_runtime_text = attack_timeline_text + (ROOT / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
if "AnimationFirstFrameSeam.RuntimeTailSeconds" in attack_runtime_text:
    err("runtime seam must not extend attack duration or event timing")
if "duplicateFirstFrameAtEnd" in attack_timeline_text:
    err("attack timing resolver must not depend on presentation seam flags")

for animation_manifest_name in ["character-animations.json", "monster-animations.json"]:
    path = ROOT / "assets/manifests" / animation_manifest_name
    if not path.is_file():
        continue
    payload = json.loads(path.read_text(encoding="utf-8"))
    clips = payload.get("clips") or []
    for clip in clips:
        duplicate = clip.get("duplicateFirstFrameAtEnd", clip.get("duplicate_first_frame_at_end"))
        source_sha = clip.get("sourceSha256", clip.get("source_sha256"))
        if duplicate is None:
            err(f"animation manifest clip missing duplicate-first-frame runtime flag: {animation_manifest_name} / {clip.get('id')}")
        if source_sha is None:
            err(f"animation manifest clip missing canonical source sha: {animation_manifest_name} / {clip.get('id')}")

for registry_name in ["src/shared/character/CharacterAnimationRegistry.luau", "src/shared/monster/MonsterAnimationRegistry.luau"]:
    registry_text = (ROOT / registry_name).read_text(encoding="utf-8")
    if "duplicateFirstFrameAtEnd" not in registry_text:
        err(f"runtime animation registry does not export first-frame seam flag: {registry_name}")

# m18 manual animation reimport verification lives in Asset Manager and mirrors
# RobloxLineage: scan detects local SHA changes, Studio reimport remains manual,
# then Open Cloud asset versions confirm a newer Approved version of the same id.
fingerprint_path = ROOT / "system/control-center/animation_fingerprint.py"
if fingerprint_path.exists():
    err("Studio content fingerprint checker must be removed; reimport confirmation is Open Cloud version based")
studio_plugin_text = (ROOT / "system/studio-plugin/Game1Bridge.server.luau").read_text(encoding="utf-8")
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
for required in ["AttackMovementLocomotionMode", "combat_idle", "EquivalentRunSpeedForLocomotion", "ResolveForModelWithStatValue", "AnimationAttackLowerBodySlot"]:
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


# m23 global UI input guard + monster behavior/debug + RobloxLineage combat AI + damage feedback.
ui_guard_m23 = (ROOT / "src/client/UiInputGuard.luau").read_text(encoding="utf-8")
attack_controller_m23 = (ROOT / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
camera_controller_m23 = (ROOT / "src/client/character/CameraController.luau").read_text(encoding="utf-8")
movement_controller_m23 = (ROOT / "src/client/character/MovementController.luau").read_text(encoding="utf-8")
aim_pose_m23 = (ROOT / "src/client/combat/AimPoseController.luau").read_text(encoding="utf-8")
for required in ["GetGuiObjectsAtPosition", "WorldInputPassthrough", "GetFocusedTextBox", "BlocksWorldInput"]:
    if required not in ui_guard_m23:
        err(f"global UI world-input guard missing {required}")
for text, label in [(attack_controller_m23, "attack"), (camera_controller_m23, "camera"), (movement_controller_m23, "movement")]:
    if "UiInputGuard" not in text:
        err(f"{label} controller does not use global UI input guard")
if 'WorldInputPassthrough", true' not in aim_pose_m23:
    err("aim reticle must be an explicit UI world-input passthrough")

monster_manifest_m23 = json.loads((ROOT / "assets/manifests/monsters.json").read_text(encoding="utf-8"))
for monster in monster_manifest_m23.get("items") or []:
    behavior = monster.get("behavior") or {}
    for key in ["aggressive", "aggroRadiusStuds", "attackRadiusStuds"]:
        if key not in behavior:
            err(f"monster behavior manifest missing {monster.get('slug')}:{key}")
monster_store_m23 = (ROOT / "system/control-center/monster_store.py").read_text(encoding="utf-8")
monster_js_m23 = (ROOT / "system/control-center/static/monster-assets.js").read_text(encoding="utf-8")
monster_html_m23 = (ROOT / "system/control-center/static/index.html").read_text(encoding="utf-8")
for required in ["monster_behavior", "aggroRadiusStuds", "attackRadiusStuds", "aggressive"]:
    if required not in monster_store_m23:
        err(f"Asset Manager monster behavior storage missing {required}")
for required in ["monster-behavior-aggressive", "monster-behavior-aggro-radius", "monster-behavior-attack-radius"]:
    if required not in monster_js_m23 + monster_html_m23:
        err(f"Asset Manager monster behavior UI missing {required}")

monster_debug_server_m23 = (ROOT / "src/server/dev/MonsterDebugService.luau").read_text(encoding="utf-8")
monster_debug_client_m23 = (ROOT / "src/client/dev/MonsterDebugController.luau").read_text(encoding="utf-8")
for required in ["GetMonsterDebugCatalog", "ApplyMonsterDebug", "MonsterAggressive", "MonsterAggroRadius", "MonsterAttackRadius"]:
    if required not in monster_debug_server_m23:
        err(f"Monster Debug server contract missing {required}")
for required in ["☑ AGGRESSIVE", "☐ PASSIVE", "AGGRO RADIUS", "ATTACK RADIUS", "RESET FROM ASSET MANAGER", "Game1MonsterAggroRadiusPreview", "Game1MonsterAttackRadiusPreview"]:
    if required not in monster_debug_client_m23:
        err(f"Monster Debug client UI missing {required}")

monster_ai_m23 = (ROOT / "src/server/monster/MonsterAIService.luau").read_text(encoding="utf-8")
spawner_m23 = (ROOT / "src/server/monster/MonsterSpawnerService.luau").read_text(encoding="utf-8")
for required in ["Aggro", "Chase", "Attack", "pursueDirectlyDuringAttack", "attackStillConnects", "PathfindingService", "MonsterAttackPursuitActive", "AttackTimelineConfig.ResolveRuntime"]:
    if required not in monster_ai_m23:
        err(f"RobloxLineage monster combat AI contract missing {required}")
for required in ["MonsterAuthoredAggressive", "MonsterAuthoredAggroRadius", "MonsterAuthoredAttackRadius", "MonsterCombatActive"]:
    if required not in spawner_m23:
        err(f"monster spawner behavior bridge missing {required}")
monster_locomotion_m23 = (ROOT / "src/client/monster/MonsterAttackLocomotionController.luau").read_text(encoding="utf-8")
for required in ["MonsterAttackPursuitActive", "MonsterAttackPursuitPlaybackSpeed", "lowerPaths", "PreSimulation"]:
    if required not in monster_locomotion_m23:
        err(f"monster attack lower-body composition missing {required}")

feedback_server_m23 = (ROOT / "src/server/combat/CombatFeedbackService.luau").read_text(encoding="utf-8")
feedback_client_m23 = (ROOT / "src/client/combat/CombatFeedbackController.luau").read_text(encoding="utf-8")
feedback_visuals_m39_path = ROOT / "src/client/combat/CombatFloatingText.luau"
feedback_visuals_m39 = feedback_visuals_m39_path.read_text(encoding="utf-8") if feedback_visuals_m39_path.is_file() else ""
damage_m23 = (ROOT / "src/server/combat/DamageService.luau").read_text(encoding="utf-8")
for required in ["outgoing", "incoming", "PublishDamage"]:
    if required not in feedback_server_m23:
        err(f"damage feedback server missing {required}")
for required in ["IncomingDamageNumber", "Color3.fromRGB(255, 82, 82)", "CombatDamageNumber"]:
    if required not in feedback_visuals_m39:
        err(f"damage feedback visuals missing {required}")
for required in ['WaitForChild("CombatFloatingText")', "ShowDamage", "ShowCritical", "if critical then"]:
    if required not in feedback_client_m23:
        err(f"m39 combat feedback controller missing {required}")
for required in ['gui.Name = "CriticalBillboard"', 'label.Text = "Critical!"', "CRITICAL_LIFETIME", "CRITICAL_RISE_STUDS"]:
    if required not in feedback_visuals_m39:
        err(f"m39 Critical! world feedback missing {required}")
if "CombatFeedbackService.PublishDamage" not in damage_m23:
    err("DamageService does not publish authoritative damage feedback")

# m25 continuous active-attack pursuit + authored return-to-town revive.
monster_ai_m25 = (ROOT / "src/server/monster/MonsterAIService.luau").read_text(encoding="utf-8")
for required in [
    'RunService.Heartbeat:Wait()',
    'agent.humanoid:Move(direction, false)',
    'ATTACK_PURSUIT_FOLLOW_GAIN',
    'targetRoot.AssemblyLinearVelocity',
    'The slower AI decision loop must not issue competing MoveTo calls',
]:
    if required not in monster_ai_m25:
        err(f"m25 continuous attack pursuit contract missing {required}")
pursuit_body_m25 = monster_ai_m25.split('local function pursueDirectlyDuringAttack', 1)[-1].split('local function maintainAttackPursuit', 1)[0]
if 'MoveTo(' in pursuit_body_m25:
    err("active-attack pursuit must not stream MoveTo destinations")

monster_sampler_m25 = (ROOT / "src/client/monster/MonsterLocomotionSampler.luau").read_text(encoding="utf-8")
monster_compositor_m25 = (ROOT / "src/client/monster/MonsterAttackLocomotionController.luau").read_text(encoding="utf-8")
for required in ['SetPlaybackSpeed', 'AdjustSpeed(speed)']:
    if required not in monster_sampler_m25:
        err(f"monster pursuit sampler live-speed contract missing {required}")
for required in ['suppressHorizontalAttackRootMotion', 'Game1RuntimeAnimationRoot', 'transform.Position.Y', 'entry.sampler:SetPlaybackSpeed']:
    if required not in monster_compositor_m25:
        err(f"monster pursuit visual stabilization missing {required}")
if 'releaseSampler(entry)\n\t\t\tif model:GetAttribute("MonsterAttackPursuitActive")' in monster_compositor_m25:
    err("pursuit playback changes must not rebuild the locomotion sampler")

character_service_m25 = (ROOT / "src/server/character/CharacterService.luau").read_text(encoding="utf-8")
death_respawn_path_m25 = ROOT / "src/client/character/DeathRespawnController.luau"
death_respawn_m25 = death_respawn_path_m25.read_text(encoding="utf-8") if death_respawn_path_m25.is_file() else ""
character_animation_m25 = (ROOT / "src/client/character/animation/CharacterAnimationController.luau").read_text(encoding="utf-8")
for required in ["ReturnToTownAvailable", "CharacterService.ReturnToTown", 'RemoteFunction', 'returnToTown.OnServerInvoke']:
    if required not in character_service_m25:
        err(f"return-to-town server contract missing {required}")
if 'createCharacter(player, tostring(player:GetAttribute("SelectedCharacterArchetype") or ""))' in character_service_m25.split('local function beginPlayerDeathIdle', 1)[-1].split('createCharacter = function', 1)[0]:
    err("player death lifecycle must not auto-respawn after DeathIdle")
for required in ["Game1DeathRespawn", "В город", "ReturnToTown", 'LifeState") or "") == "DeathIdle"']:
    if required not in death_respawn_m25:
        err(f"return-to-town client UI missing {required}")
for required in ['reviveOnSpawn', 'LifeState", "Reviving"', 'RevivePending', 'ReviveAnimationFinished', 'createCharacter(player, requested, true)']:
    if required not in character_service_m25:
        err(f"return-to-town revive server contract missing {required}")
for required in ['current == "Reviving"', 'playBaseLifeAction("revive"', 'notifyReviveAnimationFinished', 'lastLifeState == "Reviving"']:
    if required not in character_animation_m25:
        err(f"return-to-town revive animation contract missing {required}")
client_init_m25 = (ROOT / "src/client/init.client.luau").read_text(encoding="utf-8")
if "DeathRespawnController.Start()" not in client_init_m25:
    err("death respawn controller is not started")

# m26 common Options + authoritative combat-state idle + global character death/revive playback.
options_manifest_path_m26 = ROOT / "assets/manifests/options.json"
if not options_manifest_path_m26.is_file():
    err("m26 Options manifest is missing")
    options_manifest_m26 = {}
else:
    options_manifest_m26 = json.loads(options_manifest_path_m26.read_text(encoding="utf-8"))
combat_options_m26 = options_manifest_m26.get("combat") or {}
life_options_m26 = options_manifest_m26.get("characterAnimations") or {}
if float(combat_options_m26.get("stateDurationSeconds") or -1) != 6.0:
    err("m26 combat state default duration must be 6 seconds")
for key in ["deathPlaybackPercent", "revivePlaybackPercent"]:
    value = float(life_options_m26.get(key) or 0)
    if value < 1 or value > 400:
        err(f"m26 character life playback option invalid: {key}")

options_store_m26 = (ROOT / "system/control-center/options_store.py").read_text(encoding="utf-8")
options_html_m26 = (ROOT / "system/control-center/static/index.html").read_text(encoding="utf-8")
options_js_m26 = (ROOT / "system/control-center/static/options.js").read_text(encoding="utf-8")
host_agent_m26 = (ROOT / "system/control-center/host_agent.py").read_text(encoding="utf-8")
for required in ["stateDurationSeconds", "deathPlaybackPercent", "revivePlaybackPercent", "GameOptionsRegistry.luau"]:
    if required not in options_store_m26:
        err(f"m26 Options storage missing {required}")
for required in ["nav-options", "options-view", "combat state duration", "death playback %", "revive playback %"]:
    if required not in options_html_m26:
        err(f"m26 Options UI missing {required}")
for required in ["/api/options", "save-combat-options", "save-character-life-options"]:
    if required not in options_js_m26 + host_agent_m26:
        err(f"m26 Options API/UI missing {required}")

combat_state_service_m26 = (ROOT / "src/server/combat/CombatStateService.luau").read_text(encoding="utf-8")
damage_service_m26 = (ROOT / "src/server/combat/DamageService.luau").read_text(encoding="utf-8")
for required in ["GameOptions.CombatStateDurationSeconds", 'SetAttribute("InCombat", true)', 'SetAttribute("CombatState", "Combat")', "CombatUntilServerTime", "ActivatePair"]:
    if required not in combat_state_service_m26:
        err(f"m26 combat-state service missing {required}")
if "CombatStateService.ActivatePair(attacker, target)" not in damage_service_m26:
    err("m26 DamageService must activate combat state for damage dealer and receiver")

character_animation_m26 = (ROOT / "src/client/character/animation/CharacterAnimationController.luau").read_text(encoding="utf-8")
for required in ['GetAttribute("InCombat") == true', 'return "combat_idle"', "GameOptions.CharacterLifePlaybackPercent"]:
    if required not in character_animation_m26:
        err(f"m26 character combat/life animation contract missing {required}")
monster_spawner_m26 = (ROOT / "src/server/monster/MonsterSpawnerService.luau").read_text(encoding="utf-8")
for required in ["playCombatIdleState", "combatIdleTrack", 'GetAttribute("InCombat")', 'MonsterAnimationState", "combat_idle"']:
    if required not in monster_spawner_m26:
        err(f"m26 monster combat-idle contract missing {required}")

game_options_m26 = (ROOT / "src/shared/GameOptions.luau").read_text(encoding="utf-8")
game_options_registry_m26 = (ROOT / "src/shared/GameOptionsRegistry.luau").read_text(encoding="utf-8")
for required in ["CombatStateDurationSeconds", "CharacterLifePlaybackPercent"]:
    if required not in game_options_m26:
        err(f"m26 shared GameOptions missing {required}")
for required in ["stateDurationSeconds", "deathPlaybackPercent", "revivePlaybackPercent"]:
    if required not in game_options_registry_m26:
        err(f"m26 generated options registry missing {required}")

# m27 animated EquippedWeapon volume + multi-target melee + Test Loadout preview.
weapon_volume_path_m27 = ROOT / "src/shared/combat/WeaponAttackVolume.luau"
weapon_volume_m27 = weapon_volume_path_m27.read_text(encoding="utf-8") if weapon_volume_path_m27.is_file() else ""
for required in [
    "WeaponAttackVolume.StampWeaponBox",
    "WeaponAttackVolume.ReadEquippedWeaponBox",
    "WeaponAttackVolume.Build",
    "distanceToSphereExit",
    "bladeGeometry",
]:
    if required not in weapon_volume_m27:
        err(f"m27 animated weapon hit-volume contract missing {required}")

weapon_equip_m27 = (ROOT / "src/server/weapon/WeaponEquipService.luau").read_text(encoding="utf-8")
if "WeaponAttackVolume.StampWeaponBox(weapon)" not in weapon_equip_m27:
    err("m27 equipped weapons must persist their canonical local attack box")

attack_controller_m27 = (ROOT / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
for required in [
    'WaitForChild("AttackWeaponPose")',
    "WeaponPoseSampleInterval",
    "publishWeaponPose",
    "clientAttackId = sequence",
]:
    if required not in attack_controller_m27:
        err(f"m27 client animated weapon-pose sampling missing {required}")

attack_service_m27 = (ROOT / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
for required in [
    "applyAnimatedWeaponSweep",
    "animated_weapon_sweep",
    "WeaponAttackVolume.Build",
    'poseEvent.Name = "AttackWeaponPose"',
    "weaponSweepStates",
    "hitCount += 1",
]:
    if required not in attack_service_m27:
        err(f"m27 server weapon-volume/multi-target contract missing {required}")
if "local best: Model?" in attack_service_m27:
    err("m27 melee damage must not collapse an animated weapon volume to one best target")

test_loadout_m27 = (ROOT / "src/client/dev/TestLoadoutController.luau").read_text(encoding="utf-8")
for required in [
    "WEAPON HIT VOLUME: OFF",
    "createWeaponHitVolumePreview",
    "renderWeaponHitVolume",
    "WeaponAttackVolume.Build",
]:
    if required not in test_loadout_m27:
        err(f"m27 Test Loadout weapon-volume preview missing {required}")

# m29 contact-driven animated weapon sweep. Damage is no longer gated by one
# timeline frame; accepted poses are queried continuously with interpolation and
# one-hit-per-target deduplication. m32 narrows that sweep to the pre-Hit window.
attack_service_m29 = (ROOT / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
for required in [
    "activeHitTargets",
    "applyAnimatedWeaponSweep",
    "animated_weapon_sweep",
    "lastBoxCFrame",
    "previousBoxCFrame:Lerp",
    "and (not hitTargets or hitTargets[model] ~= true)",
]:
    if required not in attack_service_m29:
        err(f"m29 continuous weapon-contact sweep missing {required}")

attack_config_m29 = (ROOT / "src/shared/combat/AttackConfig.luau").read_text(encoding="utf-8")
for required in [
    "WeaponPoseSweepLinearStep",
    "WeaponPoseSweepAngularStep",
    "WeaponPoseSweepMaxSubsteps",
]:
    if required not in attack_config_m29:
        err(f"m29 weapon sweep config missing {required}")

# m31 precomputed tight hitboxes. Mesh geometry is read only while the rig is
# loaded; attack-time work is limited to cached bone transforms and OBB tests.
entity_hitbox_m31 = (ROOT / "src/server/combat/EntityHitboxService.luau").read_text(encoding="utf-8")
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
        err(f"m31 precomputed hitbox contract missing {required}")
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
        err(f"m31 obsolete runtime hit geometry remains: {forbidden}")

attack_service_m31 = (ROOT / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
for required in [
    "HeadshotDamageMultiplier",
    'SetAttribute("LastHeadshot"',
    'SetAttribute("LastAttackHeadshot"',
    "QueryDamageablesInBox(character, boxCFrame, boxSize, hitTargets)",
]:
    if required not in attack_service_m31:
        err(f"m31 combat-hitbox integration missing {required}")
for forbidden in ["fallbackAimVolume", "unarmed_fallback"]:
    if forbidden in attack_service_m31:
        err(f"m31 obsolete melee fallback remains: {forbidden}")

attack_config_m31 = (ROOT / "src/shared/combat/AttackConfig.luau").read_text(encoding="utf-8")
if "HeadshotDamageMultiplier = 2" not in attack_config_m31:
    err("m31 default headshot multiplier must stay explicit and tunable")
if "BoxWidth" in attack_config_m31 or "BoxHeight" in attack_config_m31:
    err("m31 obsolete aim-volume dimensions must be removed")

dummy_m31 = (ROOT / "src/server/dev/TrainingDummyService.luau").read_text(encoding="utf-8")
for required in ["EntityHitboxService.Attach(model, visual)", "combat hitboxes attached"]:
    if required not in dummy_m31:
        err(f"m31 Training Dummy hitbox binding missing {required}")
if "fallback dummy" in dummy_m31:
    err("m31 Training Dummy must not create a non-mesh fallback target")

test_loadout_m31 = (ROOT / "src/client/dev/TestLoadoutController.luau").read_text(encoding="utf-8")
for required in [
    "TARGET HITBOXES: OFF",
    "Game1TargetHitboxPreview",
    "CombatHitboxDebugData",
    "precomputed_bone_boxes",
]:
    if required not in test_loadout_m31:
        err(f"m31 Test Loadout hitbox preview missing {required}")
for forbidden in ["TARGET MESH REGIONS", "CombatMeshBodyBoxCFrame", "CombatMeshHeadCutoffY"]:
    if forbidden in test_loadout_m31:
        err(f"m31 obsolete mesh-classifier preview remains: {forbidden}")

monster_m31 = (ROOT / "src/server/monster/MonsterSpawnerService.luau").read_text(encoding="utf-8")
if "PoseHitboxCount" in monster_m31:
    err("m31 monster runtime still publishes obsolete PoseHitboxCount")
if 'SetAttribute("CombatHitboxCount", hitbox.count)' not in monster_m31:
    err("m31 monster runtime must publish CombatHitboxCount")


# m32 terminal Hit window + blade-side weapon volume. Continuous contact is
# allowed only through the authored Hit event; imported handle geometry behind
# the character weapon bone is never part of the attacking OBB.
weapon_volume_m32 = (ROOT / "src/shared/combat/WeaponAttackVolume.luau").read_text(encoding="utf-8")
for required in [
    'BONE_BOX_LOCAL_ATTRIBUTE = "WeaponAttackBoneBoxLocalPosition"',
    "bladeGeometry",
    "ReadWeaponBoneBoxLocalPosition",
    "weaponBonePosition",
    "bladeLength + extension",
]:
    if required not in weapon_volume_m32:
        err(f"m32 bone-to-blade volume contract missing {required}")
for forbidden in ["ReadGripBoxLocalPosition", "outwardDirection"]:
    if forbidden in weapon_volume_m32:
        err(f"m32 obsolete handle-inclusive weapon-volume path remains: {forbidden}")

attack_service_m32 = (ROOT / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
if "ReadWeaponBoneBoxLocalPosition" not in attack_service_m32:
    err("m32 server weapon sweep must use the weapon-bone cutoff")

test_loadout_m32 = (ROOT / "src/client/dev/TestLoadoutController.luau").read_text(encoding="utf-8")
if "ReadWeaponBoneBoxLocalPosition" not in test_loadout_m32:
    err("m32 Test Loadout weapon-volume preview must use the weapon-bone cutoff")
if "ReadGripBoxLocalPosition" in test_loadout_m32:
    err("m32 Test Loadout still uses obsolete grip/handle volume origin")



# m33 reticle-ray headshot policy. Weapon contact remains multi-target and uses
# the same precomputed hitboxes, but headshot classification is independent:
# the center-screen aim segment is clamped to AttackRadius and may upgrade only
# the one nearest combat region under the reticle, at most once per attack.
aim_pose_m33 = (ROOT / "src/client/combat/AimPoseController.luau").read_text(encoding="utf-8")
for required in [
    "function AimPoseController.GetAimRay()",
    "ViewportPointToRay",
    "return ray.Origin, direction.Unit",
]:
    if required not in aim_pose_m33:
        err(f"m33 center-screen aim-ray source missing {required}")

attack_controller_m33 = (ROOT / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
for required in [
    "aimPoseController.GetAimRay",
    "aimOrigin = aimOrigin",
    "aimDirection = aimDirection",
]:
    if required not in attack_controller_m33:
        err(f"m33 weapon-pose aim sampling missing {required}")
if "aim = target" in attack_controller_m33:
    err("m33 obsolete one-shot AttackIntent aim payload remains")

entity_hitbox_m33 = (ROOT / "src/server/combat/EntityHitboxService.luau").read_text(encoding="utf-8")
for required in [
    "rayBoxDistance",
    "raySegmentNearSphere",
    "queryAimBinding",
    "EntityHitboxService.RaycastAimRegions",
    'geometryRole = "head"',
    'geometryRole = "body"',
]:
    if required not in entity_hitbox_m33:
        err(f"m33 finite aim-region ray query missing {required}")
for forbidden in ['hitZone = "head"', 'hitZone = "body"']:
    if forbidden in entity_hitbox_m33:
        err(f"m33 weapon contact still classifies headshot directly: {forbidden}")

attack_service_m33 = (ROOT / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
for required in [
    "activeHeadshotTarget",
    "normalizeAimSample",
    "buildHeadshotAimSegment",
    "RaycastAimRegions",
    'aimedRegion.zone == "head"',
    "aimedRegion.model == model",
    "damageMultiplier = if isHeadshot",
    "sampledAimOrigin",
    "sampledAimDirection",
    "lastAimOrigin",
    "lastAimDirection",
]:
    if required not in attack_service_m33:
        err(f"m33 reticle-gated headshot integration missing {required}")
if "hit.hitZone" in attack_service_m33:
    err("m33 headshot must not come from weapon-contact hitZone")

attack_config_m33 = (ROOT / "src/shared/combat/AttackConfig.luau").read_text(encoding="utf-8")
for required in ["HeadshotDamageMultiplier = 2", "HeadshotAimOriginMaxDistance"]:
    if required not in attack_config_m33:
        err(f"m33 headshot config missing {required}")


# m38 character attack damage policy. Character attacks use an authored
# HitStart -> HitEnd interval. The old terminal Hit/result dispatch and pose
# buffer are removed; monsters intentionally keep their single Hit checkpoint.
attack_timeline_manifest_path = ROOT / "assets/manifests/attack-timelines.json"
attack_timeline_manifest = json.loads(attack_timeline_manifest_path.read_text(encoding="utf-8")) if attack_timeline_manifest_path.is_file() else {}
if int(attack_timeline_manifest.get("schemaVersion") or 0) != 2:
    err("m38 attack timeline manifest must use schemaVersion 2")
attack_timeline_rows = {str(row.get("clipId") or ""): row for row in attack_timeline_manifest.get("timelines") or []}
for clip_id in [
    "human_female__weapon__1hs__attack__01",
    "human_female__weapon__1hs__attack__02",
    "human_female__weapon__1hs__attack__03",
]:
    row = attack_timeline_rows.get(clip_id)
    if not row:
        err(f"m38 character timeline clip missing {clip_id}")
        continue
    events = row.get("events") or {}
    if "HitStart" not in events or "HitEnd" not in events:
        err(f"m38 {clip_id} requires HitStart and HitEnd")
    if "Hit" in events:
        err(f"m38 {clip_id} must not keep obsolete character Hit damage event")
    if float((events.get("HitStart") or {}).get("normalizedTime") or 0) > float((events.get("HitEnd") or {}).get("normalizedTime") or 0):
        err(f"m38 {clip_id} HitStart cannot be after HitEnd")
monster_timeline = attack_timeline_rows.get("monster__gremlin__attack__01") or {}
monster_events = monster_timeline.get("events") or {}
if "Hit" not in monster_events or "HitStart" in monster_events or "HitEnd" in monster_events:
    err("m38 monster timeline must retain only its single Hit policy")

character_window_path = ROOT / "src/shared/combat/CharacterAttackWindow.luau"
character_window_text = character_window_path.read_text(encoding="utf-8") if character_window_path.is_file() else ""
for required in ["CharacterAttackWindow.Resolve", "events and events.HitStart", "events and events.HitEnd", "startTime", "endTime"]:
    if required not in character_window_text:
        err(f"m38 character damage-window policy missing {required}")

attack_controller_m38 = (ROOT / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
for required in [
    "CharacterAttackWindow.Resolve(action.timeline)",
    "damageWindow.startTime",
    "damageWindow.endTime",
    "activePoseFrom = activePoseStartedAt + damagePoseStart",
    "activePoseUntil = activePoseStartedAt + damagePoseEnd",
]:
    if required not in attack_controller_m38:
        err(f"m38 client HitStart/HitEnd pose window missing {required}")

attack_service_m38 = (ROOT / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
for required in [
    "activeDamageWindows",
    "CharacterAttackWindow.Resolve(timing)",
    'SetAttribute("AttackDamageStartsAt"',
    'SetAttribute("AttackDamageEndsAt"',
    "elapsed + 1e-4 < damageWindow.startTime",
    "elapsed > damageWindow.endTime + 1e-4",
    "weaponSweepStates",
]:
    if required not in attack_service_m38:
        err(f"m38 server HitStart/HitEnd damage gate missing {required}")
for forbidden in [
    "activeDamageUntil",
    "activeDamageCutoffElapsed",
    "activeDamageStartElapsed",
    "meleeDamageWindow",
    "scheduleTimelineResults",
    "resolveMeleeDamage",
    "validatedAnimatedWeaponVolume",
    "weaponPoseBuffers",
    "lastDamageElapsed",
]:
    if forbidden in attack_service_m38:
        err(f"m38 obsolete terminal-Hit/pose-buffer path remains: {forbidden}")

# m35 Attack Timeline authoring is owned by Asset Manager. Studio only previews
# the published rig/animation and sends confirmed normalized event points back.
timeline_store_text = (ROOT / "system/control-center/timeline_store.py").read_text(encoding="utf-8")
timeline_js_text = (ROOT / "system/control-center/static/timelines.js").read_text(encoding="utf-8")
index_m35_text = (ROOT / "system/control-center/static/index.html").read_text(encoding="utf-8")
studio_bridge_m35_text = (ROOT / "system/control-center/studio_bridge.py").read_text(encoding="utf-8")
for required in [
    '"schemaVersion": 2',
    '"project": "game1"',
    '"timelines"',
]:
    if required not in attack_timeline_manifest_path.read_text(encoding="utf-8"):
        err(f"m35 attack timeline manifest missing {required}")
for required in [
    'require(script.Parent:WaitForChild("AttackTimelineData"))',
    "AttackTimelineConfig.ByClip = BY_CLIP",
]:
    if required not in attack_timeline_text:
        err(f"m35 runtime timeline resolver missing {required}")
for required in [
    "class TimelineStore",
    "begin_editor_session",
    "update_editor_state",
    "export_runtime",
    "attack-timelines.json",
    "AttackTimelineData.luau",
]:
    if required not in timeline_store_text:
        err(f"m35 timeline store missing {required}")
for required in ["EVENT_CATALOGS", '"characters"', '"HitStart"', '"HitEnd"', '"monsters"', '"Hit"', "event_catalog_for_subject"]:
    if required not in timeline_store_text:
        err(f"m38 subject-specific timeline catalog missing {required}")
for forbidden in ["Hit2", "projectile_release", '"result"']:
    if forbidden in timeline_store_text:
        err(f"m38 obsolete generic timeline event plumbing remains: {forbidden}")
if "eventCatalogs" not in timeline_js_text:
    err("m38 Asset Manager must render the subject-specific event catalog")
for required in [
    'id="nav-timelines"',
    'id="timelines-view"',
    'id="timeline-open-studio"',
    'timelines.js?v=2',
]:
    if required not in index_m35_text:
        err(f"m35 Asset Manager timeline UI missing {required}")
for required in [
    "/api/timelines/open",
    "/api/timelines/editor-state",
    "/api/timelines/save",
    "setInterval(timelinePoll,700)",
]:
    if required not in timeline_js_text:
        err(f"m35 Asset Manager timeline behavior missing {required}")
for required in [
    "run_timeline_editor_bridge",
    '"command": "timeline-editor"',
    '"/timeline-editor-result"',
]:
    if required not in studio_bridge_m35_text:
        err(f"m35 Studio timeline bridge missing {required}")
for required in [
    "Game1AttackTimeline_v2",
    "handleTimelineEditor",
    "Confirm point",
    'AGENT_BASE_URL .. "/api/timelines/editor-event"',
]:
    if required not in studio_plugin_text:
        err(f"m35 Studio Attack Timeline plugin missing {required}")

# m37 follows the RobloxLineage Attack Options preview model: the selected rig lives
# inside a ViewportFrame/WorldModel and the fetched KeyframeSequence is sampled directly
# onto Bone/Motor6D.Transform. Timeline authoring no longer depends on AnimationTrack
# playback in edit-mode Workspace.
for required in [
    'game:GetService("AnimationClipProvider")',
    'game:GetService("TweenService")',
    'Instance.new("ViewportFrame")',
    'Instance.new("WorldModel")',
    'TimelinePreviewWorld',
    'buildTimelinePoseTracks',
    'sampleTimelineTrack',
    'applyTimelinePose',
    'AnimationClipProvider:GetAnimationClipAsync',
    'clip:IsA("KeyframeSequence")',
    'preview.Parent = timelineWorld',
    'model bridge v22',
]:
    if required not in studio_plugin_text:
        err(f"m37 in-plugin timeline preview missing {required}")
for removed in [
    "timelineFreezeTrackAt",
    "track.TimePosition",
    "timelineEditor.track",
    "preview.Parent = Workspace",
]:
    if removed in studio_plugin_text:
        err(f"m37 Studio timeline still contains obsolete Workspace/AnimationTrack preview code: {removed}")
for required in [
    'path == "/api/timelines"',
    'path == "/api/timelines/open"',
    'path == "/api/timelines/editor-event"',
    'path == "/api/timelines/save"',
]:
    if required not in host_agent_text:
        err(f"m35 host agent timeline API missing {required}")
for clip_id in [
    "human_female__weapon__1hs__attack__01",
    "human_female__weapon__1hs__attack__02",
    "human_female__weapon__1hs__attack__03",
    "monster__gremlin__attack__01",
]:
    if clip_id not in attack_timeline_data_text:
        err(f"m35 generated runtime timeline is missing {clip_id}")


# m38 Rojo hotfix: live sync owns runtime code, not authored Workspace scene.
live_project = json.loads((ROOT / "default.project.json").read_text(encoding="utf-8"))
workspace_node = ((live_project.get("tree") or {}).get("Workspace") or {})
if workspace_node.get("$ignoreUnknownInstances") is not True:
    err("m38 live Rojo Workspace must preserve unknown/authored Studio instances")
for forbidden in ["Baseplate", "SpawnLocation"]:
    if forbidden in workspace_node:
        err(f"m38 live Rojo must not own authored Workspace child {forbidden}")
build_place_text = (ROOT / "place/build-place.ps1").read_text(encoding="utf-8")
for required in [".build-place.project.json", "Add-Member -NotePropertyName 'Baseplate'", "Add-Member -NotePropertyName 'SpawnLocation'", "Live Rojo will preserve authored Workspace children"]:
    if required not in build_place_text:
        err(f"m38 seed-place build isolation missing {required}")


# m40 Asset Manager: Animation Speed is presented as one clear card per animation channel.
animation_speed_ui_text = (ROOT / "system/control-center/static/animation-speed.js").read_text(encoding="utf-8")
animation_speed_css_text = (ROOT / "system/control-center/static/asset-manager.css").read_text(encoding="utf-8")
animation_speed_html_text = (ROOT / "system/control-center/static/index.html").read_text(encoding="utf-8")
for required in [
    "animation-speed-profile",
    "animation-speed-rule-grid",
    "animation-speed-rule",
    "Gameplay stat",
    "Stat units for +1% playback",
    "Playback formula",
    "Scales independently from Combat Idle",
]:
    if required not in animation_speed_ui_text and required not in animation_speed_css_text:
        err(f"m40 Animation Speed grouped UI missing {required}")
for required in ["each animation block is configured independently", "Stat units for +1% playback"]:
    if required not in animation_speed_html_text:
        err(f"m40 Animation Speed help copy missing {required}")


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
for required in ['id="nav-locations"', 'id="locations-view"', 'location-assets.css?v=1', 'locations.js?v=1']:
    if required not in index_m35_text:
        err(f"m41 Asset Manager Locations section missing {required}")
for required in [
    'path == "/api/locations"',
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
for required in ['require(script.Parent.modules.LocationCommands)', 'data.command == "location-authoring"', 'model bridge v22']:
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
    if category_ids != ["tree", "bush", "rock", "light", "fence", "decoration"]:
        err("m46 Location Assets categories must be tree/bush/rock/light/fence/decoration in canonical order")

location_asset_store_text = location_asset_store_path.read_text(encoding="utf-8") if location_asset_store_path.is_file() else ""
for required in [
    "class LocationAssetStore",
    'CATEGORIES = ("tree", "bush", "rock", "light", "fence", "decoration")',
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
    'deco-assets.css?v=3',
    'deco-assets.js?v=3',
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
    'descendant.TextureID = uri',
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
    'local CATEGORY_ORDER = { "tree", "bush", "rock", "light", "fence", "decoration" }',
]:
    if required not in deco_manager_text:
        err(f"m43 DecoManager missing {required}")

for required in [
    'require(script.Parent.modules.DecoManager)',
    'DecoManager.new({',
    'model bridge v22',
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
if "model bridge v22" not in studio_plugin_text:
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
    'reuse registered texture',
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
    'local CATEGORY_ORDER = { "tree", "bush", "rock", "light", "fence", "decoration" }',
    'local row = math.floor((index - 1) / 3)',
]:
    if required not in deco_manager_text:
        err(f"m46 DecoManager Decorations category missing {required}")
if 'decoration = "Decorations"' not in deco_placement_text:
    err("m46 DecoPlacement Decorations folder mapping is missing")
if "model bridge v22" not in studio_plugin_text:
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
if "model bridge v22" not in studio_plugin_text:
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
if "model bridge v22" not in studio_plugin_text:
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
for required in [
    'WeaponEnvironmentCollision.Query(previousVolume, volume)',
    'activeEnvironmentBlocked[player] = true',
    'activeDamageWindows[player] = nil',
    'WeaponBounceService.Publish(player, {',
    'LastAttackBounced',
]:
    if required not in attack_service_text:
        err(f"m50 AttackService environment-bounce integration missing {required}")
if attack_service_text.find('WeaponEnvironmentCollision.Query(previousVolume, volume)') > attack_service_text.find('hitCount += applyDamageInVolume', attack_service_text.find('local function applyAnimatedWeaponSweep')):
    err("m50 environment collision must resolve before damage in each weapon sweep substep")

upper_composer_text = (ROOT / "src/client/character/animation/AttackUpperBodyComposer.luau").read_text(encoding="utf-8")
character_animation_text = (ROOT / "src/client/character/animation/CharacterAnimationController.luau").read_text(encoding="utf-8")
attack_controller_text = (ROOT / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
client_init_text = (ROOT / "src/client/init.client.luau").read_text(encoding="utf-8")
server_init_text = (ROOT / "src/server/init.server.luau").read_text(encoding="utf-8")
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
if "model bridge v22" not in studio_plugin_text:
    err("m51 Studio plugin version marker is stale")
install_plugin_text = (ROOT / "system/studio-plugin/install.ps1").read_text(encoding="utf-8")
if "model bridge v22" not in install_plugin_text:
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
    "replacing an owned texture publishes a new Roblox Image Asset ID",
    "texture ${published.texture_asset_id || '—'}",
]:
    if required not in (index_m43_text + deco_assets_js_text):
        err(f"m51 Location Assets UI publication identity missing {required}")
for required in ["Game1DecoAssetSlug", "part.TextureID = uri", "RefreshTextures"]:
    if required not in deco_placed_sync_text:
        err(f"m51 DecoManager placed-texture sync missing {required}")
for required in ["DecoPlacedAssetSync.RefreshTextures", "Refresh Deco Asset Textures"]:
    if required not in deco_manager_text:
        err(f"m51 DecoManager registry refresh integration missing {required}")
if '"DecoPlacedAssetSync"' not in plugin_project_text:
    err("m51 Studio plugin project is missing DecoPlacedAssetSync")
for required in ["textureAssetId", "part.TextureID = uri", "ApplyModel", "ApplyPart"]:
    if required not in environment_visuals_text:
        err(f"m51 runtime environment texture hydration missing {required}")
for required in ["EnvironmentAssetVisuals.ApplyModel", "EnvironmentAssetVisuals.ApplyPart"]:
    if required not in environment_asset_service_text:
        err(f"m51 EnvironmentAssetService visual hydration missing {required}")


# m52 Location Assets: source-only canonical storage. The one-off Location
# Asset migration was retired by m53 after the project-wide source-only
# migration became authoritative.
for required in [
    "model_path TEXT NOT NULL DEFAULT ''",
    "texture_path TEXT NOT NULL DEFAULT ''",
    'self.root / "assets/source/location-assets"',
]:
    if required not in location_asset_store_text:
        err(f"m52 source-only LocationAssetStore missing {required}")
for forbidden in [
    "assets/prepared/location-assets",
    "model_source_path",
    "model_prepared_path",
    "texture_source_path",
    "texture_prepared_path",
]:
    if forbidden in location_asset_store_text:
        err(f"m52 active LocationAssetStore still contains legacy storage field/path {forbidden}")

if location_asset_manifest_path.is_file():
    location_asset_manifest = json.loads(location_asset_manifest_path.read_text(encoding="utf-8"))
    if location_asset_manifest.get("schemaVersion") != 4:
        err("m52 Location Asset manifest schema must be 4")
    for row in location_asset_manifest.get("items") or []:
        if not str(row.get("model_path") or "").startswith("assets/source/location-assets/"):
            err(f"m52 Location Asset model path is not canonical source-only: {row.get('slug')}")
        if not str(row.get("texture_reference_slug") or "") and not str(row.get("texture_path") or "").startswith("assets/source/location-assets/"):
            err(f"m52 owned Location Asset texture path is not canonical source-only: {row.get('slug')}")
        for legacy_field in ("model_source_path", "model_prepared_path", "texture_source_path", "texture_prepared_path"):
            if legacy_field in row:
                err(f"m52 manifest still exports legacy field {legacy_field}: {row.get('slug')}")

if "row.texture_path" not in deco_assets_js_text or "row.texture_source_path" in deco_assets_js_text:
    err("m52 Location Assets UI must use source-only texture_path")

# m53 project-wide source-only storage. Active asset bytes live only in
# assets/source. Compatibility DB columns may remain for old query shapes,
# but both aliases must resolve to the same canonical source path and no active
# subsystem may recreate assets/prepared.
source_only_module = ROOT / "system/control-center/source_only_assets.py"
source_only_text = source_only_module.read_text(encoding="utf-8") if source_only_module.is_file() else ""
if not source_only_module.is_file():
    err("m53 project-wide source-only migration module is missing")
if (ROOT / "system/control-center/location_asset_source_only_migration.py").exists():
    err("m53 obsolete Location Asset-only source migration must be removed")
for required in [
    "def migrate_source_only_assets",
    '"game1-source-only-assets-v1"',
    '"assets/prepared/"',
    '"assets/source/"',
    '"prepared-wins"',
    '"source-wins"',
    '"prepared-before"',
]:
    if required not in source_only_text:
        err(f"m53 source-only migration contract missing {required}")
if 'migrate_source_only_assets(ROOT, ROOT / ".control-center" / "game1.db")' not in host_agent_text:
    err("m53 Control Center startup does not run source-only migration before stores")
migrate_text = (ROOT / "system/control-center/migrate.py").read_text(encoding="utf-8")
if 'migrate_source_only_assets(ROOT, ROOT / ".control-center" / "game1.db")' not in migrate_text:
    err("m53 migrate.py does not run project-wide source-only migration")

legacy_prepared_root = ROOT / "assets/prepared"
if legacy_prepared_root.exists():
    legacy_files = [path for path in legacy_prepared_root.rglob("*") if path.is_file()]
    if legacy_files:
        err(f"m53 source-only migration incomplete: assets/prepared still has {len(legacy_files)} file(s)")
    else:
        err("m53 source-only migration incomplete: empty assets/prepared tree still exists")

active_manifest_stale = []
for manifest_path in (ROOT / "assets/manifests").glob("*.json"):
    if "assets/prepared/" in manifest_path.read_text(encoding="utf-8", errors="replace"):
        active_manifest_stale.append(manifest_path.name)
if active_manifest_stale:
    err("m53 manifests still reference assets/prepared: " + ", ".join(sorted(active_manifest_stale)))

for active_store in [
    ROOT / "system/control-center/character_store.py",
    ROOT / "system/control-center/character_core/identity.py",
    ROOT / "system/control-center/animation_core/storage.py",
    ROOT / "system/control-center/weapon_store.py",
    ROOT / "system/control-center/monster_store.py",
    ROOT / "system/control-center/monster_animation_store.py",
]:
    active_text = active_store.read_text(encoding="utf-8")
    if 'self.root / "assets/prepared' in active_text or 'self.root / "assets" / "prepared"' in active_text:
        err(f"m53 active store can still create assets/prepared: {active_store.relative_to(ROOT)}")

if "<b>prepared</b>" in character_js_text or "source/prepared copies" in ui:
    err("m53 Asset Manager still exposes the removed Source/Prepared dual-storage UI")

# Validate compatibility aliases in the live SQLite DB. They remain only so old
# query shapes keep working; both values must point at the exact same assets/source file.
import sqlite3 as _sqlite3_m53
_db_m53 = ROOT / ".control-center/game1.db"
if _db_m53.is_file():
    _con_m53 = _sqlite3_m53.connect(_db_m53)
    _con_m53.row_factory = _sqlite3_m53.Row
    _pairs_m53 = [
        ("characters", "source_path", "prepared_path"),
        ("animation_clips", "source_path", "prepared_path"),
        ("weapons", "model_source_path", "model_prepared_path"),
        ("weapon_textures", "source_path", "prepared_path"),
        ("monsters", "model_source_path", "model_prepared_path"),
        ("monster_textures", "source_path", "prepared_path"),
        ("monster_animation_clips", "source_path", "prepared_path"),
    ]
    _tables_m53 = {str(row[0]) for row in _con_m53.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for _table, _source_col, _prepared_col in _pairs_m53:
        if _table not in _tables_m53:
            continue
        _cols = {str(row[1]) for row in _con_m53.execute(f"PRAGMA table_info({_table})")}
        if not {_source_col, _prepared_col}.issubset(_cols):
            continue
        for _row in _con_m53.execute(f"SELECT {_source_col},{_prepared_col} FROM {_table}"):
            _source_value = str(_row[0] or "").replace("\\", "/")
            _prepared_value = str(_row[1] or "").replace("\\", "/")
            if _source_value != _prepared_value:
                err(f"m53 {_table} still has split Source/Prepared paths")
                break
            if _source_value and not _source_value.startswith("assets/source/"):
                err(f"m53 {_table} canonical path is outside assets/source: {_source_value}")
                break
    _con_m53.close()

if errors:
    print("verify failed")
    for item in errors:
        print(" -", item)
    sys.exit(1)

print("verify ok · game1 m53 project-wide source-only asset storage passed")
print("registered character archetypes:", len(archetypes))
print("active character archetype:", active_id or "none")
print("race pool: human")
print("gender pool: male, female")
print("canonical place: place/game1.rbxl")
