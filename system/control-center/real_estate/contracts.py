"""Real Estate naming, prices and mesh/armature contracts."""
from __future__ import annotations

import re

from .rig_features import feature_warnings
from services.retired_col_mesh import retired
from .rig_publication_policy import publish_bones_for_mesh, carrier_bones

HOUSE_NAME = re.compile(r"^(?P<kind>[a-z][a-z0-9_]*)_level(?P<level>[1-9][0-9]*)_(?P<variant>[0-9]+)(?:_remesh)?$")
SLUG = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
REQUIRED_MESH = "house"


def present_parts(analysis: dict) -> tuple[str, ...]:
    """All authored meshes in stable order (legacy house first when present).

    A removed mesh is not revived by stale publication records. Part names are
    authored FBX identities, not a fixed house/door enum.
    """
    meshes = analysis.get("meshes", []) if isinstance(analysis, dict) else []
    names = [item.get("name") for item in meshes if isinstance(item, dict)
             and isinstance(item.get("name"), str) and not retired(item.get("name"))]
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

    No visual mesh name is mandatory. The unified house_armature remains
    the source of authored sockets, regardless of the mesh carrying them.
    """
    meshes = {part.get('name'): part for part in value.get('meshes', [])
              if isinstance(part, dict) and isinstance(part.get('name'), str)}
    house = meshes.get('house')
    door = meshes.get('door')
    warnings = []

    def warn(part, code, message):
        warnings.append({'part': part, 'code': code, 'message': message})

    if not any(str(mesh.get('armature') or '').casefold() == 'house_armature'
               for mesh in meshes.values()):
        warn('', 'missing_house_armature',
             'Link house_armature to at least one authored mesh to publish sockets.')
    # New standard: sockets describe attachment/interaction sites; a missing
    # socket is not itself proof that an optional feature is authored. In a
    # hinge-enabled door, however, hierarchy and rigid skinning must agree.
    warnings.extend(feature_warnings(value))

    for name in value.get('unassignedArmatures', []):
        warn('', 'unassigned_armature',
             f"Armature {name} is not linked to a mesh and will not be published.")

    # Several static meshes may intentionally share the house armature. The
    # publication pipeline isolates each Model Asset and preserves its sockets,
    # so this is supported authoring, not a warning requiring confirmation.
    return warnings


def validate_analysis(value: dict) -> dict:
    meshes = value.get("meshes") if isinstance(value, dict) else None
    if not isinstance(meshes, list) or not meshes or not all(isinstance(item, dict) for item in meshes):
        raise ValueError("FBX must contain at least one visible Mesh (names are unrestricted).")
    names = [item.get("name") for item in meshes]
    if any(not isinstance(name, str) or not name.strip() or name in (".", "..")
           or "/" in name or "\\" in name for name in names):
        raise ValueError("FBX contains an invalid mesh name (empty or path separator).")
    if any(name.casefold() == 'rig_carrier' for name in names):
        raise ValueError('rig_carrier is reserved for the technical published house root')
    if len(set(name.casefold() for name in names)) != len(names):
        raise ValueError("FBX mesh names must be unique, including letter case.")
    if not any(str(item.get('armature') or '').casefold() == 'house_armature' for item in meshes):
        raise ValueError('Link house_armature to an authored mesh. A mesh named house is not required.')
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
    # Multiple meshes may share one authored house_armature. Only a selected
    # carrier publishes the static socket hierarchy; moving meshes publish
    # just their required hinge chain and child interactions.
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
    if part == 'rig_carrier':
        staged = actual.get('meshes', [])
        if len(staged) != 1 or staged[0]['name'] != 'rig_carrier':
            raise ValueError('independent socket publication must contain only rig_carrier')
        old_bones = carrier_bones(expected)
        new = staged[0]
        if new.get('armature') != 'house_armature':
            raise ValueError('rig_carrier has no authored house_armature')
        a = {b['name']: b for b in old_bones}
        b = {b['name']: b for b in new['bones']}
        if a.keys() != b.keys():
            raise ValueError('rig_carrier publication changed bone names')
        for name, before in a.items():
            after = b[name]
            if before.get('parent', '') != after.get('parent', ''):
                raise ValueError('rig_carrier changed bone parent: ' + name)
            if name not in new.get('influencedBones', []):
                raise ValueError('rig_carrier lost weighted bone: ' + name)
        return
    if part not in present_parts(expected):
        raise ValueError('unregistered staged Real Estate part')
    old = next(item for item in expected['meshes'] if item['name'] == part)
    staged = actual.get('meshes', [])
    visuals = [row for row in staged if row['name'] != 'rig_carrier']
    carriers = [row for row in staged if row['name'] == 'rig_carrier']
    if len(visuals) != 1 or carriers:
        raise ValueError('visual publication must not contain rig_carrier')
    new = visuals[0]
    if visuals[0]['name'] != part:
        raise ValueError(f'staged {part} FBX contains the wrong visual mesh')
    if publish_bones_for_mesh(old) and new.get('armature') != 'house_armature':
        raise ValueError(f'staged {part} FBX changed its bone armature')
    a = {bone['name']:bone for bone in publish_bones_for_mesh(old)}
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
