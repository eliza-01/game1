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
    """Conservative ownership boundary shared by Inventory and XML Preflight.

    Supports one static visual + SurfaceAppearance, owned Parts of multiple
    shapes, or a strictly non-colliding visual. No rig, attachments or scripts.
    """
    nodes = row.get('hierarchy') or []
    visuals = [n for n in nodes if n.get('class') == 'MeshPart']
    if len(visuals) != 1:
        return 'requires exactly one visual MeshPart (no rig_carrier)'
    if sum(n.get('class') == 'Model' for n in nodes) != 1:
        return 'nested Model hierarchy is not supported for this Runtime build'
    allowed = {'Model', 'MeshPart', 'SurfaceAppearance', *COLLISION_CLASSES}
    if any(n.get('class') not in allowed for n in nodes):
        return 'has rig / attachment / light / nested effects: managed by another system'
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
        if any(_name(model) == slug or _name(model).startswith(slug + '__')
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
    owned_primary_parts = {id(model): mesh.get('referent') for _row, model, mesh in found}
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


def _runtime_payload(rows, *, snapshot_id, catalog_digest, settings=None):
    """Validated published geometry + per-type capability + distance policy.

    This remains compiler-owned data. A runtime client never chooses cloud IDs.
    """
    from .location_streaming_config import DEFAULT_SETTINGS, validate_settings
    settings = validate_settings(settings or DEFAULT_SETTINGS)
    modes = settings['modes']
    targets = sorted({row['slug'] for row in rows})
    if not targets or len(targets) > 64 or any(modes.get(slug, 'off') == 'off' for slug in targets):
        raise ValueError('No valid selected Runtime streaming types')
    placements = []
    for row in rows:
        visual = [entry for entry in row['hierarchy'] if entry.get('class') == 'MeshPart']
        pivot = (row.get('pivotEvidence') or {}).get('modelPivot')
        if len(visual) != 1 or not isinstance(pivot, list) or len(pivot) != 12:
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
        placements.append({
            'id': row['placementId'], 'slug': row['slug'],
            'pivot': pivot, 'cframe': visual[0]['cframe'], 'size': visual[0]['size'],
        })
    if len(placements) > 5000:
        raise ValueError('Runtime manifest exceeds 5000 placements')
    return {
        'schemaVersion': 2, 'kind': RUNTIME_MANIFEST_KIND,
        'snapshotRevision': snapshot_id, 'catalogDigest': catalog_digest,
        'publishAllowed': False, 'targets': targets,
        'modes': {slug: modes[slug] for slug in targets},
        'distances': dict(settings['distances']),
        'placements': placements,
    }


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
    etree.SubElement(props, 'string', name='Value').text = json.dumps(
        payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
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
    active = sorted(slug for slug, mode in settings['modes'].items() if mode != 'off')
    if len(active) > 64:
        raise ValueError('Select at most 64 Location Asset types')
    for slug in active:
        asset = by_slug.get(slug)
        mode = settings['modes'][slug]
        if not asset or not asset.get('count'):
            raise ValueError(slug + ': no recognized placements; disable streaming for this type')
        if asset['fullStatus'] != 'PUBLISHED' or not asset['fullModelId']:
            raise ValueError(slug + ': published FULL model required')
        if mode in ('lod1', 'lod2') and (asset['lod1Status'] != 'PUBLISHED' or not asset['lod1ModelId']):
            raise ValueError(slug + ': published LOD1 required for selected mode')
        if mode == 'lod2' and (asset['lod2Status'] != 'PUBLISHED' or not asset['lod2ModelId']):
            raise ValueError(slug + ': published LOD2 required for selected mode')
        if asset.get('protectedCount'):
            raise ValueError(slug + ': protected externally owned models must not be stripped')
        selected.extend(r for r in report['placements'] if r['slug'] == slug)
    if not selected:
        raise ValueError('Select at least one eligible Location Asset for Runtime streaming')
    for row in selected:
        reason = placement_shape_problem(row)
        if reason:
            raise ValueError(str(row.get('path')) + ': ' + reason)
        if row.get('issues') or row.get('needsCollision') or row.get('needsRecapture') or row.get('ambiguous') or row.get('duplicateId') or not row.get('placementId'):
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

    def inspect(self, rows, settings=None):
        source = self.source.resolve(strict=True)
        if source != self.source or source.suffix.lower() != '.rbxlx':
            raise ValueError('Source must be a regular place/game1_runtime_source.rbxlx, not a symlink')
        from .location_streaming_config import DEFAULT_SETTINGS, validate_settings
        settings = validate_settings(settings or DEFAULT_SETTINGS)
        tree = _parse(source)
        targets = sorted({row['slug'] for row in rows})
        selected = _verify(tree, rows, targets)
        _runtime_payload(rows, snapshot_id=0, catalog_digest='preflight', settings=settings)
        _apply_workspace_streaming(tree, settings)
        if any(_name(node) == RUNTIME_MANIFEST_NAME for node in _items(tree.getroot())):
            raise ValueError('Saved authoring Place already contains a Runtime marker')
        if len([node for node in tree.getroot() if node.tag == 'Item'
                and node.get('class') == 'ReplicatedStorage']) != 1:
            raise ValueError('Saved Place must include exactly one ReplicatedStorage service')
        return {'source': str(source), 'sourceSha256': _sha(source),
                'eligible': len(selected), 'counts': {slug: sum(r['slug'] == slug for r in rows) for slug in targets},
                'sourceBytes': source.stat().st_size}

    def prepare(self, rows, *, expected_sha, snapshot_id, catalog_digest, settings=None):
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise ValueError('Run Preflight first')
        from .location_streaming_config import DEFAULT_SETTINGS, validate_settings
        settings = validate_settings(settings or DEFAULT_SETTINGS)
        meta = self.inspect(rows, settings)
        if expected_sha != meta['sourceSha256']:
            raise ValueError('Saved authoring Place changed since Preflight; run it again')
        tree = _parse(self.source)
        matched = _verify(tree, rows, sorted({r['slug'] for r in rows}))
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
            removed_refs = {node.get('referent') for _row, _model, mesh in matched
                            for node in (mesh, *[c for c in mesh if c.tag == 'Item'])}
            for _row, model, mesh in matched:
                # Null only the verified OWN-visual PrimaryPart pointer. Never
                # remove/retarget any external Ref or modify the authoring file.
                for ref in model.findall('./Properties/Ref'):
                    if (ref.get('name') == 'PrimaryPart'
                            and (ref.text or '').strip() == mesh.get('referent')):
                        ref.text = 'null'
                model.remove(mesh)
            runtime_payload = _runtime_payload(rows, snapshot_id=snapshot_id, catalog_digest=catalog_digest, settings=settings)
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
            # Every removed visual referent must also disappear from all Ref
            # properties; a dangling PrimaryPart must never reach Studio.
            if any((ref.text or '').strip() in removed_refs
                   for node in _items(rebuilt.getroot())
                   for ref in node.findall('./Properties/Ref')):
                raise RuntimeError('Runtime XML retains a reference to removed visual')
            added_refs = set(after_refs) - set(before_refs)
            if (len(before_refs) - len(after_refs) != len(removed_refs) - 1
                    or len(added_refs) != 1 or (set(before_refs) - set(after_refs)) != removed_refs):
                raise RuntimeError('Unexpected instances changed during Runtime XML serialization')
            new_marker = [node for node in _items(rebuilt.getroot())
                          if node.get('referent') in added_refs and node.get('class') == 'StringValue']
            if len(new_marker) != 1 or _name(new_marker[0]) != RUNTIME_MANIFEST_NAME:
                raise RuntimeError('Compiled runtime manifest marker missing')
            data = json.loads(_property(new_marker[0], 'string', 'Value').text or '{}')
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
                if (len(items) != expected_count or
                    any(item.get('class') not in COLLISION_CLASSES or not _name(item).startswith('__Game1Collision_') for item in items)):
                    raise RuntimeError('Runtime collider/root validation failed: ' + row['path'])
            manifest = {
                'schemaVersion': 1, 'kind': 'game1-location-runtime-draft',
                'snapshotRevision': snapshot_id, 'catalogDigest': catalog_digest,
                'sourceSha256': expected_sha, 'runtimeSha256': _sha(runtime),
                'targets': runtime_payload['targets'], 'modes': runtime_payload['modes'],
                'distances': settings['distances'], 'workspace': settings['workspace'],
                'removedVisualMeshParts': len(rows),
                'retainedCollisionModels': sum(any(n.get('class') in COLLISION_CLASSES for n in row['hierarchy']) for row in rows),
                'retainedPlacementRoots': len(rows), 'publishAllowed': False,
                'placements': rows,
            }
            (build_dir / 'placement_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            (build_dir / 'build_report.json').write_text(json.dumps({
                'snapshotRevision': snapshot_id,
                'backup': str(backup), 'backupSha256': _sha(backup),
                'runtime': str(runtime), 'runtimeSha256': _sha(runtime),
                'placements': len(rows), 'runtimeVisualMarker': RUNTIME_MANIFEST_NAME,
                'streamingModes': runtime_payload['modes'], 'workspace': settings['workspace'],
                'publishAllowed': False,
                'note': 'Draft only: bounded client FULL/LOD1 pilot embedded; Studio and mobile validation NOT_RUN; publish gate closed',
            }, ensure_ascii=False, indent=2), encoding='utf-8')
            return {'backupPath': str(backup), 'runtimePath': str(runtime),
                    'manifestPath': str(build_dir / 'placement_manifest.json'),
                    'reportPath': str(build_dir / 'build_report.json'),
                    'removedVisualMeshParts': len(rows), 'publishAllowed': False}
        except Exception:
            # On error keep no misleading partial runtime artefacts.
            shutil.rmtree(build_dir, ignore_errors=True)
            raise
