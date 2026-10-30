"""M167 read-only verification of characters domain contracts.

All diagnostics are emitted via the provided sink, at the original call site.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable


def check_character_manifest(
    ROOT: Path, err: Callable[[str], None]
) -> tuple:
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

    return archetypes, active_id


def check_character_rig(
    ROOT: Path, err: Callable[[str], None]
) -> tuple:
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

    return character_service_text, rig_text


def check_character_publication(
    ROOT: Path, err: Callable[[str], None], *, host_agent_text, plugin_text, archetypes
) -> tuple:
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
    publication_preparer_text = (publication_preparer.read_text(encoding="utf-8") + (ROOT / "system/asset-manager/model_publication.py").read_text(encoding="utf-8")) if publication_preparer.is_file() else ""
    bone_planner = ROOT / "system/asset-manager/bone_weight_survival.py"
    bone_planner_text = bone_planner.read_text(encoding="utf-8") if bone_planner.is_file() else ""
    for required in [
        "SURVIVAL_WEIGHT = 0.05",
        "MAX_INFLUENCES = 4",
    ]:
        if required not in bone_planner_text:
            err(f"shared publication bone-survival planner missing {required}")
    for required in [
        "plan_publication_weights",
        "ROBLOX_MAX_INFLUENCES = MAX_INFLUENCES",
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
    if "boneNames" not in plugin_text or 'validate_published_rig(result, row, kind="character")' not in host_agent_text or 'f"{label} stripped' not in host_agent_text:
        err("Studio character sync must report exact bones stripped by Roblox publication")
    return schema_text, ui, js, character_js_text


def check_character_identity(
    ROOT: Path, err: Callable[[str], None], *, schema_text, ui, host_agent_text, js_text
) -> None:
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




def check_character_starting_stats(
    ROOT: Path, err: Callable[[str], None], *, character_service_text, stats_service_text
) -> None:
    # m13+ starting stats.
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
