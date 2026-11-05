"""Host Agent adapter for shared Blender FBX mesh inspection."""
from __future__ import annotations
import json
import math
from pathlib import Path
from services.mesh_authoring_policy import is_collision_mesh, location_mesh_profile


def inspect(root: Path, source: Path) -> dict:
    from services.fbx_blender_report import inspect_report
    return validate(inspect_report(root, 'analyze_model_fbx.py', source, label='Location FBX'))


def validate(analysis: dict) -> dict:
    """Validate untrusted Blender JSON before caching or giving it to Studio."""
    if not isinstance(analysis, dict) or analysis.get('schemaVersion') != 1:
        raise ValueError('invalid Location FBX inspection schema')
    meshes = analysis.get('meshes')
    if not isinstance(meshes, list) or not (1 <= len(meshes) <= 1000):
        raise ValueError('invalid Location FBX mesh count')
    names = set()
    for mesh in meshes:
        if not isinstance(mesh, dict) or not isinstance(mesh.get('name'), str):
            raise ValueError('invalid Location FBX mesh entry')
        name = mesh['name'].strip()
        if not name or len(name) > 160 or name.casefold() in names:
            raise ValueError('duplicate or invalid Location FBX mesh name')
        names.add(name.casefold())
        if type(mesh.get('vertices')) is not int or mesh['vertices'] < 0:
            raise ValueError('invalid vertex count')
        if not isinstance(mesh.get('armature'), str) or not isinstance(mesh.get('bones'), list):
            raise ValueError('invalid Location FBX skeleton')
        if len(mesh['bones']) > 4096:
            raise ValueError('too many FBX bones')
        bone_names = set()
        for bone in mesh['bones']:
            if not isinstance(bone, dict) or not isinstance(bone.get('name'), str) or not isinstance(bone.get('parent'), str):
                raise ValueError('invalid FBX bone')
            if bone['name'] in bone_names:
                raise ValueError('duplicate FBX bone')
            bone_names.add(bone['name'])
            matrix = bone.get('matrixLocal')
            if not isinstance(matrix, list) or len(matrix) != 16 or not all(type(v) in (int,float) and math.isfinite(v) for v in matrix):
                raise ValueError('invalid FBX rest matrix')
        if not isinstance(mesh.get('influencedBones'), list):
            raise ValueError('missing FBX influences')
        if any(not isinstance(name, str) or name not in bone_names for name in mesh['influencedBones']):
            raise ValueError('FBX weights reference an unknown bone')
        if any(bone['parent'] and bone['parent'] not in bone_names for bone in mesh['bones']):
            raise ValueError('FBX bone parent missing from armature')
    has_collider = any(is_collision_mesh(m['name']) for m in meshes)
    if analysis.get('hasCollider') != has_collider:
        raise ValueError('FBX collision role mismatch')
    for mesh in meshes:
        profile = location_mesh_profile(mesh['name'], has_collider=has_collider)
        if mesh.get('role') != profile['role'] or mesh.get('physics') != profile:
            raise ValueError('FBX physics policy mismatch')
    return analysis
