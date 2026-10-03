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
    "src/client/combat/AttackController.luau",
    "src/shared/character/CharacterConfig.luau",
    "src/shared/character/CharacterMovementConfig.luau",
    "src/shared/character/CharacterRegistry.luau",
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

if errors:
    print("verify failed")
    for item in errors:
        print(" -", item)
    sys.exit(1)

print("verify ok · game1 m4.3 canonical character template contracts passed")
print("registered character archetypes:", len(archetypes))
print("active character archetype:", active_id or "none")
print("race pool: human")
print("gender pool: male, female")
print("canonical place: place/game1.rbxl")
