"""Captured posed triangles -> shared color atlas + single static FBX.

Offline authoring only. No source asset download or mutation. Resolve only
registered texture bytes, pinned by the M635 FULL/equipment identity.
"""
from pathlib import Path
import json
import math
import tempfile

from PIL import Image, ImageChops
from .fbx_blender_report import run_report
from .model_lod_common import check_revision, sha256
from . import mnpc_lod_geometry as geometry

MAX_TRIANGLES = 30000
FIELDS = {'expectedRevision', 'fullFingerprint', 'captureSha256', 'targetTriangles', 'textureSize'}


def _vec(value, n, lo, hi):
    if not isinstance(value, list) or len(value) != n or any(type(x) not in (float,int) or not math.isfinite(x) or not lo <= x <= hi for x in value):
        raise ValueError('Invalid captured geometry vector')
    return value


def validate_pieces(pieces, meshes):
    if not isinstance(pieces, list) or len(pieces) != len(meshes):
        raise ValueError('Captured geometry must cover every visible mesh')
    records = {m['path']: m for m in meshes}
    total = 0
    for p in pieces:
        if not isinstance(p,dict) or set(p) != {'path','vertices','uvs','triangles','tint','alphaMode'} or not isinstance(p['path'],str) or p['path'] not in records:
            raise ValueError('Unknown or duplicate captured geometry piece')
        m = records.pop(p['path'])
        if m['transparency'] != 0:
            raise ValueError('Partial MeshPart transparency is unsupported in automatic bake')
        if p['alphaMode'] not in ('Texture','Overlay','Transparency') or (m['colorMap'] != '') != (p['alphaMode'] != 'Texture'):
            raise ValueError('Invalid captured texture mode')
        _vec(p['tint'],3,0,1)
        vs, uv, fs = p['vertices'], p['uvs'], p['triangles']
        if not all(isinstance(a,list) for a in (vs,uv,fs)) or not 1 <= len(fs) <= MAX_TRIANGLES or not 3 <= len(vs) <= len(fs)*3 or not 1 <= len(uv) <= len(fs)*3:
            raise ValueError('Invalid captured topology counts')
        total += len(fs)
        if total > MAX_TRIANGLES:
            raise ValueError('Captured assembly exceeds triangle budget')
        for v in vs: _vec(v,3,-100000,100000)
        for v in uv: _vec(v,2,-.00001,1.00001)
        for f in fs:
            if not isinstance(f,list) or len(f) != 6 or any(type(i) is not int or not 1 <= i <= (len(vs) if k < 3 else len(uv)) for k,i in enumerate(f)) or len(set(f[:3])) != 3:
                raise ValueError('Invalid captured triangle/corner index')
    return total


def _texture_sources(owner, kind, slug, full):
    rows = {'body': owner._actor(kind,slug)}
    identities = {'body':full}
    for hand, entry in full.get('equipment',{}).items():
        if entry:
            rows[hand] = owner.weapons.get(entry['slug'])
            identities[hand] = entry['visual']
    result = {}
    for key, row in rows.items():
        identity = identities[key]['textures']
        if isinstance(identity, dict):
            binding = row.get('atlas_binding') or {}
            if binding.get('variant_id') != identity['variantId'] or str(binding.get('published_id')) != str(identity['imageId']) or binding.get('source_sha256') != identity['sha256']:
                raise ValueError('Registered atlas changed; recapture FULL')
            entries = [(str(identity['imageId']), identity['sha256'], binding.get('source_path'))]
        else:
            entries = []
            for pinned in identity:
                matched = [t for t in row.get('textures',[]) if t['slot']==pinned['slot'] and str(t['asset_id'])==str(pinned['imageId']) and t['sha256']==pinned['sha256']]
                if len(matched)!=1:
                    raise ValueError('Registered texture changed; recapture FULL')
                t=matched[0]
                entries.append((str(pinned['imageId']), pinned['sha256'], t.get('prepared_path') or t.get('source_path')))
        for image_id, digest, path in entries:
            if not path:
                raise ValueError(f'Missing registered texture source: {key}/{image_id}')
            source=(owner.root / path).resolve()
            if not source.is_relative_to(owner.root):
                raise ValueError('Registered texture source outside project')
            lookup=(key,image_id)
            if lookup in result and result[lookup]!=(source,digest):
                raise ValueError('Ambiguous registered texture bytes')
            result[lookup]=(source,digest)
    return result


def _appearance_key(piece, mesh):
    return (mesh['owner'], mesh['colorMap'] or mesh['textureId'], tuple(round(c*255) for c in piece['tint']), piece['alphaMode'])


def _read_image(key, sources):
    owner, image_id, tint, alpha_mode = key
    if not image_id:
        return Image.new('RGBA',(4,4),(*tint,255))
    if (owner,image_id) not in sources:
        raise ValueError(f'Missing registered image {owner}/{image_id}')
    path, expected = sources[(owner,image_id)]
    if not path.is_file() or not 0 < path.stat().st_size <= 20*1024*1024 or sha256(path)!=expected:
        raise ValueError(f'Registered texture bytes changed or exceed budget: {path.name}')
    try:
        with Image.open(path) as source:
            if source.format not in ('PNG','JPEG','WEBP') or not all(1<=n<=4096 for n in source.size):
                raise ValueError(f'Unsupported registered color texture: {path.name}')
            rgba=source.convert('RGBA')
    except (OSError,Image.DecompressionBombError) as error:
        raise ValueError(f'Cannot read registered color texture: {path.name}') from error
    if sha256(path)!=expected:
        raise ValueError('Texture changed during read')
    alpha=rgba.getchannel('A')
    if alpha_mode=='Overlay' and alpha.getextrema()[0]!=255:
        raise ValueError('SurfaceAppearance Overlay alpha requires a separate material bake')
    rgb=ImageChops.multiply(rgba.convert('RGB'),Image.new('RGB',rgba.size,tint))
    rgb.putalpha(alpha)
    return rgb


def _pad(atlas, image, x, y, gutter):
    """Extrude all four edges and corners, including alpha, into the gutter."""
    w,h=image.size
    atlas.paste(image,(x,y))
    for box, size, dest in [((0,0,1,h),(gutter,h),(x-gutter,y)),((w-1,0,w,h),(gutter,h),(x+w,y)),
        ((0,0,w,1),(w,gutter),(x,y-gutter)),((0,h-1,w,h),(w,gutter),(x,y+h))]:
        atlas.paste(image.crop(box).resize(size),(dest))
    for ix,dx in ((0,x-gutter),(w-1,x+w)):
        for iy,dy in ((0,y-gutter),(h-1,y+h)):
            atlas.paste(image.crop((ix,iy,ix+1,iy+1)).resize((gutter,gutter)),(dx,dy))


def assemble(capture, sources, size, output):
    pieces, meshes = capture['geometry'], {m['path']:m for m in capture['meshes']}
    total=validate_pieces(pieces,capture['meshes'])
    keys={p['path']:_appearance_key(p,meshes[p['path']]) for p in pieces}
    # Deduplicate equivalent source bytes + tint, even across body/weapon owners.
    def identity(key):
        if not key[1]: return ('solid', key[2], key[3])
        if key[:2] not in sources: raise ValueError('Captured texture source missing')
        return (sources[key[:2]][1],key[2],key[3])
    unique={}
    # Verify every referenced path even if two independent registrations have
    # the same expected digest and therefore share a tile.
    used={key[:2] for key in keys.values() if key[1]}
    for key in used:
        if key not in sources or not sources[key][0].is_file() or sha256(sources[key][0])!=sources[key][1]:
            raise ValueError(f'Registered texture missing or changed: {key[0]}/{key[1]}')
    for key in keys.values(): unique.setdefault(identity(key),key)
    count=len(unique); cols=math.ceil(math.sqrt(count)); rows=math.ceil(count/cols)
    cell=min(size//cols,size//rows); gutter=2
    if cell-2*gutter < 16:
        raise ValueError('Atlas too small for captured materials; choose larger atlas')
    atlas=Image.new('RGBA',(size,size),(0,0,0,0)); rects={}
    for i,(ident,key) in enumerate(unique.items()):
        image=_read_image(key,sources)
        image.thumbnail((cell-2*gutter,cell-2*gutter),Image.Resampling.LANCZOS)
        x=(i%cols)*cell+gutter; y=(i//cols)*cell+gutter
        _pad(atlas,image,x,y,gutter)
        rects[ident]=(x,y,*image.size)
    # Roblox UV convention: image top-left; Blender UV bottom-left. Native
    # import/alignment still requires Studio comparison, no inferred scale.
    vertices=[]; faces=[]; face_uv=[]
    for p in pieces:
        offset=len(vertices); x,y,w,h=rects[identity(keys[p['path']])]
        vertices.extend([[a,-c,b] for a,b,c in p['vertices']])
        for f in p['triangles']:
            faces.append([offset+i-1 for i in f[:3]])
            corners=[]
            for i in f[3:]:
                u,v=p['uvs'][i-1];u=max(0,min(1,u));v=max(0,min(1,v))
                corners.append([(x+.5+u*(w-1))/size,1-(y+.5+v*(h-1))/size])
            face_uv.append(corners)
    atlas.save(output,format='PNG')
    return {'vertices':vertices,'faces':faces,'faceUV':face_uv},total,count


def bake(owner, kind, slug, payload, animations):
    from . import mnpc_lod_capture as capture_module
    if not isinstance(payload,dict) or set(payload)!=FIELDS:
        raise ValueError('Bake requires capture checksum, current FULL/LOD revision and budgets')
    target, size=payload['targetTriangles'],payload['textureSize']
    if type(target) is not int or not 100<=target<=10000 or type(size) is not int or size not in (128,256,512,1024):
        raise ValueError('Invalid LOD1 triangle or atlas budget')
    with owner._lock:
        current=owner.describe(kind,slug)
        check_revision(payload['expectedRevision'],current['revision'])
        if current['status']=='MODEL_PENDING' or not current['fullFingerprint'] or current['fullFingerprint']!=payload['fullFingerprint']:
            raise ValueError('Resolve pending publication or changed FULL before bake')
        info=capture_module.summary(owner,kind,slug,animations)
        if info['status']!='CAPTURED' or not info.get('geometryReady') or info['captureSha256']!=payload['captureSha256']:
            raise ValueError('Capture current FULL with geometry before baking')
        stored=json.loads(capture_module._file(owner,kind,slug).read_text(encoding='utf-8'))
        idle,candidates=capture_module.idle_identity(animations,slug)
        raw=stored['capture']
        if stored['idleFingerprint']!=idle or stored['fullFingerprint']!=current['fullFingerprint'] or capture_module.digest(raw)!=payload['captureSha256']:
            raise ValueError('Capture changed; refresh')
        capture_module.validate_capture(raw,current['fullIdentity'],candidates)
        sources=_texture_sources(owner,kind,slug,current['fullIdentity'])
        with tempfile.TemporaryDirectory(prefix='game1-mnpc-bake-') as tmp:
            folder=Path(tmp); atlas=folder/'lod1.png'; src=folder/'posed.json'; fbx=folder/f'{slug}_lod1.fbx'; report_path=folder/'report.json'
            mesh, count, materials=assemble(raw,sources,size,atlas)
            src.write_text(json.dumps(mesh,allow_nan=False,separators=(',',':')),encoding='utf-8')
            report=run_report(owner.root,'bake_mnpc_lod_fbx.py',(src,fbx,report_path,str(target)),report_path=report_path,label='MNPC captured geometry bake',timeout=120)
            g=geometry.validate(report)
            if g['triangles']>min(target,count) or not fbx.is_file():
                raise ValueError('Bake did not produce a valid FBX within budget')
            used={(m['owner'],m['colorMap'] or m['textureId']) for m in raw['meshes'] if m['colorMap'] or m['textureId']}
            if any(not sources[key][0].is_file() or sha256(sources[key][0])!=sources[key][1] for key in used):
                raise ValueError('Registered texture changed during bake')
            latest=owner.describe(kind,slug)
            check_revision(current['revision'],latest['revision'])
            if latest['fullFingerprint']!=current['fullFingerprint'] or capture_module.idle_identity(animations,slug)[0]!=idle or capture_module.summary(owner,kind,slug,animations).get('captureSha256')!=payload['captureSha256']:
                raise ValueError('FULL/idle/capture changed during bake; retry')
            recipe={'schemaVersion':1,'mode':'captured_idle','captureSha256':payload['captureSha256'],'idleFingerprint':idle,
                    'animationId':raw['animationId'],'pose':raw['pose'],'targetTriangles':target,'textureSize':size,
                    'outputTextureSize':[size,size],'inputTriangles':count,'inputMeshes':len(raw['meshes']), 'materialTiles':materials,
                    'rootSpace':'roblox_navigation_studs_y_up','uvSpace':'roblox_top_left_to_blender_bottom_left',
                    'reviewedAssembly':False}
            return owner.stage(kind,slug,{'sourcePath':str(fbx),'texturePath':str(atlas),'expectedRevision':current['revision'],
                'fullFingerprint':current['fullFingerprint']},recipe=recipe,prepared_report=g,prepared_sha=sha256(fbx))
