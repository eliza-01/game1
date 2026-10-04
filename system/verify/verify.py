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
if manifest.get("schemaVersion") != 3:
    err("character manifest schema must be 3; run python .\\system\\control-center\\migrate.py")
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
if "CombatPoseHitboxes" not in attack_text:
    err("attack service must prefer pose-following skeletal hitboxes")
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
for required in ["CombatPoseHitboxes", "Game1PoseHitbox", "TransformedBoneFrame", "SegmentRadius"]:
    if required not in hitbox_text + resolver_text:
        err(f"skeleton hitbox runtime missing {required}")

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
for required in ["project_settings", "character_publications", "race text", "gender text", "skeleton_signature"]:
    if required not in schema_text:
        err(f"control center schema missing {required}")

store_text = (ROOT / "system/control-center/character_store.py").read_text(encoding="utf-8")
if 'RACES = ("human",)' not in store_text or 'GENDERS = ("male", "female")' not in store_text:
    err("character identity pools are missing")
if "analyze_character_fbx" not in store_text:
    err("character armature analysis is not wired into registration")
if "prepare_character_fbx" not in store_text:
    err("character FBX preparation is not wired into registration")
if "create_model_asset" not in store_text or "update_model_asset" not in store_text:
    err("character model publication contract is missing")
if 'src/shared/character/CharacterRegistry.luau' not in store_text:
    err("character registry generator must target the character shared domain")

ui = (ROOT / "system/control-center/static/index.html").read_text(encoding="utf-8")
css = ROOT / "system/control-center/static/asset-manager.css"
js = ROOT / "system/control-center/static/character-assets.js"
if not css.is_file() or not js.is_file():
    err("character asset manager css/js files are missing")
if 'id="race"' not in ui or 'id="gender"' not in ui or 'id="publish-character"' not in ui:
    err("character asset manager race/gender/publication controls are missing")

analyzer = ROOT / "system/asset-manager/analyze_character_fbx.py"
if not analyzer.is_file() or "FBX contains no armature" not in analyzer.read_text(encoding="utf-8"):
    err("deterministic character fbx armature analyzer is missing")
analysis_text = (ROOT / "system/control-center/character_analysis.py").read_text(encoding="utf-8")
if "shutil.copy2(source, output)" not in analysis_text or "preserve-source-bytes" not in analysis_text:
    err("character prepared FBX must preserve authored source bytes")
preparer = ROOT / "system/asset-manager/prepare_character_fbx.py"
if preparer.is_file() and "transform_apply" in preparer.read_text(encoding="utf-8"):
    err("character FBX preparer must not rebake authored rotation/scale")

# m5.1 character animation contract
animation_manifest_path = ROOT / "assets/manifests/character-animations.json"
if not animation_manifest_path.is_file():
    err(r"character animation manifest is missing; run python .\system\control-center\migrate.py")
    animation_manifest = {}
else:
    animation_manifest = json.loads(animation_manifest_path.read_text(encoding="utf-8"))
if animation_manifest.get("schemaVersion") != 2 or animation_manifest.get("project") != "game1":
    err("character animation manifest must be game1 schema 2")
if animation_manifest.get("weaponSets") != ["hands", "1hs", "bow"]:
    err("m5.1 character animation weapon sets must be hands, 1hs and bow")

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
    'WEAPON_SETS = ("hands", "1hs", "bow")',
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

if errors:
    print("verify failed")
    for item in errors:
        print(" -", item)
    sys.exit(1)

print("verify ok · game1 m5.2 archetype edit + character animation contracts passed")
print("registered character archetypes:", len(archetypes))
print("active character archetype:", active_id or "none")
print("race pool: human")
print("gender pool: male, female")
print("canonical place: place/game1.rbxl")
