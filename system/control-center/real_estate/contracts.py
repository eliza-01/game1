"""Real Estate naming, prices and mesh/armature contracts."""
from __future__ import annotations

import re

from .rig_features import feature_warnings

HOUSE_NAME = re.compile(r"^(?P<kind>[a-z][a-z0-9_]*)_level(?P<level>[1-9][0-9]*)_(?P<variant>[0-9]+)$")
SLUG = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
REQUIRED_MESH = "house"


def present_parts(analysis: dict) -> tuple[str, ...]:
    """All authored meshes, always with house first and stable publication order.

    A removed mesh is not revived by stale publication records. Part names are
    authored FBX identities, not a fixed house/door enum.
    """
    meshes = analysis.get("meshes", []) if isinstance(analysis, dict) else []
    names = [item.get("name") for item in meshes if isinstance(item, dict)
             and isinstance(item.get("name"), str)]
    return tuple(sorted(names, key=lambda name: (name != REQUIRED_MESH, name.casefold(), name)))



def parse_name(filename: str) -> dict:
    name = str(filename).rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".fbx")
    match = HOUSE_NAME.fullmatch(name.lower())
    if not match:
        raise ValueError("house FBX name must follow house_level1_01 (type_levelN_variant)")
    return {"houseType": match["kind"], "level": int(match["level"]), "variant": match["variant"]}


def identity(payload: dict) -> dict:
    kind = str(payload.get("houseType") or "house").strip().lower()
    if not SLUG.fullmatch(kind):
        raise ValueError("house type must be lowercase latin letters, digits or underscore")
    level = _positive_int(payload.get("level", 1), "level")
    variant_raw = str(payload.get("variant") or "01").strip()
    if not variant_raw.isdigit() or int(variant_raw) < 1 or len(variant_raw) > 8:
        raise ValueError("variant must be a positive number")
    variant = variant_raw.zfill(2)
    slug = f"{kind}_level{level}_{variant}"
    if len(slug) > 64:
        raise ValueError("house identity is too long")
    return {"slug": slug, "houseType": kind, "level": level, "variant": variant}


def _positive_int(raw, label: str) -> int:
    if isinstance(raw, bool) or not re.fullmatch(r"[0-9]+", str(raw).strip()):
        raise ValueError(f"{label} must be a positive integer")
    value = int(raw)
    if value < 1 or value > 2_147_483_647:
        raise ValueError(f"{label} must be between 1 and 2147483647")
    return value


def prices(payload: dict) -> dict:
    return {key: _positive_int(payload.get(key, 1), key) for key in ("purchasePrice", "minLevel", "salePrice")}


def warnings_for_analysis(value: dict) -> list[dict]:
    """Report missing authoring features without implying they are all blockers.

    House mesh/house_armature are required by validate_analysis; the same
    issues are reported here for UIs that inspect partial analysis results.
    """
    meshes = {part.get('name'): part for part in value.get('meshes', [])
              if isinstance(part, dict) and isinstance(part.get('name'), str)}
    house = meshes.get('house')
    door = meshes.get('door')
    warnings = []

    def warn(part, code, message):
        warnings.append({'part': part, 'code': code, 'message': message})

    if house is None:
        warn('house', 'missing_house', 'Required mesh house is missing. Add it before registration.')
    if house is None or house.get('armature', '').casefold() != 'house_armature':
        warn('house', 'missing_house_armature',
             'Required house_armature is missing or not assigned to mesh house.')
    if door is None:
        warn('door', 'missing_door', 'Optional mesh door is missing. Houses without doors are supported.')
    elif not door.get('armature'):
        warn('door', 'missing_door_armature', 'door is present without a linked door_armature (optional).')
    # New standard: sockets describe attachment/interaction sites; a missing
    # socket is not itself proof that an optional feature is authored. In a
    # hinge-enabled door, however, hierarchy and rigid skinning must agree.
    warnings.extend(feature_warnings(value))

    for name in value.get('unassignedArmatures', []):
        warn('', 'unassigned_armature',
             f"Armature {name} is not linked to a mesh and will not be published.")

    owners = {}
    for part in value.get('meshes', []):
        if isinstance(part, dict) and part.get('armature'):
            owners.setdefault(part['armature'], []).append(part.get('name'))
    for rig, parts in owners.items():
        if len(parts) > 1:
            warn(', '.join(parts), 'shared_armature',
                 f"Meshes {', '.join(parts)} share armature {rig}. Each will receive an independent copy of its bones on publication.")
    return warnings


def validate_analysis(value: dict) -> dict:
    meshes = value.get("meshes") if isinstance(value, dict) else None
    if not isinstance(meshes, list) or not meshes or not all(isinstance(item, dict) for item in meshes):
        raise ValueError("FBX must contain a Mesh named house (other meshes may have any names).")
    names = [item.get("name") for item in meshes]
    if any(not isinstance(name, str) or not name.strip() or name in (".", "..")
           or "/" in name or "\\" in name for name in names):
        raise ValueError("FBX contains an invalid mesh name (empty or path separator).")
    if len(set(name.casefold() for name in names)) != len(names):
        raise ValueError("FBX mesh names must be unique, including letter case.")
    if "house" not in names:
        raise ValueError("Required mesh house is missing. Add mesh house before registering this FBX.")
    house = next(item for item in meshes if item['name'] == 'house')
    if str(house.get('armature') or '').casefold() != 'house_armature':
        raise ValueError("Required house_armature is missing or not assigned to mesh house. "
                         "Link an armature named house_armature to mesh house in Blender.")
    armatures = []
    for item in meshes:
        name = item["name"]
        armature = item.get("armature") or ""
        if not isinstance(armature, str):
            raise ValueError(f"{name}: armature name is invalid")
        if armature:
            armatures.append(armature)
        bones = item.get("bones")
        if not isinstance(bones, list):
            raise ValueError(f"{name}: cannot read bone list from FBX")
        names = [bone.get("name") if isinstance(bone, dict) else None for bone in bones]
        if len(names) != len(set(names)) or any(not isinstance(n, str) or not n for n in names):
            raise ValueError(f"{name}: bone names must be non-empty and unique")
        if int(item.get("vertices") or 0) < 3:
            raise ValueError(f"{name}: mesh has fewer than three vertices; check the FBX export")
    # Multiple meshes may reference one Blender armature. Each gets its own
    # exported Model Asset (and independent copy of the bones) in Studio.
    return value


def assert_skeleton_survived(expected: dict, actual: dict) -> None:
    validate_analysis(actual)
    if present_parts(expected) != present_parts(actual):
        raise ValueError("publication changed the Real Estate mesh list")
    for name in present_parts(expected):
        old = next(item for item in expected["meshes"] if item["name"] == name)
        new = next(item for item in actual["meshes"] if item["name"] == name)
        a = {b["name"]: b for b in old["bones"]}
        b = {bone["name"]: bone for bone in new["bones"]}
        if a.keys() != b.keys():
            raise ValueError(f"publication changed {name} bone set")
        for bone_name, before in a.items():
            after = b[bone_name]
            if before["parent"] != after["parent"]:
                raise ValueError(f"publication changed parent of {name}/{bone_name}")
            if len(before["matrixLocal"]) != len(after["matrixLocal"]) or any(
                abs(float(x) - float(y)) > 0.0001
                for x, y in zip(before["matrixLocal"], after["matrixLocal"])
            ):
                raise ValueError(f"publication changed rest pose of {name}/{bone_name}")
            if bone_name not in new.get("influencedBones", []):
                raise ValueError(f"publication did not preserve weighted bone {name}/{bone_name}")


def assert_rig_survived(expected: dict, actual: dict, part: str) -> None:
    """Reject missing/cross-import bones, different parents and rest transforms."""
    if part not in present_parts(expected) or len(actual.get('meshes', [])) != 1:
        raise ValueError('staged Real Estate rig must contain exactly its expected mesh')
    old = next(item for item in expected['meshes'] if item['name'] == part)
    new = actual['meshes'][0]
    if new['name'] != part:
        raise ValueError(f'staged {part} FBX contains the wrong mesh')
    if old['bones'] and new.get('armature') != old.get('armature'):
        raise ValueError(f'staged {part} FBX changed its bone armature')
    a = {bone['name']:bone for bone in old['bones']}
    b = {bone['name']:bone for bone in new['bones']}
    if a.keys() != b.keys():
        raise ValueError(f'staged {part} changed bone names')
    for name, before in a.items():
        after = b[name]
        if before['parent'] != after['parent']:
            raise ValueError(f'staged {part} changed parent for {name}')
        if len(before['matrixLocal']) != len(after['matrixLocal']) or any(
            abs(float(x)-float(y)) > .0001
            for x,y in zip(before['matrixLocal'],after['matrixLocal'])
        ):
            raise ValueError(f'staged {part} changed rest pose for {name}')
        if name not in new.get('influencedBones', []):
            raise ValueError(f'staged {part} lost weighted bone {name}')
