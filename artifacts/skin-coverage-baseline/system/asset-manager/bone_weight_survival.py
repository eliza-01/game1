"""Deterministic four-influence FBX publication planner (no Blender dependency).

Only a temporary publication copy is changed; canonical FBX/skin data are not.
Each authored bone must retain at least one nontrivial vertex influence after
Roblox's four-influences-per-vertex cap, including nondeforming helper bones.
"""

from __future__ import annotations

from math import isfinite

MAX_INFLUENCES = 4
SURVIVAL_WEIGHT = 0.05
ANCHOR_WEIGHT = 0.055  # survives FBX float rounding and normalization


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return {}
    return {name: value / total for name, value in weights.items() if value > 0}


def _distance_sq(a, b):
    return sum((float(x) - float(y)) ** 2 for x, y in zip(a, b))


def plan_publication_weights(
    bone_heads: dict[str, tuple], vertices: list[dict], *,
    min_covered_vertices: int = 1,
    minimum_weight: float = SURVIVAL_WEIGHT,
    anchor_weight: float = ANCHOR_WEIGHT,
) -> dict:
    """Normalize skin weights and keep every bone above an explicit coverage policy.

    All model domains use these defaults. Coverage settings are algorithm inputs,
    not asset-name exceptions; no domain adapter overrides them.
    """
    if not bone_heads or not vertices:
        raise ValueError("publication requires an armature and skinned vertices")
    if (min_covered_vertices < 1 or not 0 < minimum_weight <= anchor_weight <= 1
            or min_covered_vertices > len(vertices)):
        raise ValueError("invalid publication bone coverage policy")
    names = set(bone_heads)
    over_limit_before = 0
    pruned_vertices = 0
    for vertex in vertices:
        raw = vertex['weights']
        active = {
            name: float(value) for name, value in raw.items()
            if name in names and isfinite(float(value)) and float(value) > 0
        }
        ordered = sorted(active.items(), key=lambda item: (-item[1], item[0]))
        if len(ordered) > MAX_INFLUENCES:
            over_limit_before += 1
            pruned_vertices += 1
        vertex['weights'] = _normalize(dict(ordered[:MAX_INFLUENCES]))

    def coverage():
        counts = {name: 0 for name in names}
        for vertex in vertices:
            for name, weight in vertex['weights'].items():
                if weight >= minimum_weight:
                    counts[name] += 1
        return counts

    counts = coverage()
    anchors = []
    completed = set()
    for name in sorted(names):
        while counts[name] < min_covered_vertices:
            candidates = []
            for index, vertex in enumerate(vertices):
                weights = vertex['weights']
                if weights.get(name, 0.0) >= minimum_weight:
                    continue  # Each bone must be backed by distinct vertices.
                if name in weights or len(weights) < MAX_INFLUENCES:
                    evictions = [None]
                else:
                    evictions = [other for other in weights if other != name]
                for evict in evictions:
                    # Simulate the replacement before choosing a vertex: do not
                    # destroy the last surviving anchor of another bone, or an
                    # already-completed bone's required redundant coverage.
                    kept = {other: weight for other, weight in weights.items()
                            if other != evict and other != name}
                    remainder = sum(kept.values())
                    candidate = {other: weight / remainder * (1 - anchor_weight)
                                 for other, weight in kept.items()} if remainder else {}
                    candidate[name] = anchor_weight if candidate else 1.0
                    endangered = any(
                        value >= minimum_weight and candidate.get(other, 0.0) < minimum_weight
                        and counts[other] <= (min_covered_vertices if other in completed else 1)
                        for other, value in weights.items() if other != name
                    )
                    if endangered:
                        continue
                    score = (
                        0 if name in weights else 1,
                        0 if evict is None else 1,
                        _distance_sq(vertex['position'], bone_heads[name]),
                        float(weights.get(evict, 0.0)) if evict else 0.0,
                        index,
                    )
                    candidates.append((score, index, candidate))
            if not candidates:
                raise ValueError(f"no safe <=4-influence vertex to preserve bone {name!r} "
                                 f"on {min_covered_vertices} vertices")
            _, index, replacement = min(candidates, key=lambda item: item[0])
            old = vertices[index]['weights']
            for other, weight in old.items():
                if weight >= minimum_weight:
                    counts[other] -= 1
            vertices[index]['weights'] = replacement
            for other, weight in replacement.items():
                if weight >= minimum_weight:
                    counts[other] += 1
            anchors.append({'bone': name, 'mesh': vertices[index].get('mesh'),
                            'vertex': vertices[index].get('index', index)})
        completed.add(name)

    missing = sorted(name for name, count in coverage().items()
                     if count < min_covered_vertices)
    if missing:
        raise ValueError("publication bones lack required vertex coverage: " + ", ".join(missing))
    if any(len(vertex['weights']) > MAX_INFLUENCES for vertex in vertices):
        raise AssertionError("publication exceeded four influences per vertex")
    return {
        'verticesOverFourBefore': over_limit_before,
        'verticesOverFourAfter': 0,
        'prunedVertices': pruned_vertices,
        'patchedBoneCount': len(anchors),
        'patchedBones': anchors,
        'survivingBoneCount': len(names),
        'minimumInfluence': minimum_weight,
        'minimumVerticesPerBone': min_covered_vertices,
    }
