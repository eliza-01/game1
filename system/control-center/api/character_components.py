"""Modular Characters HTTP adapters. Authentication remains at Host Agent boundary."""
from urllib.parse import unquote
from character_core.components import ComponentConflict
from character_core.atlas_authoring import CharacterAtlasAuthoring

ROOT='/api/characters/components'


def read(path,sources):
    queue_root=ROOT+'/publication-queue'
    if path==queue_root or path.startswith(queue_root+'/'):
        job_id=path[len(queue_root):].strip('/') or None
        job=sources['character_publications'].get(job_id)
        if job_id and job is None:return 404,{'error':'publication queue not found'}
        return 200,{'schema_version':1,'job':job}
    if path!=ROOT:return None
    data=sources['character_components'].snapshot()
    data['publication']=sources['publication_config']()
    return 200,data


def write(path,body,deps):
    if not path.startswith(ROOT+'/'):return None
    store=deps['character_components']
    try:
        payload=body()
        if path.startswith(ROOT+'/atlases/'):
            flow=CharacterAtlasAuthoring(store)
            if path==ROOT+'/atlases/inspect':return 200,flow.inspect(payload.get('sourcePath') or '')
            if path==ROOT+'/atlases/publish':
                result=flow.publish(payload,deps['publication_credentials'])
                if 'character_assemblies' in deps:deps['character_assemblies'].characters.export()
                return 200,result
            if path==ROOT+'/atlases/reveal':return 200,flow.reveal(payload.get('sourcePath') or '')
            return 404,{'error':'unknown Character atlas operation'}
        if path==ROOT+'/publication-queue':
            credentials=deps['publication_credentials']('game1 character components')
            return 202,deps['character_publications'].start(payload.get('items'),payload.get('request_id'),credentials)
        if path==ROOT+'/inspect':return 200,store.inspect(payload.get('sourcePath') or '')
        if path==ROOT+'/register':return 200,store.register(payload.get('token'),payload.get('replacements',[]))
        if path==ROOT+'/atlas':
            revision=payload.get('expectedRevision')
            if revision is None:raise ValueError('expectedRevision is required')
            result=store.bind_atlas(str(payload.get('id') or ''),payload.get('variantId'),int(revision))
            if 'character_assemblies' in deps:deps['character_assemblies'].characters.export()
            return 200,result
        if path==ROOT+'/publish':
            result=store.publish(str(payload.get('kind') or ''),str(payload.get('id') or ''),
                deps['publication_credentials']('game1 character component'))
            if 'character_assemblies' in deps:deps['character_assemblies'].characters.export()
            return 200,result
        return 404,{'error':'unknown character component operation'}
    except ComponentConflict as error:
        return 409,{'error':str(error),'code':'inspection_conflict','schema_version':1}
    except Exception as error:
        return 400,{'error':str(error),'schema_version':1}
