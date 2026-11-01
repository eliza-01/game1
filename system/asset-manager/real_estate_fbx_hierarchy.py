"""Recover the authoring rig boundaries lost by Blender's nested-FBX import.

FBX Model/OO and skin-cluster connections are the source of truth for *object*
relationships. Blender may promote a child armature's Null container to a bone
of its parent armature. Inspect and publication must share this normalization.
Neither the authored FBX nor stored/published assets are mutated here.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import struct


@dataclass(frozen=True)
class AuthoredRigs:
    bones: dict[str, frozenset[str]]
    parents: dict[str, dict[str, str]]
    mesh_rigs: dict[str, str]
    nested: frozenset[str]


def _fbx_records(source: Path):
    """Read only FBX object/connection metadata; skip geometry/array payloads.

    Supports the 32- and 64-bit binary node offsets (FBX 7.4/7.5+). This is
    intentionally a bounded metadata reader, not a replacement FBX importer.
    """
    with Path(source).open('rb') as stream:
        magic = stream.read(23)
        if magic != b'Kaydara FBX Binary  \x00\x1a\x00':
            raise ValueError('Real Estate rig discovery requires a binary FBX 7.x file')
        version_bytes = stream.read(4)
        if len(version_bytes) != 4:
            raise ValueError('FBX header is truncated')
        version = struct.unpack('<I', version_bytes)[0]
        if not 7400 <= version < 8000:
            raise ValueError(f'Unsupported FBX version {version} for Real Estate rig discovery')
        wide = version >= 7500
        header = 25 if wide else 13
        header_format = '<QQQB' if wide else '<IIIB'
        size = Path(source).stat().st_size

        def child_nodes(limit, depth=0):
            if depth > 4:
                raise ValueError('Unexpected nested FBX metadata')
            while stream.tell() + header <= limit:
                start = stream.tell()
                raw = stream.read(header)
                if len(raw) != header:
                    raise ValueError('Truncated FBX node header')
                end, count, byte_size, name_size = struct.unpack(header_format, raw)
                if not end:
                    return
                if end <= start or end > size or start + header + name_size + byte_size > end:
                    raise ValueError('Invalid FBX node offsets')
                name = stream.read(name_size).decode('utf-8', 'replace')
                interested = name in ('Model', 'Geometry', 'Deformer', 'C')
                if interested and count > 16:
                    raise ValueError('Invalid FBX object metadata')
                props = []
                for _ in range(count):
                    tag = stream.read(1)
                    scalar = {b'Y': 'h', b'C': '?', b'B': 'B', b'I': 'i',
                              b'L': 'q', b'F': 'f', b'D': 'd'}.get(tag)
                    if scalar:
                        props.append(struct.unpack('<' + scalar, stream.read(struct.calcsize(scalar)))[0])
                    elif tag in (b'R', b'S'):
                        length_bytes = stream.read(4)
                        if len(length_bytes) != 4:
                            raise ValueError('Truncated FBX property')
                        length = struct.unpack('<I', length_bytes)[0]
                        if length > size or stream.tell() + length > end:
                            raise ValueError('Invalid FBX property length')
                        if interested and tag == b'S':
                            props.append(stream.read(length).decode('utf-8', 'replace'))
                        else:
                            stream.seek(length, 1)
                            props.append(None)
                    elif tag in (b'b', b'i', b'l', b'f', b'd'):
                        array_header = stream.read(12)
                        if len(array_header) != 12:
                            raise ValueError('Truncated FBX array')
                        length = struct.unpack('<III', array_header)[2]
                        if stream.tell() + length > end:
                            raise ValueError('Invalid FBX array length')
                        stream.seek(length, 1)
                        props.append(None)
                    else:
                        raise ValueError(f'Unknown FBX property type {tag!r}')
                if stream.tell() > end:
                    raise ValueError('FBX property exceeds node')
                if interested:
                    yield name, props
                if name in ('Objects', 'Connections'):
                    yield from child_nodes(end, depth + 1)
                stream.seek(end)

        yield from child_nodes(size)


def authored_rigs(source: Path) -> AuthoredRigs:
    """Find the nearest *object* armature for each bone and each mesh."""
    models = {}
    geometries = {}
    deformers = {}
    connections = []
    for kind, props in _fbx_records(source):
        if kind in ('Model', 'Geometry', 'Deformer'):
            if len(props) < 3 or not isinstance(props[0], int):
                raise ValueError(f'Malformed FBX {kind} record')
            name = str(props[1]).split('\x00', 1)[0]
            (models if kind == 'Model' else geometries if kind == 'Geometry' else deformers)[props[0]] = (name, props[2])
        elif kind == 'C' and len(props) >= 3 and props[0] == 'OO':
            connections.append((props[1], props[2]))

    model_parents = {child: parent for child, parent in connections if child in models and parent in models}

    def closest_armature(node):
        visited = set()
        while node in model_parents:
            node = model_parents[node]
            if node in visited:
                raise ValueError('FBX model hierarchy has a cycle')
            visited.add(node)
            if models[node][1] == 'Null':
                return node
        return None

    bones = defaultdict(set)
    parents = defaultdict(dict)
    armatures = {}
    bone_owners = {}
    for ident, (name, kind) in models.items():
        if kind != 'LimbNode':
            continue
        armature = closest_armature(ident)
        if armature is None:
            continue
        owner = models[armature][0]
        if name in bones[owner]:
            raise ValueError(f'Duplicate bone {name!r} in authored armature {owner!r}')
        armatures[armature] = owner
        bones[owner].add(name)
        bone_owners[ident] = owner
        parent = model_parents.get(ident)
        parents[owner][name] = models[parent][0] if parent in models and models[parent][1] == 'LimbNode' else ''

    if len(set(armatures.values())) != len(armatures):
        raise ValueError('FBX contains duplicate armature object names')

    nested = set()
    for ident, name in armatures.items():
        parent = model_parents.get(ident)
        visited = set()
        while parent in models and parent not in visited:
            visited.add(parent)
            if parent in armatures:
                nested.add(name)
                break
            parent = model_parents.get(parent)

    mesh_rigs = {}
    model_by_geometry = {child: parent for child, parent in connections
                         if child in geometries and parent in models}
    skin_by_geometry = defaultdict(set)
    for child, parent in connections:
        if child in deformers and deformers[child][1] == 'Skin' and parent in geometries:
            skin_by_geometry[parent].add(child)
    clusters_by_skin = defaultdict(set)
    for child, parent in connections:
        if child in deformers and deformers[child][1] == 'Cluster' and parent in deformers:
            clusters_by_skin[parent].add(child)
    bones_by_cluster = defaultdict(set)
    for child, parent in connections:
        if child in bone_owners and parent in deformers and deformers[parent][1] == 'Cluster':
            bones_by_cluster[parent].add(bone_owners[child])
    for geometry, model in model_by_geometry.items():
        if geometries[geometry][1] != 'Mesh':
            continue
        name = models[model][0]
        owners = {owner for skin in skin_by_geometry[geometry]
                  for cluster in clusters_by_skin[skin] for owner in bones_by_cluster[cluster]}
        if len(owners) > 1:
            raise ValueError(f'Mesh {name!r} is skinned across authored armatures {sorted(owners)}')
        if owners:
            mesh_rigs[name] = owners.pop()
        else:
            armature = closest_armature(model)
            if armature in armatures:
                mesh_rigs[name] = armatures[armature]
    return AuthoredRigs({k: frozenset(v) for k, v in bones.items()},
                       dict(parents), mesh_rigs, frozenset(nested))
