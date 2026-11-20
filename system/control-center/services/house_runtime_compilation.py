"""Strict house visual extraction for the existing Location Runtime XML compiler.

Only managed authored Workspace roots are eligible. Server-owned parts, bones,
attachments, collision, doors, root instances and all Plot bindings survive.
The compiler changes visual MeshParts into invisible BasePart proxies preserving
identity, CFrame, joints and socket attachment trees; the client creates the
visual mesh independently from the original published Mesh ID.
"""
from __future__ import annotations

import math
import hashlib
import json
import re
from collections import defaultdict
from xml.etree import ElementTree as ET

from .location_runtime_build import _name, _mesh_id, _cframe, _vector3
from .house_runtime_profile import validate as validate_profile, readiness

# Only a qualified, separately published house type can enter the runtime.
MAX_HOUSES = 500
MAX_VISUAL_PARTS = 10000
MAX_MANIFEST_BYTES = 180000  # Roblox StringValue.Value hard cap is 200K
_CFRAME_KEYS = ('X','Y','Z','R00','R01','R02','R10','R11','R12','R20','R21','R22')
_ONLY_MESH = {'MeshContent', 'MeshId', 'MeshID', 'TextureID', 'TextureContent',
              'CollisionFidelity', 'RenderFidelity', 'DoubleSided', 'MeshSize',
              'HasSkinnedMesh', 'FluidFidelity'}
_SAFE_PROPS = {'Name', 'CFrame', 'size', 'Size', 'PivotOffset', 'Anchored',
    'CanCollide', 'CanTouch', 'CanQuery', 'CastShadow', 'Massless',
    'CollisionGroup', 'CollisionGroupId', 'CustomPhysicalProperties',
    'AttributesSerialize', 'Tags', 'RootPriority', 'Locked'}
_ALLOWED_CHILDREN = {'Bone', 'Attachment', 'SurfaceAppearance', 'WrapLayer', 'WrapTarget',
                     'WeldConstraint', 'Weld', 'Motor6D'}


def build_inputs(houses, placements):
    """The Real Estate store, not the Place Registry, owns stable Plot types."""
    authors = {h['slug']:h for h in houses.list()}
    plots = defaultdict(list)
    for row in placements.snapshot()['items']:
        plots[row['houseSlug']].append(row)
    selected = {}
    for slug, house in authors.items():
        profile = house.get('runtimeProfile') or {'mode':'off'}
        if profile.get('mode') == 'off':
            continue
        values = validate_profile(slug, {k:profile[k] for k in ('mode','lod1','hide','hysteresis')})
        # Saved Plot pivots describe future spawn slots, not live instances.
        # Validate publication only for a type actually present in the XML.
        if len(plots[slug]) > 50:
            raise ValueError(f'{slug}: too many Plot placements')
        if any(type(row.get('plotIndex')) is not int or row['plotIndex'] < 1 or row['plotIndex'] > 50
               or type(row.get('worldCFrame')) is not list or len(row['worldCFrame']) != 12
               or row.get('scale',0) <= 0 for row in plots[slug]):
            raise ValueError(f'{slug}: invalid Plot binding')
        selected[slug] = {'house':house, 'profile':values, 'placements':plots[slug]}
    return selected


def _workspace(tree):
    workspaces = [node for node in tree.getroot() if node.tag == 'Item' and node.get('class') == 'Workspace']
    if len(workspaces) != 1:
        raise ValueError('Runtime source needs exactly one Workspace')
    return workspaces[0]


def _walk(node, parents):
    for child in node:
        if child.tag != 'Item':
            continue
        path = parents + (_name(child),)
        yield child, path
        yield from _walk(child, path)


def _get_item(node, name, klass=None):
    found = [c for c in node if c.tag == 'Item' and _name(c) == name
             and (klass is None or c.get('class') == klass)]
    if len(found) != 1:
        raise ValueError(f'{_name(node)}: expected unique {name} ({klass})')
    return found[0]


def _part_option(house, name):
    opts = house.get('meshOptions',{}).get(name)
    if not isinstance(opts,dict) or opts.get('appearanceMode') not in ('material','atlas','material_atlas'):
        raise ValueError(f"{house['slug']}/{name}: missing per-part appearance")
    if opts.get('destructible'):
        raise ValueError(f"{house['slug']}/{name}: destructible MeshPart cannot be streamed")
    return opts


def _asset_id(value, context):
    text = str(value or '')
    if not re.fullmatch(r'[1-9]\d{0,18}', text):
        raise ValueError(f'{context}: missing/invalid published ID')
    return text


def _numbers(values, n):
    return isinstance(values,(list,tuple)) and len(values)==n and all(
        type(v) in (int,float) and math.isfinite(v) and abs(v)<1e9 for v in values)


def _descendants(node):
    for child in node:
        if child.tag=='Item':
            yield child
            yield from _descendants(child)


def _find_parts(root, house):
    """Only a v4 root with one canonical carrier is safe for proxy substitution."""
    static = _get_item(root, 'StaticAssembly', 'Model')
    carrier = _get_item(static, 'rig_carrier', 'MeshPart')
    carrier_bones = { _name(c) for c in _descendants(carrier)
        if c.get('class') in ('Attachment','Bone') }
    parts = {}
    for item,path in _walk(root, ()):
        if item.get('class') != 'MeshPart' or item is carrier:
            continue
        name = _name(item)
        if name in parts or name not in house['meshParts']:
            raise ValueError(f"{house['slug']}: unexpected or duplicate MeshPart {name}")
        if not path or path[0] not in ('StaticAssembly','DoorAssembly'):
            raise ValueError(f"{house['slug']}/{name}: visual is outside managed assemblies")
        for child in _descendants(item):
            if child.get('class') not in _ALLOWED_CHILDREN:
                raise ValueError(f"{house['slug']}/{name}: unsupported nested {child.get('class')}")
            if (path[0] == 'StaticAssembly' and child.get('class') in ('Attachment','Bone')
                    and _name(child).endswith('_socket') and _name(child) not in carrier_bones):
                raise ValueError(f"{house['slug']}/{name}: socket is not in canonical carrier")
        parts[name]=(item,path)
    if set(parts) != set(house['meshParts']):
        raise ValueError(f"{house['slug']}: mismatch between source and published MeshParts: "
                         f"{sorted(set(house['meshParts'])-set(parts))}")
    return carrier,parts


def _proxy(mesh, no_collide):
    """Shared visual proxy, with the existing house collision policy."""
    from .runtime_visual_proxy import convert
    removed = convert(mesh, expected_collide=not no_collide, fill_missing_physics=True)
    props = mesh.find('Properties')
    for key, value in (('CanTouch', not no_collide), ('CanQuery', not no_collide)):
        for prop in props:
            if prop.get('name') == key:
                prop.text = str(value).lower()
                break
    return removed


def _coordinates_close(a,b):
    # The world position may differ by minor saved-XML rounding, but applying
    # a mismatched orientation to EVERY door/socket would be catastrophic.
    return (_numbers(a,12) and _numbers(b,12)
            and all(abs(a[i]-b[i]) < 0.35 for i in range(3))
            and all(abs(a[i]-b[i]) < 0.02 for i in range(3,12)))



def _compose_frame(parent, relative):
    """Roblox CFrame multiplication without Euler angle decomposition."""
    if not _numbers(parent,12) or not _numbers(relative,12):
        raise ValueError('invalid Plot / anchor frame')
    out = [parent[axis] + sum(parent[3+axis*3+k]*relative[k] for k in range(3))
           for axis in range(3)]
    out += [sum(parent[3+r*3+k]*relative[3+k*3+c] for k in range(3))
            for r in range(3) for c in range(3)]
    return out


def inspect(tree, selected):
    """Preflight on saved XML. Never edits authoring source or registered Plots."""
    if not selected:
        return []
    workspace=_workspace(tree)
    found=defaultdict(list)
    for node,path in _walk(workspace, ('Workspace',)):
        if node.get('class') != 'Model' or _name(node) not in selected:
            continue
        # Any registered type appearing outside the canonical structure fails
        # rather than getting stripped partially or accidentally duplicated.
        found[_name(node)].append((node,path))
    result=[]
    for slug,item in selected.items():
        house=item['house']; rows=found[slug]
        # The authoring XML is a snapshot of actual instances. A registered
        # Plot pivot is independent of whether a house currently occupies it.
        if rows:
            blockers = readiness(house, item['profile'], house['lod1'])['warnings']
            if blockers:
                raise ValueError(f'{slug}: ' + '; '.join(blockers))
        seen_plots=set()
        for model,path in rows:
            carrier,parts=_find_parts(model,house)
            # Match the serialized Model pivot to its immutable Plot binding.
            # rig_carrier is a socket owner, not an authoring placement pivot.
            # The Plot binding stores Model:GetPivot(), not the CFrame of
            # rig_carrier. A carrier may be offset and rotated relative to the
            # house's authored pivot (notably the 90-degree Blender axis basis).
            # Compare the serialized MODEL pivot before matching any Plot.
            model_pivot = model.find('./Properties/OptionalCoordinateFrame[@name="WorldPivotData"]/CFrame')
            if model_pivot is None:
                raise ValueError(f'{slug}: authored Model WorldPivotData missing in saved Place')
            try:
                frame = [float(model_pivot.findtext(key)) for key in _CFRAME_KEYS]
            except (TypeError, ValueError) as exc:
                raise ValueError(f'{slug}: invalid serialized house WorldPivotData') from exc
            if not _numbers(frame, 12):
                raise ValueError(f'{slug}: invalid serialized house WorldPivotData')
            if len(path) != 5 or path[:2] != ('Workspace','Plots') or path[3] != 'Houses' or not path[2].isdigit():
                raise ValueError(f'{slug}: house is outside canonical Workspace.Plots.<index>.Houses')
            plot_index=int(path[2])
            if not 1 <= plot_index <= 50 or plot_index in seen_plots:
                raise ValueError(f'{slug}: invalid/duplicate authored Model at Plot {plot_index:02d}')
            seen_plots.add(plot_index)
            # Current visuals use their authored Model pivot/scale, NOT a
            # historical pivot saved for a potentially different house type.
            model_scale=model.find('./Properties/float[@name="ScaleFactor"]')
            try:
                scale=float(model_scale.text) if model_scale is not None else 1.0
            except (TypeError, ValueError) as exc:
                raise ValueError(f'{slug}: invalid authored Model ScaleFactor') from exc
            if not math.isfinite(scale) or not 0.001 <= scale <= 1000:
                raise ValueError(f'{slug}: invalid authored Model ScaleFactor')
            visuals=[]
            for name,(mesh,local_path) in sorted(parts.items()):
                opts=_part_option(house,name)
                if opts.get('noCollide') is not True and opts.get('collisionFidelity') != 'Box':
                    raise ValueError(f'{slug}/{name}: collidable mesh requires Box fidelity for proxy')
                texture=house.get('textures',{}).get(name,{})
                atlas = ''
                if opts['appearanceMode'] != 'material':
                    atlas = _asset_id(texture.get('assetId'),slug+'/'+name+' texture')
                mesh_id=_mesh_id(mesh)
                cf=list(_cframe(mesh));size=list(_vector3(mesh,'Size'))
                if not _numbers(cf,12) or not _numbers(size,3) or min(size)<=0:
                    raise ValueError(f'{slug}/{name}: invalid mesh geometry')
                limit=opts.get('loadDistanceStuds',50) if opts.get('distanceStreaming') else item['profile']['lod1']
                if type(limit) not in (float,int) or not math.isfinite(limit):
                    raise ValueError(f'{slug}/{name}: invalid streaming distance')
                # In FULL-only mode parts not explicitly bounded exist until
                # house hide threshold; LOD1 forces ALL full meshes away.
                if opts.get('distanceStreaming') is not True:
                    limit=item['profile']['lod1'] if item['profile']['mode']=='lod1' else item['profile']['hide']
                visual={'name':name,'meshId':mesh_id,'textureId':atlas,'mode':opts['appearanceMode'],
                    'material':opts.get('visualMaterial') or 'SmoothPlastic',
                    'color':opts.get('visualColor') or '#FFFFFF',
                    'doubleSided':opts.get('doubleSided') is True,
                    'alpha':opts.get('alphaEnabled') is True,
                    'distance':int(limit), 'cframe':cf,'size':size,'path':list(local_path),
                    'moving':local_path[0]=='DoorAssembly'}
                if visual['alpha'] and not atlas:
                    raise ValueError(f'{slug}/{name}: alpha needs published atlas')
                visuals.append(visual)
            result.append({'slug':slug,'plotIndex':plot_index,
                'path':list(path[1:]),'pivot':frame,
                'scale':scale,'parts':visuals, 'model':model,
                'matches':parts})
    if len(result)>MAX_HOUSES:
        raise ValueError('Too many instantiated Real Estate houses for Runtime')
    if sum(len(r['parts']) for r in result)>MAX_VISUAL_PARTS:
        raise ValueError('Too many Real Estate MeshParts for runtime manifest')
    return result


def transform(rows, selected):
    """Replace visuals with technical proxies ONLY in the isolated Runtime tree."""
    converted=0
    for row in rows:
        house=selected[row['slug']]['house']
        for name,(mesh,_path) in row['matches'].items():
            _proxy(mesh,_part_option(house,name).get('noCollide') is True)
            converted+=1
    return converted


def _inverse_frame(frame):
    """Invert a rigid CFrame (transpose 3x3) without Euler decomposition."""
    r = [frame[3+i:6+i] for i in (0,3,6)]
    inverse_rotation = [[r[c][row] for c in range(3)] for row in range(3)]
    position = [-sum(inverse_rotation[i][k]*frame[k] for k in range(3)) for i in range(3)]
    return position + [v for line in inverse_rotation for v in line]


def _local_part(world, pivot, scale):
    local = _compose_frame(_inverse_frame(pivot), world)
    return [v/scale if i<3 else v for i,v in enumerate(local)]


def payload(rows, selected):
    """One immutable visual definition per HOUSE TYPE, not per Plot.

    39 copies of 16 parts can exceed Roblox StringValue's 200,000 character
    limit. Store local authored transforms once, and only per-Plot pivot/scale.
    Any per-Plot visual deviation fails Preflight instead of being normalized.
    """
    types = {}
    active_slugs={row['slug'] for row in rows}
    for slug, entry in sorted(selected.items()):
        if slug not in active_slugs:
            continue
        profile=entry['profile']
        types[slug] = {'mode':profile['mode'],'lod1':profile['lod1'],
            'hide':profile['hide'],'hysteresis':profile['hysteresis'],
            'lod1ModelAssetId':str(entry['house']['lod1'].get('modelAssetId') or ''),
            'parts':[]}
    assigned={}
    placements=[]
    for row in rows:
        slug=row['slug']; scale=row['scale']; expected=assigned.get(slug)
        descriptions=[]
        for part in row['parts']:
            record={k:v for k,v in part.items() if k not in ('cframe','size')}
            record['cframe'] = _local_part(part['cframe'], row['pivot'],scale)
            record['size'] = [v/scale for v in part['size']]
            descriptions.append(record)
        if expected is None:
            types[slug]['parts']=descriptions
            assigned[slug]=descriptions
        elif len(expected)!=len(descriptions):
            raise ValueError(slug+': inconsistent MeshPart count between Plots')
        else:
            for old,new in zip(expected,descriptions):
                if any(old[k]!=new[k] for k in old if k not in ('cframe','size')):
                    raise ValueError(slug+'/'+new['name']+': inconsistent MeshPart properties on Plots')
                if (not _coordinates_close(old['cframe'],new['cframe'])
                        or not all(abs(a-b) < 0.05 for a,b in zip(old['size'],new['size']))):
                    raise ValueError(slug+'/'+new['name']+': inconsistent authored transforms on Plots')
        placements.append({key:row[key] for key in ('slug','plotIndex','path','pivot','scale')})
    result={'types':types,'placements':placements}
    # Even in the presence of many types, fail before writing an illegal
    # Roblox StringValue. The final envelope is checked in the builder.
    return result


def fingerprint(selected):
    """Preflight invalidation includes EVERY visual, atlas, LOD and Plot revision.

    A mesh color/atlas change may not advance a Real Estate type revision, so
    the digest must cover the actual persisted source fields, not just slugs.
    """
    records = []
    for slug, item in sorted(selected.items()):
        h = item['house']
        records.append({
            'slug':slug, 'profile':item['profile'], 'revision':h['revision'],
            'modelSha':h.get('model_sha256'), 'meshParts':h['meshParts'],
            'meshOptions':h.get('meshOptions'),
            'textures':{k:v.get('assetId') for k,v in h.get('textures',{}).items()},
            'rigAssets':h.get('rigAssets'), 'lod1':h.get('lod1'),
            'placements':[{k:r.get(k) for k in ('plotIndex','worldCFrame','houseAnchorLocalCFrame','scale','revision')}
                for r in item['placements']],
        })
    return hashlib.sha256(json.dumps(records,sort_keys=True,ensure_ascii=False,
                       separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()
