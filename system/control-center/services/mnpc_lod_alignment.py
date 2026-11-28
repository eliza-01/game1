"""Offline, revision-pinned alignment of a published static MNPC mesh.

Reference vertices are read from the immutable M636 FBX (Blender Z-up),
then converted back to navigation-root studs. No fitting to FULL bounds,
no guessed pivot and no Runtime or Place mutation.
"""
from itertools import permutations, product
import math

from .fbx_blender_report import inspect_report
from .model_lod_common import check_revision, verified_source
from .mnpc_lod_capture import asset_id, digest
from .mnpc_capture_bridge import request_studio
from . import mnpc_lod_geometry as geometry

MAX_VERTICES = 20000


def vector(value, *, positive=False):
    if not isinstance(value, list) or len(value) != 3 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>1000000 or (positive and x<=0) for x in value):
        raise ValueError('Invalid MNPC alignment vector')
    return tuple(value)


def points(value):
    if not isinstance(value,list) or not 4<=len(value)<=MAX_VERTICES:
        raise ValueError('Invalid MNPC alignment vertex count')
    unique = sorted(set(vector(p) for p in value))
    if len(unique) < 4:
        raise ValueError('Degenerate MNPC alignment vertices')
    return unique


def bounds(p):
    lo=tuple(min(v[i] for v in p) for i in range(3))
    hi=tuple(max(v[i] for v in p) for i in range(3))
    span=tuple(b-a for a,b in zip(lo,hi))
    if min(span)<=1e-6: raise ValueError('Degenerate MNPC alignment geometry')
    return tuple((a+b)/2 for a,b in zip(lo,hi)),span


def _grid(vertices, cell):
    out={}
    for p in vertices:
        key=tuple(math.floor(x/cell) for x in p)
        out.setdefault(key,[]).append(p)
    return out


_NEIGHBORS=list(product((-1,0,1),repeat=3))


def _error(vertices, grid, tol):
    maximum=0
    for p in vertices:
        key=tuple(math.floor(x/tol) for x in p)
        best=math.inf
        for delta in _NEIGHBORS:
            for q in grid.get(tuple(a+b for a,b in zip(key,delta)),()):
                best=min(best, sum((a-b)**2 for a,b in zip(p,q)))
        if best>tol*tol: return None
        maximum=max(maximum,best)
    return math.sqrt(maximum)


def fit(reference, imported, size):
    """Fit proper signed axis permutations + uniform positive scale + translation.

    Compare both point sets, not only bounds. Reject symmetry/ambiguity, reflection,
    anisotropic scale and geometry drift. Runtime receives a proper CFrame + Size.
    """
    ref=points(reference); actual=points(imported); size=vector(size,positive=True)
    rc,rs=bounds(ref); ac,aspan=bounds(actual)
    tol=max(.001,min(.02,math.sqrt(sum(v*v for v in rs))*.0005))
    grid=_grid(ref,tol); matches=[]
    for perm in permutations(range(3)):
        parity=(-1)**sum(perm[i]>perm[j] for i in range(3) for j in range(i+1,3))
        ratios=[rs[i]/aspan[perm[i]] for i in range(3)]
        scale=sum(ratios)/3
        if not 1e-5<=scale<=1e5 or any(abs(r/scale-1)>.002 for r in ratios): continue
        for signs in product((-1,1),repeat=3):
            if parity*math.prod(signs)!=1: continue
            offset=[rc[i]-scale*signs[i]*ac[perm[i]] for i in range(3)]
            mapped=[tuple(scale*signs[i]*p[perm[i]]+offset[i] for i in range(3)) for p in actual]
            a=_error(mapped,grid,tol)
            if a is None: continue
            b=_error(ref,_grid(mapped,tol),tol)
            if b is None: continue
            rotation=[signs[i] if j==perm[i] else 0 for i in range(3) for j in range(3)]
            matches.append({'rootCFrame':offset+rotation,'size':[v*scale for v in size],
                'scale':scale,'maxVertexError':max(a,b),'tolerance':tol})
    if len(matches)!=1:
        raise ValueError('MNPC import alignment ' + ('ambiguous (symmetric geometry)' if matches else 'failed (orientation, scale or geometry mismatch)'))
    result=matches[0]
    vector(result['size'],positive=True)
    if any(not .001 <= v <= 2048 for v in result['size']):
        raise ValueError('MNPC aligned size outside Roblox MeshPart limits')
    return result


def reference_points(owner, current):
    source=verified_source(owner.root,current)
    report=inspect_report(owner.root,'inspect_mnpc_alignment_fbx.py',source,label='MNPC alignment reference')
    inspected=geometry.validate(report)
    if inspected != {k:current['geometry'][k] for k in inspected}:
        raise ValueError('MNPC FBX report changed; restage current source')
    raw=points(report.get('points'))
    center,span=bounds(raw)
    if any(abs(center[i]-span[i]/2-inspected['boundsMin'][i])>1e-5 or
           abs(center[i]+span[i]/2-inspected['boundsMax'][i])>1e-5 for i in range(3)):
        raise ValueError('MNPC reference vertices differ from inspected bounds')
    # Inverse of M636 assemble [x,-z,y]. Blender world axes, not FBX axes.
    return [[x,z,-y] for x,y,z in raw]


def identity(current):
    return {key:current[key] for key in ('kind','slug','revision','fullFingerprint','sourceSha256','modelAssetId','imageAssetId')}


def verify(owner, kind, slug, payload, *, bridge=None, reference=None):
    if not isinstance(payload,dict) or set(payload)!={'expectedRevision'}:
        raise ValueError('MNPC alignment requires expectedRevision only')
    with owner._lock:
        current=owner.describe(kind,slug)
        check_revision(payload['expectedRevision'],current['revision'])
        if current['status']!='PUBLISHED': raise ValueError('Publish current MNPC LOD1 before import verification')
        recipe=(current.get('geometry') or {}).get('preparation') or {}
        if recipe.get('mode')!='captured_idle' or recipe.get('rootSpace')!='roblox_navigation_studs_y_up':
            raise ValueError('Automatic alignment requires M636 captured-idle root-space FBX; capture and bake first')
        pinned=identity(current)
        ref=(reference or reference_points)(owner,current)
        request={**pinned,'expectedRevision':current['revision']}
        imported=(bridge or import_from_studio)(request)
        if not isinstance(imported,dict) or set(imported)!={'meshId','size','meshSize','vertices','triangles'}:
            raise ValueError('Invalid Studio MNPC import report')
        mesh_id=asset_id(imported['meshId'])
        if type(imported['triangles']) is not int or imported['triangles']!=current['geometry']['triangles']:
            raise ValueError('MNPC imported triangle count changed')
        vector(imported['meshSize'],positive=True)
        placement=fit(ref,imported['vertices'],imported['size'])
        fresh=owner.describe(kind,slug)
        if fresh['status']!='PUBLISHED' or identity(fresh)!=pinned:
            raise ValueError('MNPC publication changed during import; refresh')
        result={'schemaVersion':1,'identity':pinned,'meshId':mesh_id,'meshSize':imported['meshSize'],
            'triangles':imported['triangles'],'referenceSha256':digest(ref),**placement}
        owner.record_alignment(kind,slug,current['revision'],result)
        return owner.describe(kind,slug)


def import_from_studio(payload):
    return request_studio(payload,command_name='mnpc-align-v1',result_path='/mnpc-align-result',
        identity_keys=('kind','slug','revision','fullFingerprint','sourceSha256','modelAssetId','imageAssetId','expectedRevision'),
        result_key='alignment',timeout_seconds=90)
