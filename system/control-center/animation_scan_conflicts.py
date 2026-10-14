"""Validate animation scan coordinates before writing to registries.

Multiple filenames/aliases can describe the same animation slot. A folder
scan must not decide which source is authoritative, especially after Remove:
ambiguous files remain unassigned until the author resolves the collision.
This pure module is shared by the NPC and Monster scan paths.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path


def partition_scan_candidates(candidates: list[tuple[Path, dict]], *, kind: str) -> tuple[list[tuple[Path, dict]], list[dict]]:
    """Return unambiguous candidates and an explicit per-file conflict report.

    Coordinate identity includes the weapon type, semantic state and variant.
    Conflict groups do not enter the transaction at all: no surviving clip
    can be overwritten by an arbitrary filename or scan ordering.
    """
    if kind not in {"npc", "monster"}:
        raise ValueError(f"unknown animation scan actor kind: {kind}")

    grouped: dict[tuple[str, str, int], list[tuple[Path, dict]]] = defaultdict(list)
    for path, binding in candidates:
        coordinate = (str(binding.get("weaponSet") or ""), str(binding["slot"]), int(binding["variant"]))
        grouped[coordinate].append((path, binding))

    accepted: list[tuple[Path, dict]] = []
    unassigned: list[dict] = []
    for (weapon_set, slot, variant), entries in grouped.items():
        if len(entries) == 1:
            accepted.extend(entries)
            continue
        names = ", ".join(sorted(str(path) for path, _ in entries))
        label = f"{weapon_set} / {slot} / {variant:02d}" if weapon_set else f"{slot} / {variant:02d}"
        reason = (
            f"{kind.upper()} animation scan conflict: {len(entries)} files map to {label}: {names}. "
            "Keep only one file for this slot in the scan folder, or rename it to another valid state/variant; "
            "the conflicting files were not registered."
        )
        for path, _ in entries:
            unassigned.append({"path": str(path), "filename": path.name, "reason": reason})
    return accepted, unassigned
