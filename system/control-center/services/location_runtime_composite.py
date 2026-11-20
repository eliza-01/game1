"""Composite Location Asset Runtime policy.

A Location's rig_carrier and *all* of its Bone/Attachment/effect descendants
remain server-owned. Every visible MeshPart is replaced with an invisible
Part preserving its referent, joints and effect attachment tree; one local
visual can later be restored per named proxy from the same published model.
No animation, socket, collider, fire or light is authored/reconstructed here.
"""
from collections import Counter

from .runtime_visual_proxy import bool_property

MAX_VISUALS = 64


def is_composite(row):
    nodes = row.get('hierarchy') or []
    return (sum(n.get('class') == 'MeshPart' for n in nodes) > 1
            or any(n.get('class') in ('Bone','Attachment','Animator','AnimationController',
                                    'ParticleEmitter','Fire','PointLight','SpotLight',
                                    'SurfaceLight','Smoke','Sparkles','Beam','Trail')
                   for n in nodes))


def structure_problem(row):
    nodes = row.get('hierarchy') or []
    visuals = [n for n in nodes if n.get('class') == 'MeshPart'
               and n.get('name') != 'rig_carrier']
    carriers = [n for n in nodes if n.get('class') == 'MeshPart'
                and n.get('name') == 'rig_carrier']
    if not 1 <= len(visuals) <= MAX_VISUALS:
        return 'composite needs 1–64 named visual MeshParts'
    if len(carriers) > 1:
        return 'composite has duplicate rig_carrier'
    if len({n.get('name') for n in visuals}) != len(visuals):
        return 'composite has duplicate visual MeshPart names'
    if sum(n.get('class') == 'Model' for n in nodes) != 1:
        return 'nested Model hierarchy requires an explicit renderer contract'
    if any(n.get('class') in ('Script','LocalScript','ModuleScript') for n in nodes):
        return 'composite contains executable scripts; cannot move visual roots safely'
    for n in nodes:
        if n.get('class') == 'MeshPart' and n.get('name') != 'rig_carrier':
            if n.get('canCollide') and n.get('collisionFidelity') not in (
                'Enum.CollisionFidelity.Box','Box'):
                return 'collidable visual is not Box fidelity; Part proxy would change physics'
    if not row.get('placementId') or row.get('issues') or row.get('ambiguous') or row.get('duplicateId'):
        return 'unresolved placement identity/Studio diagnostics'
    return ''


def validate_xml(model, row, *, name, cframe, vector3, mesh_id, near):
    """Match every visual by unique name and current Scan mesh ID/transform.

    Also check *all* source descendants against their recorded class/name
    parent relationship; a stale or partial Scan cannot authorize stripping.
    """
    snapshot = row['hierarchy']
    if not snapshot or snapshot[0].get('class') != 'Model':
        raise ValueError(f"{row['path']}: missing scanned Model root")
    actual = []
    def visit(node, parent):
        index = len(actual) + 1
        actual.append((node, parent))
        for child in node:
            if child.tag == 'Item': visit(child, index)
    visit(model,None)
    if len(actual) != len(snapshot):
        raise ValueError(f"{row['path']}: composite hierarchy differs from Scan")
    def triples(recorded):
        return [(r['class'],r['name'],r.get('parent')) for r in recorded]
    expected = triples(snapshot)
    observed = [(node.get('class'),name(node),parent) for node,parent in actual]
    # Studio's GetDescendants and Roblox XML child serialization may order
    # siblings differently. Validate parent identity via named ancestry.
    def signatures(nodes):
        paths=[]
        for i,(klass,nm,parent) in enumerate(nodes):
            if parent is None:
                path=(klass,nm)
            else:
                idx=parent - 1
                if not 0 <= idx < len(paths):
                    raise ValueError('Invalid composite hierarchy parent index')
                path=paths[idx]+(klass,nm)
            paths.append(path)
        return Counter(paths)
    if signatures(expected) != signatures(observed):
        raise ValueError(f"{row['path']}: hierarchy/rig/effect structure differs from Scan")
    visuals=[]
    expected_vis={n['name']:n for n in snapshot if n['class']=='MeshPart' and n['name']!='rig_carrier'}
    for item, _parent in actual:
        if item.get('class') == 'MeshPart' and name(item)=='rig_carrier':
            carrier = next((n for n in snapshot if n['class']=='MeshPart'
                            and n['name']=='rig_carrier'),None)
            if not carrier or mesh_id(item) != str(carrier.get('meshId')):
                raise ValueError(f"{row['path']}: carrier identity differs from Scan")
            if not near(cframe(item),carrier.get('cframe') or ()) or not near(vector3(item,'Size'),carrier.get('size') or ()):
                raise ValueError(f"{row['path']}: carrier transform differs from Scan")
        if item.get('class') in ('Part','WedgePart','CornerWedgePart'):
            collider = next((n for n in snapshot if n['class']==item.get('class')
                             and n['name']==name(item)),None)
            if not collider or not near(cframe(item),collider.get('cframe') or ()) or not near(vector3(item,'Size'),collider.get('size') or ()):
                raise ValueError(f"{row['path']}: collision geometry differs from Scan")
            for prop, field in (('CanCollide','canCollide'),('CanQuery','canQuery')):
                if bool_property(item,prop) != (collider.get(field) is True):
                    raise ValueError(f"{row['path']}: collision flags differ from Scan")
        if item.get('class') != 'MeshPart' or name(item)=='rig_carrier': continue
        spec=expected_vis.pop(name(item),None)
        if not spec or mesh_id(item) != str(spec.get('meshId')):
            raise ValueError(f"{row['path']}: unexpected MeshPart/Mesh ID {name(item)}")
        if not near(cframe(item),spec.get('cframe') or ()) or not near(vector3(item,'Size'),spec.get('size') or ()):
            raise ValueError(f"{row['path']}/{name(item)}: transform differs from Scan")
        if bool_property(item,'CanCollide') != (spec.get('canCollide') is True):
            raise ValueError(f"{row['path']}/{name(item)}: collision differs from Scan")
        # The client will recreate a visual alongside the *same* proxy and
        # server rig. Never delete effects, bones or attachments in XML.
        visuals.append(item)
    if expected_vis:
        raise ValueError(f"{row['path']}: missing visual components {sorted(expected_vis)}")
    return visuals


def component_manifest(row):
    # Paths are at most two layers deep in the supported v1 composite contract;
    # a caller must first validate the source XML against the Studio snapshot.
    visuals=[]
    for n in row['hierarchy']:
        if n.get('class') == 'MeshPart' and n.get('name') != 'rig_carrier':
            visuals.append({'name':n['name'], 'meshId':str(n['meshId']),
                'cframe':list(n['cframe']), 'size':list(n['size']),
                'collidable':n.get('canCollide') is True})
    return visuals
