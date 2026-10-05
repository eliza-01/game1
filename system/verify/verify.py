from pathlib import Path
import json
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
if manifest.get("schemaVersion") != 4:
    err("character manifest schema must be 4; run python .\\system\\control-center\\migrate.py")
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
    "src/server/combat/SkeletonHitRegionResolver.luau",
    "src/server/dev/TrainingDummyService.luau",
    "src/client/character/MovementController.luau",
    "src/client/character/CameraController.luau",
    "src/client/character/PlayerStatusController.luau",
    "src/client/character/animation/AnimationResolver.luau",
    "src/client/character/animation/AnimationTrackCache.luau",
    "src/client/character/animation/CharacterAnimationController.luau",
    "src/client/combat/AttackController.luau",
    "src/client/combat/AimPoseController.luau",
    "src/shared/character/CharacterConfig.luau",
    "src/shared/character/CharacterMovementConfig.luau",
    "src/shared/character/CharacterRegistry.luau",
    "src/shared/character/CharacterAnimationRegistry.luau",
    "src/shared/character/CharacterStatsConfig.luau",
    "src/shared/combat/AttackConfig.luau",
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
if "math.max(0, math.floor(normalizedRawDamage - defense))" not in damage_text:
    err("damage formula contract missing")

attack_text = (ROOT / "src/server/combat/AttackService.luau").read_text(encoding="utf-8")
dummy_text = (ROOT / "src/server/dev/TrainingDummyService.luau").read_text(encoding="utf-8")
if "[game1][attack] hit" not in attack_text or "[game1][attack] miss" not in attack_text:
    err("attack smoke-test logging contract missing")
if "EntityHitboxService.QueryBox" not in attack_text:
    err("attack service must refine melee candidates against virtual skeletal hit regions")
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
resolver_text = (ROOT / "src/server/combat/SkeletonHitRegionResolver.luau").read_text(encoding="utf-8")
for required in ["virtual_bone_regions", "QueryBox", "capsuleIntersectsBox", "TransformedBoneFrame", "SegmentRadius", "SemanticRole"]:
    if required not in hitbox_text + resolver_text:
        err(f"virtual skeleton hit-region runtime missing {required}")
if "RunService.Heartbeat" in hitbox_text or 'Instance.new("Part")' in hitbox_text:
    err("combat hit regions must be virtual queries, not Heartbeat-following replicated Parts")
for required in ['"upper_arm"', '"shin"', '"forehead"']:
    if required not in resolver_text:
        err(f"semantic skeleton resolver regression: missing {required}")

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
for required in ["resolveSkeletonUp", "spineRank", "isFootBone", "PivotTo", "ImportedRigRootWeld", "Game1GeneratedCharacterRoot"]:
    if required not in template_text:
        err(f"game1 Studio character template module missing {required}")
if "CFrame.Angles(0, 0, math.rad(90))" in template_text or "CFrame.Angles(math.rad(90)" in template_text:
    err("character template orientation must be skeleton-derived, not a hard-coded 90-degree fix")
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
if "update it through the studio animation-version bridge" not in animation_store_text:
    err("changed animation assets must preserve their permanent id")

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
for required in ["MovementState", "PlayAction", "AnimationResolvedClip", "AnimationTrackCache"]:
    if required not in controller_runtime:
        err(f"character animation controller missing {required}")
client_init_text = (ROOT / "src/client/init.client.luau").read_text(encoding="utf-8")
if "CharacterAnimationController.Start()" not in client_init_text:
    err("character animation controller is not started by the client runtime")
attack_controller_text = (ROOT / "src/client/combat/AttackController.luau").read_text(encoding="utf-8")
if 'animationController.PlayAction("attack")' not in attack_controller_text:
    err("combat attack input is not connected to the semantic attack animation slot")
for required in ["BeginAimFacingCompensation", "TorsoYawLimit", "aimPoseController.BeginAttack"]:
    if required not in attack_controller_text:
        err(f"robloxlineage attack/aim integration missing {required}")
aim_pose_text = (ROOT / "src/client/combat/AimPoseController.luau").read_text(encoding="utf-8")
for required in ["RunService.PreSimulation", "spine.001", "AimTorsoYawDegrees", "bone.Transform = delta * bone.Transform", "ViewportPointToRay", "Game1AimReticle"]:
    if required not in aim_pose_text:
        err(f"procedural torso aim controller missing {required}")
movement_runtime = (ROOT / "src/client/character/MovementController.luau").read_text(encoding="utf-8")
for required in ["BeginAimFacingCompensation", "UpdateAimFacingCompensation", "applyAimFacingCompensation"]:
    if required not in movement_runtime:
        err(f"movement aim-facing compensation missing {required}")
if "AimPoseController.Start()" not in client_init_text:
    err("procedural torso aim controller is not started by the client runtime")
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
if weapon_manifest.get("schemaVersion") != 1 or weapon_manifest.get("project") != "game1":
    err("weapon manifest must be game1 schema 1")
weapon_options = weapon_manifest.get("options") or {}
if weapon_options.get("weaponTypes") != ["1hs", "2hs", "bow"]:
    err("weapon type pool must be 1hs, 2hs, bow")
if weapon_options.get("rarities") != ["common", "uncommon", "rare", "mythical", "legendary", "immortal"]:
    err("weapon rarity pool must be common through immortal")

weapon_store_path = ROOT / "system/control-center/weapon_store.py"
weapon_store_text = weapon_store_path.read_text(encoding="utf-8") if weapon_store_path.is_file() else ""
for required in [
    "class WeaponStore",
    "def slugify_english",
    'WEAPON_TYPES = ("1hs", "2hs", "bow")',
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
if "DefaultRunStat = 50" not in movement_config_text or "currentRunSpeed" not in movement_config_text:
    err("movement runtime must derive Roblox speed from RunSpeed=50 baseline")
if 'character:GetAttribute("AttackSpeed")' not in attack_text:
    err("server attack cooldown does not use AttackSpeed")
if 'character:GetAttribute("AttackSpeed")' not in attack_controller_text:
    err("client attack debounce does not use AttackSpeed")

if 'id="nav-weapons"' not in ui or 'id="register-weapon"' not in ui or 'id="weapon-stat-attack-speed"' not in ui:
    err("asset manager weapon registration section is missing")
if 'id="weapon-test-loadout"' in ui or 'id="save-weapon-test-loadout"' in ui:
    err("studio test loadout must not live in the web asset manager")
weapon_js_path = ROOT / "system/control-center/static/weapon-assets.js"
weapon_js_text = weapon_js_path.read_text(encoding="utf-8") if weapon_js_path.is_file() else ""
for required in ["weaponSlugify", "weaponRegister", "weaponPublish", "weaponSync", "weaponActivate"]:
    if required not in weapon_js_text:
        err(f"asset manager weapon ui missing {required}")
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

if errors:
    print("verify failed")
    for item in errors:
        print(" -", item)
    sys.exit(1)

print("verify ok · game1 m6.2 archetype safety + Studio-native test loadout contracts passed")
print("registered character archetypes:", len(archetypes))
print("active character archetype:", active_id or "none")
print("race pool: human")
print("gender pool: male, female")
print("canonical place: place/game1.rbxl")
