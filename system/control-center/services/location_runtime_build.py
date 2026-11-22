"""Conservative offline Runtime Place compiler for saved Roblox XML places.

Only a verified authoring `.rbxlx` can be used. This compiler never contacts
Studio or Roblox, never edits the authoring file, and never publishes.
Unsupported models fail closed rather than being partially stripped.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from urllib.parse import parse_qs, urlsplit
from pathlib import Path
from collections import Counter
import shutil
import time
import uuid

from xml.etree import ElementTree as etree


MAX_XML_BYTES = 150 * 1024 * 1024


def _sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _parse(path):
    if not path.is_file() or path.is_symlink() or not 100 < path.stat().st_size <= MAX_XML_BYTES:
        raise ValueError('Save the current authoring Place as place/game1_runtime_source.rbxlx (XML, max 150 MB)')
    # Reject external entity definitions; ElementTree itself does not resolve
    # external entities, but fail rather than silently accepting a DTD.
    with path.open('rb') as stream:
        header = stream.read(512)
    if b'<!DOCTYPE' in header or b'<!ENTITY' in header:
        raise ValueError('DOCTYPE and XML entities are not accepted in source Place')
    try:
        tree = etree.parse(str(path))
    except (etree.ParseError, OSError) as error:
        raise ValueError('Source Place is not a valid Roblox XML .rbxlx file') from error
    if tree.getroot().tag != 'roblox' or tree.getroot().get('version') not in ('4', '5'):
        raise ValueError('Source file must be a complete Roblox XML Place, not a Model .rbxmx')
    return tree


def _name(node):
    values = [e for e in node.findall('./Properties/string') if e.get('name') == 'Name']
    return (values[0].text or '') if values else ''


def _items(root):
    for child in root:
        if child.tag == 'Item':
            yield child
            yield from _items(child)


def _authoring_marker_root(tree):
    """Find the editor-only Game1Authoring folder without touching its source.

    Do not remove a folder if an unmanaged object has taken that reserved name,
    or if a reference outside the folder would become dangling in Runtime.
    """
    workspace = [node for node in tree.getroot()
                 if node.tag == 'Item' and node.get('class') == 'Workspace']
    if len(workspace) != 1:
        raise ValueError('Saved Place must include exactly one Workspace service')
    roots = [node for node in workspace[0] if node.tag == 'Item'
             and _name(node) == 'Game1Authoring']
    if not roots:
        return workspace[0], None, set()
    if len(roots) != 1 or roots[0].get('class') != 'Folder':
        raise ValueError('Workspace.Game1Authoring must be one editor-owned Folder')
    authored = {roots[0], *_items(roots[0])}
    refs = [node.get('referent') for node in authored]
    if any(not ref for ref in refs) or len(refs) != len(set(refs)):
        raise ValueError('Game1Authoring contains missing or duplicate XML referents')
    owned_refs = set(refs)
    for node in _items(tree.getroot()):
        if node in authored:
            continue
        for ref in node.findall('./Properties/Ref'):
            if (ref.text or '').strip() in owned_refs:
                raise ValueError('External reference into Game1Authoring; cannot strip safely')
    return workspace[0], roots[0], owned_refs


def _strip_authoring_markers(tree):
    workspace, folder, refs = _authoring_marker_root(tree)
    if folder is not None:
        workspace.remove(folder)
    return refs


def _model_paths(root):
    # Path has the same service/Model hierarchy used by Studio's GetFullName.
    def walk(node, parts):
        if node.tag != 'Item':
            return
        name = _name(node)
        here = parts + (name,)
        yield ('.'.join(here), node)
        for child in node:
            if child.tag == 'Item':
                yield from walk(child, here)
    for child in root:
        if child.tag == 'Item':
            yield from walk(child, ())


def _property(node, tag, name):
    match = [e for e in node.findall('./Properties/*') if e.get('name') == name]
    if len(match) != 1 or match[0].tag != tag:
        raise ValueError(f'Missing or unexpected {name} on {_name(node)}')
    return match[0]


def _vector3(node, name):
    # Roblox XML serializes BasePart.Size as lower-case `size` in many
    # Studio versions, despite its public Luau property spelling `Size`.
    aliases = ('size', 'Size') if name.lower() == 'size' else (name,)
    v = None
    for candidate in aliases:
        try:
            v = _property(node, 'Vector3', candidate)
            break
        except ValueError:
            continue
    if v is None:
        raise ValueError('Missing Size on ' + _name(node))
    return tuple(float(v.findtext(axis)) for axis in ('X', 'Y', 'Z'))


def _cframe(node):
    cf = _property(node, 'CoordinateFrame', 'CFrame')
    return tuple(float(cf.findtext(k)) for k in (
        'X', 'Y', 'Z', 'R00', 'R01', 'R02', 'R10', 'R11', 'R12', 'R20', 'R21', 'R22'))


def _roblox_asset_id(uri, name):
    """Resolve only a numeric Roblox cloud asset, never an arbitrary URI.

    A Content object/opaque reference cannot be checked against the numeric
    Mesh ID in the authoritative Studio snapshot, so it must fail closed.
    """
    uri = uri.strip()
    match = re.fullmatch(r'rbxassetid://([1-9][0-9]*)', uri)
    if match:
        return match.group(1)
    if re.fullmatch(r'[1-9][0-9]*', uri):
        return uri
    parsed = urlsplit(uri)
    if (parsed.scheme in ('http', 'https') and
            parsed.hostname in ('www.roblox.com', 'roblox.com', 'assetdelivery.roblox.com') and
            parsed.path.rstrip('/') in ('/asset', '/v1/asset') and
            not parsed.fragment):
        params = parse_qs(parsed.query, strict_parsing=True)
        ids = params.get('id', [])
        if len(ids) == 1 and re.fullmatch(r'[1-9][0-9]*', ids[0]):
            return ids[0]
    raise ValueError(f'{name}: unsupported or non-numeric MeshContent URI ({uri[:120]!r})')


def _mesh_id(node):
    """Read legacy MeshId/MeshID and the Studio 2026 MeshContent XML.

    Roblox Studio began serializing new Content asset properties in Nov 2026:
        <Content name="MeshContent"><uri>rbxassetid://123</uri></Content>
    Previous files can contain <Content name="MeshId"><url>...</url></Content>.
    If both are present, they must resolve to the SAME asset ID.
    """
    name = _name(node)
    values = [e for e in node.findall('./Properties/*')
              if e.get('name') in ('MeshContent', 'MeshId', 'MeshID')]
    if not values:
        raise ValueError(f'{name}: no serialized MeshContent/MeshId property in saved Place XML; '
                         'Studio Scan reads live properties and does not inspect the XML export')
    resolved = []
    for value in values:
        if value.tag == 'Content':
            children = list(value)
            if (len(children) != 1 or children[0].tag not in ('uri', 'url', 'Url')
                    or list(children[0])):
                raise ValueError(f'{name}: unsupported {value.get("name")} Content source; '
                                 'only a published Roblox asset URI is allowed (not null/object/opaque)')
            raw = children[0].text or ''
        elif value.tag == 'string' and value.get('name') in ('MeshId', 'MeshID'):
            raw = value.text or ''
        else:
            raise ValueError(f'{name}: unsupported XML property type for {value.get("name")}: {value.tag}')
        resolved.append(_roblox_asset_id(raw, name))
    if len(set(resolved)) != 1:
        raise ValueError(f'{name}: conflicting MeshContent/MeshId values in saved Place XML')
    return resolved[0]


def _near(a, b, tolerance=0.025):
    return len(a) == len(b) and all(abs(float(x) - float(y)) < tolerance for x, y in zip(a, b))


COLLISION_CLASSES = ('Part', 'WedgePart', 'CornerWedgePart')


def placement_shape_problem(row):
    """Shared Preflight and LOD Manager eligibility boundary.

    Simple Location geometry keeps its established M388 pilot. Composite
    visuals (including carriers, bones, lights and emitters) use the same
    Runtime compiler/scheduler via a strict, separately verified adapter.
    """
    nodes = row.get('hierarchy') or []
    from .location_runtime_composite import is_composite, structure_problem
    if is_composite(row):
        return structure_problem(row)
    visuals = [n for n in nodes if n.get('class') == 'MeshPart']
    if len(visuals) != 1:
        return 'requires one identifiable visual MeshPart'
    if sum(n.get('class') == 'Model' for n in nodes) != 1:
        return 'nested Model hierarchy is not supported for this Runtime build'
    allowed = {'Model', 'MeshPart', 'SurfaceAppearance', *COLLISION_CLASSES}
    if any(n.get('class') not in allowed for n in nodes):
        return 'unsupported visual descendants'
    colliders = [n for n in nodes if n.get('class') in COLLISION_CLASSES]
    if any(not str(n.get('name', '')).startswith('__Game1Collision_') for n in colliders):
        return 'contains non-Blueprint physical Parts'
    if len(colliders) > 256:
        return 'too many collision Parts'
    if not colliders and (visuals[0].get('canCollide') is not False or visuals[0].get('canQuery') is not False):
        return 'no independent collision; visual MeshPart still collidable/queryable'
    return ''


def _verify(source_tree, rows, targets):
    index = {}
    for path, node in _model_paths(source_tree.getroot()):
        if node.get('class') == 'Model':
            index.setdefault(path, []).append(node)
    selected_paths = {r['path'] for r in rows}
    for path, models in index.items():
        if not path.startswith('Workspace.'):
            continue
        # LandscapePainter stem attachments are named slug_<8 hex> rather
        # than DecoManager's slug__<8 hex>. Both belong to the selected type;
        # never silently leave unscanned copies in the compiled Runtime.
        if any(_name(model) == slug or _name(model).startswith(slug + '__')
               or (path.startswith('Workspace.Game1LandscapeDecor.')
                   and re.fullmatch(re.escape(slug) + r'_[0-9a-f]{8}', _name(model)))
               for slug in targets for model in models) and path not in selected_paths:
            raise ValueError('Uninventoried target Location Model in saved Place: ' + path)
    found = []
    removed = set()
    for row in rows:
        path = row['path']
        problem = placement_shape_problem(row)
        if problem:
            raise ValueError(f'{path}: {problem}')
        models = index.get(path, [])
        if len(models) != 1:
            raise ValueError(f'{path}: expected one Model in saved XML, got {len(models)}')
        model = models[0]
        from .location_runtime_composite import is_composite, validate_xml
        if is_composite(row):
            # All effects and the rig_carrier are preserved. Only the
            # identified visible MeshParts become lightweight Part proxies.
            components = validate_xml(model, row, name=_name, cframe=_cframe,
                vector3=_vector3, mesh_id=_mesh_id, near=_near)
            found.append((row, model, components))
            continue
        items = [child for child in model if child.tag == 'Item']
        visuals = [c for c in items if c.get('class') == 'MeshPart']
        colliders = [c for c in items if c.get('class') in COLLISION_CLASSES
                     and _name(c).startswith('__Game1Collision_')]
        if len(visuals) != 1 or len(items) != len(colliders) + 1:
            raise ValueError(f'{path}: unexpected or nested contents in source Model')
        mesh = visuals[0]
        mesh_children = [child for child in mesh if child.tag == 'Item']
        if (len(mesh_children) != sum(n.get('class') == 'SurfaceAppearance' for n in row['hierarchy'])
            or any(child.get('class') != 'SurfaceAppearance' or any(n.tag == 'Item' for n in child)
                   for child in mesh_children)):
            raise ValueError(f'{path}: unsupported visual descendants (rig/effects)')
        if any(any(child.tag == 'Item' for child in collider) for collider in colliders):
            raise ValueError(f'{path}: collision Part contains nested descendants')
        if _mesh_id(mesh) != str(row['meshId']):
            raise ValueError(f'{path}: MeshId differs from the current Studio Snapshot')
        visual_snapshot = next(n for n in row['hierarchy'] if n.get('class') == 'MeshPart')
        if not _near(_cframe(mesh), visual_snapshot['cframe']) or not _near(_vector3(mesh, 'Size'), visual_snapshot['size']):
            raise ValueError(f'{path}: source MeshPart transform differs from latest Scan')
        # Duplicate collision names are invalid because the XML to snapshot
        # association must be one-to-one, including distinct Wedge shapes.
        expected = {(n.get('class'), n.get('name')): n for n in row['hierarchy']
                    if n.get('class') in COLLISION_CLASSES}
        if len(expected) != len(colliders):
            raise ValueError(f'{path}: collision count/name differs from latest Scan')
        for collision in colliders:
            match = expected.pop((collision.get('class'), _name(collision)), None)
            if not match or not _near(_cframe(collision), match['cframe']) or not _near(_vector3(collision, 'Size'), match['size']):
                raise ValueError(f'{path}: collision differs from latest Scan')
        if expected:
            raise ValueError(f'{path}: missing collision in saved XML')
        if not colliders:
            # The XML geometry itself must confirm no collision or query
            # behavior, independent of what the Studio Scan reported.
            for name in ('CanCollide', 'CanQuery'):
                values = [x for x in mesh.findall('./Properties/*') if x.get('name') == name]
                if len(values) != 1 or values[0].tag != 'bool' or (values[0].text or '').lower() != 'false':
                    raise ValueError(f'{path}: visual-only asset must have {name}=false in saved XML')
        if not row.get('placementId') or row.get('issues') or row.get('ambiguous') or row.get('duplicateId'):
            raise ValueError(f'{path}: unresolved placement diagnostics')
        found.append((row, model, mesh))
        for node in (mesh, *mesh_children):
            ref = node.get('referent')
            if not ref or ref in removed:
                raise ValueError(f'{path}: missing/duplicate removed visual referent')
            removed.add(ref)
    # The selected root Model may point PrimaryPart to its OWN visual MeshPart.
    # Removing that visual invalidates the property, but clearing it in the
    # *runtime copy only* is safe: immutable placement pivots live in the
    # Runtime Manifest and collision Parts retain their world CFrames.
    # Never permit arbitrary references (including another Model's PrimaryPart).
    owned_primary_parts = {id(model): mesh.get('referent') for _row, model, mesh in found
                           if not isinstance(mesh, list)}
    for node in _items(source_tree.getroot()):
        if node.get('referent') in removed:
            continue
        for ref in node.findall('./Properties/Ref'):
            target = (ref.text or '').strip()
            if target not in removed:
                continue
            if (node.get('class') == 'Model'
                    and ref.get('name') == 'PrimaryPart'
                    and owned_primary_parts.get(id(node)) == target):
                continue
            raise ValueError(f'Visual has external reference from '
                             f'{node.get("class")} {_name(node)}.{ref.get("name")}; '
                             'cannot strip safely')
    return found


RUNTIME_MANIFEST_NAME = 'Game1LocationRuntimeManifest'
RUNTIME_MANIFEST_KIND = 'game1-location-visual-stream-v1'
# One Roblox StringValue cannot hold a large runtime world manifest. Keep
# small drafts backwards compatible and segment larger ones into children of
# the SAME marker: no additional runtime streaming service is introduced.
RUNTIME_INLINE_BYTES = 180000
RUNTIME_CHUNK_BYTES = 120000
RUNTIME_MAX_CHUNKS = 64
RUNTIME_CHUNK_TRANSPORT = 'chunked-v1'


def _manifest_json(payload):
    # ASCII-only JSON means character boundaries are identical to UTF-8 byte
    # boundaries; Roblox's per-StringValue byte limit can be checked exactly.
    return json.dumps(payload, ensure_ascii=True, separators=(',', ':'), allow_nan=False)


def _manifest_segments(payload):
    encoded = _manifest_json(payload)
    if len(encoded) <= RUNTIME_INLINE_BYTES:
        return encoded, []
    chunks = [encoded[pos:pos + RUNTIME_CHUNK_BYTES]
              for pos in range(0, len(encoded), RUNTIME_CHUNK_BYTES)]
    if len(chunks) > RUNTIME_MAX_CHUNKS:
        raise ValueError('Runtime manifest exceeds bounded transport capacity ('
                         f'{len(chunks)} chunks; maximum {RUNTIME_MAX_CHUNKS})')
    descriptor = _manifest_json({
        'transport': RUNTIME_CHUNK_TRANSPORT, 'chunks': len(chunks),
        'bytes': len(encoded), 'sha256': hashlib.sha256(encoded.encode('ascii')).hexdigest(),
    })
    return descriptor, chunks


def _read_embedded_manifest(marker):
    # Verify serialized Runtime XML, including chunk count and checksum.
    descriptor = _property(marker, 'string', 'Value').text or ''
    decoded = json.loads(descriptor)
    if not isinstance(decoded, dict) or decoded.get('transport') is None:
        if list(marker.findall('./Item')):
            raise RuntimeError('Unexpected inline Runtime marker children')
        return decoded
    chunks = list(marker.findall('./Item'))
    count = decoded.get('chunks')
    if (decoded.get('transport') != RUNTIME_CHUNK_TRANSPORT
            or type(count) is not int or not 2 <= count <= RUNTIME_MAX_CHUNKS
            or len(chunks) != count or type(decoded.get('bytes')) is not int
            or type(decoded.get('sha256')) is not str):
        raise RuntimeError('Invalid compiled Runtime manifest transport')
    values = []
    for index, node in enumerate(chunks, 1):
        if node.get('class') != 'StringValue' or _name(node) != f'Chunk{index:03d}':
            raise RuntimeError('Invalid Runtime manifest chunk order')
        value = _property(node, 'string', 'Value').text or ''
        if not 0 < len(value) <= RUNTIME_CHUNK_BYTES:
            raise RuntimeError('Invalid Runtime manifest chunk size')
        values.append(value)
    encoded = ''.join(values)
    if (len(encoded) != decoded['bytes'] or
            hashlib.sha256(encoded.encode('ascii')).hexdigest() != decoded['sha256']):
        raise RuntimeError('Runtime manifest checksum mismatch')
    return json.loads(encoded)


def _runtime_payload(rows, *, snapshot_id, catalog_digest, settings=None, houses=None):
    """Validated published geometry + per-type capability + distance policy.

    This remains compiler-owned data. A runtime client never chooses cloud IDs.
    """
    from .location_streaming_config import DEFAULT_SETTINGS, validate_settings, runtime_mode, distance_profile
    settings = validate_settings(settings or DEFAULT_SETTINGS)
    targets = sorted({row['slug'] for row in rows})
    if (not targets and not houses) or len(targets) > 64 or any(runtime_mode(settings, slug) == 'off' for slug in targets):
        raise ValueError('No valid selected Runtime streaming types')
    placements = []
    compound_signatures = {}
    for row in rows:
        from .location_runtime_composite import is_composite, component_manifest
        composite = is_composite(row)
        visual = ([entry for entry in row['hierarchy'] if entry.get('class') == 'MeshPart'
                   and entry.get('name') != 'rig_carrier'] if composite else
                  [entry for entry in row['hierarchy'] if entry.get('class') == 'MeshPart'])
        pivot = (row.get('pivotEvidence') or {}).get('modelPivot')
        if not visual or not isinstance(pivot, list) or len(pivot) != 12:
            raise ValueError(f"{row['path']}: no verified Model pivot for runtime streaming")
        positions = (pivot, visual[0].get('cframe'), visual[0].get('size'))
        lengths = (12, 12, 3)
        for values, length in zip(positions, lengths):
            if not isinstance(values, list) or len(values) != length or not all(
                    isinstance(v, (float, int)) and not isinstance(v, bool)
                    and math.isfinite(v) and abs(v) < 1000000000 for v in values):
                raise ValueError(f"{row['path']}: invalid geometry in runtime marker")
        if any(v <= 0 for v in visual[0]['size']):
            raise ValueError(f"{row['path']}: invalid runtime visual size")
        entry = {'id': row['placementId'], 'slug': row['slug'],
            'pivot': pivot, 'cframe': visual[0]['cframe'], 'size': visual[0]['size']}
        if composite:
            entry['modelPath'] = row['path'].split('.')[1:]
            if not entry['modelPath'] or any(not segment or '.' in segment
                                             for segment in entry['modelPath']):
                raise ValueError(f"{row['path']}: invalid runtime Model path")
            entry['components'] = component_manifest(row)
            signature = tuple((v['name'],v['meshId']) for v in entry['components'])
            previous = compound_signatures.setdefault(row['slug'], signature)
            if previous != signature:
                raise ValueError(f"{row['slug']}: different Mesh IDs/parts across placements; Sync first")
        placements.append(entry)
    if len(placements) > 5000:
        raise ValueError('Runtime manifest exceeds 5000 placements')
    payload = {
        'schemaVersion': 4, 'hysteresis': settings['hysteresis'], 'kind': RUNTIME_MANIFEST_KIND,
        'snapshotRevision': snapshot_id, 'catalogDigest': catalog_digest,
        'publishAllowed': False, 'targets': targets,
        'modes': {slug: runtime_mode(settings, slug) for slug in targets},
        'assetDistances': {slug: distance_profile(settings, slug) for slug in targets},
        'placements': placements,
    }
    if houses:
        payload['houses'] = houses
    # Check the same bounded transport that will be written by the compiler.
    # Large catalogs are chunked, not rejected because of placement counts.
    _manifest_segments(payload)
    return payload


def _apply_workspace_streaming(tree, settings):
    """Apply Roblox Studio streaming properties ONLY in the fresh Runtime XML tree.

    Enum token values are the published Roblox Enum values, never guessed from
    string names. Unsupported serialized property types fail closed.
    """
    world = settings['workspace']
    workspaces = [node for node in tree.getroot() if node.tag == 'Item' and node.get('class') == 'Workspace']
    if len(workspaces) != 1:
        raise ValueError('Saved Place must have exactly one Workspace service')
    properties = workspaces[0].find('Properties')
    if properties is None:
        raise ValueError('Workspace has no serialized Properties')
    fields = {
        'StreamingEnabled': ('bool', 'true' if world['streamingEnabled'] else 'false'),
        'StreamingMinRadius': ('int', str(world['minRadius'])),
        'StreamingTargetRadius': ('int', str(world['targetRadius'])),
        'ModelStreamingBehavior': ('token', str({'Default':0,'Legacy':1,'Improved':2}[world['modelStreamingBehavior']])),
        'StreamingIntegrityMode': ('token', str({'Default':0,'Disabled':1,'MinimumRadiusPause':2,'PauseOutsideLoadedArea':3}[world['streamingIntegrityMode']])),
        'StreamOutBehavior': ('token', str({'Default':0,'LowMemory':1,'Opportunistic':2}[world['streamOutBehavior']])),
    }
    for name, (tag, value) in fields.items():
        existing = [item for item in properties if item.get('name') == name]
        if len(existing) > 1 or (existing and existing[0].tag != tag):
            raise ValueError('Workspace XML has unsupported/duplicate ' + name)
        node = existing[0] if existing else etree.SubElement(properties, tag, name=name)
        node.text = value
    return fields


def _embed_runtime_manifest(tree, payload):
    """Embed client-side placement data ONLY into the separate Runtime XML tree."""
    services = [node for node in tree.getroot() if node.tag == 'Item'
                and node.get('class') == 'ReplicatedStorage']
    if len(services) != 1:
        raise ValueError('Saved Place must include exactly one ReplicatedStorage service')
    service = services[0]
    if any(_name(node) == RUNTIME_MANIFEST_NAME for node in service.iter('Item')):
        raise ValueError('Runtime marker already exists in source Place; refusing draft recompile')
    marker = etree.SubElement(service, 'Item', {
        'class': 'StringValue', 'referent': 'RBX_' + uuid.uuid4().hex,
    })
    props = etree.SubElement(marker, 'Properties')
    etree.SubElement(props, 'string', name='Name').text = RUNTIME_MANIFEST_NAME
    descriptor, chunks = _manifest_segments(payload)
    etree.SubElement(props, 'string', name='Value').text = descriptor
    for index, value in enumerate(chunks, 1):
        child = etree.SubElement(marker, 'Item', {
            'class': 'StringValue', 'referent': 'RBX_' + uuid.uuid4().hex,
        })
        child_props = etree.SubElement(child, 'Properties')
        etree.SubElement(child_props, 'string', name='Name').text = f'Chunk{index:03d}'
        etree.SubElement(child_props, 'string', name='Value').text = value
    return marker


def build_rows(overview, registry, settings=None):
    """Fail-closed build input over immutable Place Registry snapshot."""
    snap = overview.get('snapshot') or {}
    if snap.get('freshness') != 'SCANNED_THIS_SESSION' or not snap.get('catalogMatches'):
        raise ValueError('Run Scan Place again in this Control Center session before preparing Runtime')
    report = registry.revisions.get(snap['revisionId'])
    from .location_streaming_config import DEFAULT_SETTINGS, validate_settings
    settings = validate_settings(settings or DEFAULT_SETTINGS)
    selected = []
    by_slug = {r['slug']:r for r in overview['items']}
    from .location_streaming_config import runtime_mode
    # The immutable Scan, not a hand-authored slug allowlist, defines coverage.
    # Disabled types are explicit author decisions, never the implicit default.
    active = sorted({item['slug'] for item in overview['items']
                     if (item.get('count') or item.get('protectedCount'))
                     and runtime_mode(settings, item['slug']) != 'off'})
    if len(active) > 64:
        raise ValueError('Runtime supports at most 64 scanned Location Asset types')
    for slug in active:
        asset = by_slug.get(slug)
        mode = runtime_mode(settings, slug)
        externals = [r for r in report.get('protected', []) if r.get('slug') == slug]
        if not asset or not (asset.get('count') or externals):
            raise ValueError(slug + ': no recognized placements; disable streaming for this type')
        if asset['fullStatus'] != 'PUBLISHED' or not asset['fullModelId']:
            raise ValueError(slug + ': published FULL model required')
        if mode in ('lod1', 'lod2') and (asset['lod1Status'] != 'PUBLISHED' or not asset['lod1ModelId']):
            raise ValueError(slug + ': published LOD1 required for selected mode')
        if mode == 'lod2' and (asset['lod2Status'] != 'PUBLISHED' or not asset['lod2ModelId']):
            raise ValueError(slug + ': published LOD2 required for selected mode')
        # Painter is not a Deco placement. Only the complete published
        # attachment + intact tether/rig may be compiled, with all owner
        # attributes and nonvisual descendants preserved in the XML.
        from .location_runtime_composite import is_composite
        for external in externals:
            if not external.get('runtimeCandidate') or external.get('review'):
                raise ValueError(slug + ': LandscapePainter attachment not Runtime-verified: '
                                 + str(external.get('path')))
            if not is_composite(external):
                raise ValueError(slug + ': LandscapePainter requires composite runtime structure')
            selected.append({
                **external, 'placementId': 'painter_' + hashlib.sha256(
                    external['path'].encode('utf-8')).hexdigest()[:24],
                'issues': [], 'ambiguous': False, 'duplicateId': False,
                'needsRecapture': False, 'hasModel': True,
            })
        selected.extend(r for r in report['placements'] if r['slug'] == slug)
    if not selected:
        raise ValueError('Select at least one eligible Location Asset for Runtime streaming')
    for row in selected:
        reason = placement_shape_problem(row)
        if reason:
            raise ValueError(str(row.get('path')) + ': ' + reason)
        if row.get('issues') or row.get('needsCollision') or row.get('needsPhysics') or row.get('needsRecapture') or row.get('ambiguous') or row.get('duplicateId') or not row.get('placementId'):
            raise ValueError(str(row.get('path')) + ': unresolved placement diagnostic')
    ids = [r['placementId'] for r in selected]
    if len(ids) != len(set(ids)) or len({r['path'] for r in selected}) != len(selected):
        raise ValueError('Duplicate Placement IDs or paths in selected objects')
    return selected


class RuntimePlaceBuilder:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.source = self.root / 'place' / 'game1_runtime_source.rbxlx'
        self.destination = self.root / '.control-center' / 'runtime-builds'

    def inspect(self, rows, settings=None, house_inputs=None):
        source = self.source.resolve(strict=True)
        if source != self.source or source.suffix.lower() != '.rbxlx':
            raise ValueError('Source must be a regular place/game1_runtime_source.rbxlx, not a symlink')
        from .location_streaming_config import DEFAULT_SETTINGS, validate_settings
        settings = validate_settings(settings or DEFAULT_SETTINGS)
        tree = _parse(source)
        _, authoring_root, authoring_refs = _authoring_marker_root(tree)
        targets = sorted({row['slug'] for row in rows})
        selected = _verify(tree, rows, targets)
        from .house_runtime_compilation import inspect as inspect_houses, payload as house_payload
        house_rows = inspect_houses(tree, house_inputs or {})
        prepared_houses = house_payload(house_rows, house_inputs) if house_rows else None
        # Explicitly report placed houses that remain FULL Workspace instances.
        # A Plot registration alone does not opt a house into streaming.
        untouched_houses = {}
        for model_path, model in _model_paths(tree.getroot()):
            match = re.fullmatch(r'Workspace\.Plots\.\d+\.Houses\.(house_level\d+_\d{2})', model_path)
            if match and match.group(1) not in (house_inputs or {}):
                slug = match.group(1)
                untouched_houses[slug] = untouched_houses.get(slug, 0) + 1
        _runtime_payload(rows, snapshot_id=0, catalog_digest='preflight',
                         settings=settings, houses=prepared_houses)
        _apply_workspace_streaming(tree, settings)
        if any(_name(node) == RUNTIME_MANIFEST_NAME for node in _items(tree.getroot())):
            raise ValueError('Saved authoring Place already contains a Runtime marker')
        if len([node for node in tree.getroot() if node.tag == 'Item'
                and node.get('class') == 'ReplicatedStorage']) != 1:
            raise ValueError('Saved Place must include exactly one ReplicatedStorage service')
        return {'source': str(source), 'sourceSha256': _sha(source),
                'eligible': len(selected), 'houseCount': len(house_rows),
                'houseMeshParts': sum(len(r['parts']) for r in house_rows),
                'untouchedHouseCounts': untouched_houses,
                'untouchedHouseModels': sum(untouched_houses.values()),
                'counts': {slug: sum(r['slug'] == slug for r in rows) for slug in targets},
                'sourceBytes': source.stat().st_size,
                'authoringMarkersToStrip': len(authoring_refs)}

    def prepare(self, rows, *, expected_sha, snapshot_id, catalog_digest, settings=None, house_inputs=None):
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise ValueError('Run Preflight first')
        from .location_streaming_config import DEFAULT_SETTINGS, validate_settings
        settings = validate_settings(settings or DEFAULT_SETTINGS)
        meta = self.inspect(rows, settings, house_inputs)
        if expected_sha != meta['sourceSha256']:
            raise ValueError('Saved authoring Place changed since Preflight; run it again')
        tree = _parse(self.source)
        matched = _verify(tree, rows, sorted({r['slug'] for r in rows}))
        from .house_runtime_compilation import inspect as inspect_houses, transform as transform_houses, payload as house_payload
        selected_houses = inspect_houses(tree, house_inputs or {})
        prepared_houses = house_payload(selected_houses, house_inputs) if selected_houses else None
        # Write into a never-reused private build directory. The source is never edited.
        self.destination.mkdir(parents=True, exist_ok=True)
        build_dir = self.destination / ('runtime_' + time.strftime('%Y%m%dT%H%M%S', time.gmtime()) + '_' + uuid.uuid4().hex[:8])
        build_dir.mkdir(mode=0o700)
        try:
            backup = build_dir / 'authoring_backup.rbxlx'
            shutil.copy2(self.source, backup)
            if _sha(backup) != expected_sha:
                raise RuntimeError('Backup checksum failed; no Runtime Place generated')
            # Runtime copy retains each root Model and server collision Parts.
            before_refs = [node.get('referent') for node in _items(tree.getroot())]
            removed_refs = set()
            from .runtime_visual_proxy import convert as proxy_visual
            for _row, model, mesh in matched:
                if isinstance(mesh, list):
                    # Compound rig remains server-owned. Replace visual
                    # mesh content with inexpensive parts, preserving all
                    # effect children, welds and original referents.
                    for visual in mesh:
                        removed_refs.update(proxy_visual(visual))
                    continue
                removed_refs.update(node.get('referent') for node in mesh.iter('Item'))
                for ref in model.findall('./Properties/Ref'):
                    if (ref.get('name') == 'PrimaryPart'
                            and (ref.text or '').strip() == mesh.get('referent')):
                        ref.text = 'null'
                model.remove(mesh)
            converted_house_parts = transform_houses(selected_houses, house_inputs or {})
            # Authoring boundaries and spawn gizmos are never runtime objects.
            # Only remove the reserved Workspace folder, not actual NPC spawns.
            authored_refs = _strip_authoring_markers(tree)
            removed_refs.update(authored_refs)
            runtime_payload = _runtime_payload(rows, snapshot_id=snapshot_id, catalog_digest=catalog_digest,
                                               settings=settings, houses=prepared_houses)
            _apply_workspace_streaming(tree, settings)
            _embed_runtime_manifest(tree, runtime_payload)
            runtime = build_dir / 'runtime_place.rbxlx'
            temp = build_dir / 'runtime_place.tmp'
            tree.write(str(temp), encoding='utf-8', xml_declaration=True)
            os.replace(temp, runtime)
            # Verify that all intended stripped MeshParts are absent and all
            # Collision Parts still exist, from a fresh parse on disk.
            rebuilt = _parse(runtime)
            # Reopen the result and ensure every Workspace setting was serialized
            # with the expected Roblox XML type and value.
            workspace_nodes = [n for n in rebuilt.getroot() if n.tag == 'Item' and n.get('class') == 'Workspace']
            expected_workspace = _apply_workspace_streaming(tree, settings)
            if len(workspace_nodes) != 1:
                raise RuntimeError('Runtime Workspace missing')
            for property_name, (tag, expected_value) in expected_workspace.items():
                prop = _property(workspace_nodes[0], tag, property_name)
                if prop.text != expected_value:
                    raise RuntimeError('Runtime Workspace streaming value mismatch: ' + property_name)
            after_refs = [node.get('referent') for node in _items(rebuilt.getroot())]
            if any(path == 'Workspace.Game1Authoring' or path.startswith('Workspace.Game1Authoring.')
                   for path, _ in _model_paths(rebuilt.getroot())):
                raise RuntimeError('Editor-only Game1Authoring leaked into Runtime Place')
            # Every removed visual referent must also disappear from all Ref
            # properties; a dangling PrimaryPart must never reach Studio.
            if any((ref.text or '').strip() in removed_refs
                   for node in _items(rebuilt.getroot())
                   for ref in node.findall('./Properties/Ref')):
                raise RuntimeError('Runtime XML retains a reference to removed visual')
            added_refs = set(after_refs) - set(before_refs)
            new_marker = [node for node in _items(rebuilt.getroot())
                          if node.get('referent') in added_refs
                          and _name(node) == RUNTIME_MANIFEST_NAME]
            if len(new_marker) != 1 or new_marker[0].get('class') != 'StringValue':
                raise RuntimeError('Compiled runtime manifest marker missing')
            marker_nodes = [new_marker[0], *list(new_marker[0].findall('./Item'))]
            marker_refs = {node.get('referent') for node in marker_nodes}
            if (len(marker_refs) != len(marker_nodes) or added_refs != marker_refs
                    or len(before_refs) - len(after_refs) != len(removed_refs) - len(marker_nodes)
                    or (set(before_refs) - set(after_refs)) != removed_refs):
                raise RuntimeError('Unexpected instances changed during Runtime XML serialization')
            data = _read_embedded_manifest(new_marker[0])
            if data != runtime_payload:
                raise RuntimeError('Compiled runtime placement data differs from validated snapshot')
            index = {}
            for path, node in _model_paths(rebuilt.getroot()):
                if node.get('class') == 'Model':
                    index.setdefault(path, []).append(node)
            for row in rows:
                found = index.get(row['path'], [])
                if len(found) != 1:
                    raise RuntimeError('Runtime root missing: ' + row['path'])
                items = [x for x in found[0] if x.tag == 'Item']
                expected_count = sum(n.get('class') in COLLISION_CLASSES for n in row['hierarchy'])
                from .location_runtime_composite import is_composite
                if is_composite(row):
                    snapshot_visuals = [n for n in row['hierarchy']
                        if n.get('class') == 'MeshPart' and n.get('name') != 'rig_carrier']
                    model_parts = [n for n in found[0].iter('Item') if n is not found[0]
                                   and n.get('class') == 'Part']
                    expected_names = Counter(n['name'] for n in snapshot_visuals)
                    converted = Counter(_name(n) for n in model_parts if _name(n) in expected_names)
                    if converted != expected_names:
                        raise RuntimeError('Runtime composite visual proxies missing: ' + row['path'])
                    # Unmodified server carrier/effect/animation instances
                    # are checked by whole-file referent identity below.
                elif (len(items) != expected_count or
                    any(item.get('class') not in COLLISION_CLASSES or not _name(item).startswith('__Game1Collision_') for item in items)):
                    raise RuntimeError('Runtime collider/root validation failed: ' + row['path'])
            # Verify every managed house MeshPart has become a lightweight
            # technical proxy; refuse a half-compiled Runtime Place.
            if selected_houses:
                nodes = {n.get('referent'):n for n in _items(rebuilt.getroot())}
                for house in selected_houses:
                    for mesh,_path in house['matches'].values():
                        proxy = nodes.get(mesh.get('referent'))
                        if proxy is None or proxy.get('class')!='Part':
                            raise RuntimeError('House visual proxy missing from Runtime XML')
            manifest = {
                'schemaVersion': 1, 'kind': 'game1-location-runtime-draft',
                'snapshotRevision': snapshot_id, 'catalogDigest': catalog_digest,
                'sourceSha256': expected_sha, 'runtimeSha256': _sha(runtime),
                'targets': runtime_payload['targets'], 'modes': runtime_payload['modes'],
                'assetDistances': runtime_payload['assetDistances'], 'hysteresis': settings['hysteresis'], 'workspace': settings['workspace'],
                'removedVisualMeshParts': sum(len(x) if isinstance(x, list) else 1 for _row, _model, x in matched),
                'convertedHouseVisualMeshParts': converted_house_parts,
                'housePlacements': len(selected_houses),
                'untouchedHouseCounts': meta['untouchedHouseCounts'],
                'retainedCollisionModels': sum(any(n.get('class') in COLLISION_CLASSES for n in row['hierarchy']) for row in rows),
                'retainedPlacementRoots': len(rows),
                'removedAuthoringInstances': len(authored_refs), 'publishAllowed': False,
                'placements': rows,
            }
            (build_dir / 'placement_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            (build_dir / 'build_report.json').write_text(json.dumps({
                'snapshotRevision': snapshot_id,
                'backup': str(backup), 'backupSha256': _sha(backup),
                'runtime': str(runtime), 'runtimeSha256': _sha(runtime),
                'placements': len(rows), 'housePlacements': len(selected_houses),
                'convertedHouseVisualMeshParts': converted_house_parts,
                'untouchedHouseCounts': meta['untouchedHouseCounts'],
                'runtimeVisualMarker': RUNTIME_MANIFEST_NAME,
                'removedAuthoringInstances': len(authored_refs),
                'streamingModes': runtime_payload['modes'], 'workspace': settings['workspace'],
                'publishAllowed': False,
                'note': 'Draft only: bounded client FULL/LOD1 pilot embedded; Studio and mobile validation NOT_RUN; publish gate closed',
            }, ensure_ascii=False, indent=2), encoding='utf-8')
            return {'backupPath': str(backup), 'runtimePath': str(runtime),
                    'manifestPath': str(build_dir / 'placement_manifest.json'),
                    'reportPath': str(build_dir / 'build_report.json'),
                    'removedVisualMeshParts': sum(len(x) if isinstance(x, list) else 1 for _row, _model, x in matched), 'convertedHouseVisualMeshParts': converted_house_parts,
                    'housePlacements': len(selected_houses),
                    'untouchedHouseCounts': meta['untouchedHouseCounts'],
                    'removedAuthoringInstances': len(authored_refs),
                    'publishAllowed': False}
        except Exception:
            # On error keep no misleading partial runtime artefacts.
            shutil.rmtree(build_dir, ignore_errors=True)
            raise
