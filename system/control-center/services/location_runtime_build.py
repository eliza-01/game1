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


TARGET_SLUGS = ('stone_fence_02', 'stone_pillar_03')
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


def _verify(source_tree, rows):
    index = {}
    for path, node in _model_paths(source_tree.getroot()):
        if node.get('class') == 'Model':
            index.setdefault(path, []).append(node)
    # An authored Location Model omitted by the Studio registry must never
    # silently survive as an untracked FULL visual in the runtime draft.
    selected_paths = {r['path'] for r in rows}
    for path, nodes in index.items():
        if not path.startswith('Workspace.'):
            continue
        if any(_name(node) == slug or _name(node).startswith(slug + '__')
               for slug in TARGET_SLUGS for node in nodes) and path not in selected_paths:
            raise ValueError('Uninventoried target Location Model in saved Place: ' + path)
    found = []
    removed = set()
    for row in rows:
        path = row['path']
        models = index.get(path, [])
        if len(models) != 1:
            raise ValueError(f'{path}: expected exactly one Model in the saved XML, got {len(models)}')
        model = models[0]
        children = list(model)
        items = [c for c in children if c.tag == 'Item']
        visual = [c for c in items if c.get('class') == 'MeshPart']
        collision = [c for c in items if c.get('class') == 'Part' and _name(c) == '__Game1Collision_Part']
        if len(items) != 2 or len(visual) != 1 or len(collision) != 1:
            raise ValueError(f'{path}: only one MeshPart plus one owned collision Part is supported')
        mesh = visual[0]
        if any(c.tag == 'Item' for c in mesh):
            raise ValueError(f'{path}: nested visual contents are not validated')
        if _mesh_id(mesh) != str(row['meshId']):
            raise ValueError(f'{path}: MeshId differs from the current Studio Snapshot')
        expected = next((v for v in row['hierarchy'] if v.get('class') == 'MeshPart'), None)
        collider = next((v for v in row['hierarchy'] if v.get('class') == 'Part' and
                         v.get('name') == '__Game1Collision_Part'), None)
        if not expected or not collider:
            raise ValueError(f'{path}: snapshot is missing visual or collider geometry')
        if not _near(_cframe(mesh), expected['cframe']) or not _near(_vector3(mesh, 'Size'), expected['size']):
            raise ValueError(f'{path}: source MeshPart transform differs from the latest Scan')
        if not _near(_cframe(collision[0]), collider['cframe']) or not _near(_vector3(collision[0], 'Size'), collider['size']):
            raise ValueError(f'{path}: collision differs from the latest Scan')
        if not row.get('placementId') or row.get('issues') or row.get('ambiguous') or row.get('duplicateId'):
            raise ValueError(f'{path}: unresolved placement diagnostics')
        found.append((row, model, mesh))
        ref = mesh.get('referent')
        if not ref or ref in removed:
            raise ValueError(f'{path}: missing/duplicate MeshPart referent')
        removed.add(ref)
    # Roblox object reference properties pointing at removed visuals must not
    # survive in the runtime Place. A mesh with links is not safe to strip.
    for node in _items(source_tree.getroot()):
        for c in node.findall('./Properties/Ref'):
            if (c.text or '').strip() in removed:
                raise ValueError(f'Visual has external reference from {_name(node)}; cannot strip safely')
    return found


RUNTIME_MANIFEST_NAME = 'Game1LocationRuntimeManifest'
RUNTIME_MANIFEST_KIND = 'game1-location-visual-stream-v1'


def _runtime_payload(rows, *, snapshot_id, catalog_digest):
    """Small immutable client geometry contract from the validated Place Registry.

    The sidecar retains the full audit trail; only one CFrame and Size per
    placement is included in the runtime ReplicatedStorage marker.
    """
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
        raise ValueError('Pilot runtime manifest exceeds maximum placements')
    return {
        'schemaVersion': 1, 'kind': RUNTIME_MANIFEST_KIND,
        'snapshotRevision': snapshot_id, 'catalogDigest': catalog_digest,
        'publishAllowed': False, 'targets': list(TARGET_SLUGS),
        'placements': placements,
    }


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


def build_rows(overview, registry):
    """Fail-closed build input over immutable Place Registry snapshot."""
    snap = overview.get('snapshot') or {}
    if snap.get('freshness') != 'SCANNED_THIS_SESSION' or not snap.get('catalogMatches'):
        raise ValueError('Run Scan Place again in this Control Center session before preparing Runtime')
    report = registry.revisions.get(snap['revisionId'])
    selected = []
    by_slug = {r['slug']:r for r in overview['items']}
    for slug in TARGET_SLUGS:
        asset = by_slug.get(slug)
        if not asset or asset['lod1Status'] != 'PUBLISHED' or not asset['lod1ModelId']:
            raise ValueError(slug + ': a currently published LOD1 is required')
        if asset.get('protectedCount'):
            raise ValueError(slug + ': protected externally owned models must not be stripped')
        selected.extend(r for r in report['placements'] if r['slug'] == slug)
    if not selected:
        raise ValueError('No eligible placement models found')
    for row in selected:
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

    def inspect(self, rows):
        source = self.source.resolve(strict=True)
        if source != self.source or source.suffix.lower() != '.rbxlx':
            raise ValueError('Source must be a regular place/game1_runtime_source.rbxlx, not a symlink')
        tree = _parse(source)
        selected = _verify(tree, rows)
        _runtime_payload(rows, snapshot_id=0, catalog_digest='preflight')
        if any(_name(node) == RUNTIME_MANIFEST_NAME for node in _items(tree.getroot())):
            raise ValueError('Saved authoring Place already contains a Runtime marker')
        if len([node for node in tree.getroot() if node.tag == 'Item'
                and node.get('class') == 'ReplicatedStorage']) != 1:
            raise ValueError('Saved Place must include exactly one ReplicatedStorage service')
        return {'source': str(source), 'sourceSha256': _sha(source),
                'eligible': len(selected), 'counts': {slug: sum(r['slug'] == slug for r in rows) for slug in TARGET_SLUGS},
                'sourceBytes': source.stat().st_size}

    def prepare(self, rows, *, expected_sha, snapshot_id, catalog_digest):
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise ValueError('Run Preflight first')
        meta = self.inspect(rows)
        if expected_sha != meta['sourceSha256']:
            raise ValueError('Saved authoring Place changed since Preflight; run it again')
        tree = _parse(self.source)
        matched = _verify(tree, rows)
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
            removed_refs = {mesh.get('referent') for _row, _model, mesh in matched}
            for _row, model, mesh in matched:
                model.remove(mesh)
            runtime_payload = _runtime_payload(rows, snapshot_id=snapshot_id, catalog_digest=catalog_digest)
            _embed_runtime_manifest(tree, runtime_payload)
            runtime = build_dir / 'runtime_place.rbxlx'
            temp = build_dir / 'runtime_place.tmp'
            tree.write(str(temp), encoding='utf-8', xml_declaration=True)
            os.replace(temp, runtime)
            # Verify that all intended stripped MeshParts are absent and all
            # Collision Parts still exist, from a fresh parse on disk.
            rebuilt = _parse(runtime)
            after_refs = [node.get('referent') for node in _items(rebuilt.getroot())]
            added_refs = set(after_refs) - set(before_refs)
            if (len(before_refs) - len(after_refs) != len(rows) - 1
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
                if len(items) != 1 or items[0].get('class') != 'Part' or _name(items[0]) != '__Game1Collision_Part':
                    raise RuntimeError('Runtime collider/root validation failed: ' + row['path'])
            manifest = {
                'schemaVersion': 1, 'kind': 'game1-location-runtime-draft',
                'snapshotRevision': snapshot_id, 'catalogDigest': catalog_digest,
                'sourceSha256': expected_sha, 'runtimeSha256': _sha(runtime),
                'targets': list(TARGET_SLUGS), 'removedVisualMeshParts': len(rows),
                'retainedCollisionModels': len(rows), 'publishAllowed': False,
                'placements': rows,
            }
            (build_dir / 'placement_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            (build_dir / 'build_report.json').write_text(json.dumps({
                'snapshotRevision': snapshot_id,
                'backup': str(backup), 'backupSha256': _sha(backup),
                'runtime': str(runtime), 'runtimeSha256': _sha(runtime),
                'placements': len(rows), 'runtimeVisualMarker': RUNTIME_MANIFEST_NAME,
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
