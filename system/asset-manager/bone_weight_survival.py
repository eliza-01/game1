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


def plan_publication_weights(bone_heads: dict[str, tuple], vertices: list[dict]) -> dict:
    """Mutates vertices' 'weights' only; returns a verifiable publication report.

    A vertex has ``position`` and ``weights`` and may have ``mesh`` / ``index``.
    Pre-existing weights are not copied into new helper geometry, and no new bones
    are generated. Fails closed if there is not a safe vertex for a given bone.
    """
    if not bone_heads or not vertices:
        raise ValueError("publication requires an armature and skinned vertices")
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
        retained = _normalize(dict(ordered[:MAX_INFLUENCES]))
        if len(active) > MAX_INFLUENCES:
            pruned_vertices += 1
        vertex['weights'] = retained

    def coverage():
        result = {name: 0 for name in names}
        for vertex in vertices:
            for name, value in vertex['weights'].items():
                if value >= SURVIVAL_WEIGHT:
                    result[name] += 1
        return result

    counts = coverage()
    anchors = []
    for name in sorted(names):
        if counts[name]:
            continue
        candidates = []
        for index, vertex in enumerate(vertices):
            weights = vertex['weights']
            if name in weights or len(weights) < MAX_INFLUENCES:
                evict = None
            else:
                choices = [
                    (value, other) for other, value in weights.items()
                    if value < SURVIVAL_WEIGHT or counts[other] > 1
                ]
                if not choices:
                    continue
                _, evict = min(choices)
            # Preserve existing anatomical weighting where possible, avoid
            # evicting an already unique anchor, then prefer nearby vertices.
            score = (
                0 if name in weights else 1,
                0 if evict is None else 1,
                _distance_sq(vertex['position'], bone_heads[name]),
                float(weights.get(evict, 0.0)) if evict else 0.0,
                index,
            )
            candidates.append((score, index, evict))
        if not candidates:
            raise ValueError(f"no safe <=4-influence vertex to preserve bone {name!r}")
        _, index, evict = min(candidates)
        target = vertices[index]
        weights = target['weights']
        for other, value in weights.items():
            if value >= SURVIVAL_WEIGHT:
                counts[other] -= 1
        if evict is not None:
            del weights[evict]
        weights.pop(name, None)
        remainder = sum(weights.values())
        if remainder > 0:
            weights = {key: (value / remainder) * (1 - ANCHOR_WEIGHT) for key, value in weights.items()}
        else:
            weights = {}
        weights[name] = ANCHOR_WEIGHT if weights else 1.0
        target['weights'] = weights
        for other, value in weights.items():
            if value >= SURVIVAL_WEIGHT:
                counts[other] += 1
        anchors.append({'bone': name, 'mesh': target.get('mesh'), 'vertex': target.get('index', index)})
    missing = sorted(name for name, count in coverage().items() if count <= 0)
    if missing:
        raise ValueError("publication bones still lack >=0.05 influence: " + ", ".join(missing))
    if any(len(vertex['weights']) > MAX_INFLUENCES for vertex in vertices):
        raise AssertionError("publication exceeded four influences per vertex")
    return {
        'verticesOverFourBefore': over_limit_before,
        'verticesOverFourAfter': 0,
        'prunedVertices': pruned_vertices,
        'patchedBoneCount': len(anchors),
        'patchedBones': anchors,
        'survivingBoneCount': len(names),
    }
