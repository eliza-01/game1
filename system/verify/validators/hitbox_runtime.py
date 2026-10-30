"""Read-only M99 hitbox delegation, geometry and head resolver contracts (M170)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable


def check_hitbox_runtime(ROOT: Path, err: Callable[[str], None]):
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

    return hitbox_implementation_text
