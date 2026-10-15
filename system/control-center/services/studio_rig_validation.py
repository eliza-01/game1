"""Reusable authored-skeleton verification for published character and NPC rigs."""
import json


def validate_published_rig(result: dict, row: dict, *, kind: str) -> None:
    """Refuse an incomplete model before it can replace the authored Studio rig.

    `kind` is `character` or `monster` (NPCs use the monster rig pipeline).
    Error messages are part of the Asset Manager compatibility contract.
    """
    if kind not in ("character", "monster"):
        raise ValueError(f"unknown rig validation kind: {kind}")

    stats = result.get("rigStats") or {}
    if int(stats.get("baseParts") or 0) <= 0 or int(stats.get("bones") or 0) + int(stats.get("motor6Ds") or 0) <= 0:
        if kind == "character":
            raise ValueError("Studio loaded a character asset without articulated BasePart geometry")
        raise ValueError("Studio loaded a monster asset without an articulated rig")

    try:
        expected_analysis = json.loads(str(row.get("skeleton_json") or "{}"))
    except Exception:
        expected_analysis = {}
    expected_names = {
        str(item.get("name") or "")
        for item in (expected_analysis.get("bones") or [])
        if str(item.get("name") or "")
    }
    actual_names = {str(name) for name in (stats.get("boneNames") or []) if str(name)}
    label = "Roblox publication" if kind == "character" else "Roblox monster publication"
    if expected_names and actual_names:
        missing = sorted(expected_names - actual_names, key=str.casefold)
        if missing:
            preview = ", ".join(missing[:20])
            suffix = " …" if len(missing) > 20 else ""
            raise ValueError(
                f"{label} stripped {len(missing)} of {len(expected_names)} registered bones: {preview}{suffix}"
            )
    elif expected_names and int(stats.get("bones") or 0) < len(expected_names):
        raise ValueError(
            f"{label} returned only {int(stats.get('bones') or 0)} of {len(expected_names)} registered bones"
        )
