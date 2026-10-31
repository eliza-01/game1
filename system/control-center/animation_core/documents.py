"""Versioned clip event documents, independent of Roblox Animation Asset IDs."""
import hashlib
import json
import math
import re
from pathlib import Path
import uuid
from sqlite_connection import connect

MAX_BYTES=128*1024
EVENT_NAMES={'blink','face_state','face_reset','eyes_set','eyes_spin_start','eyes_spin_stop'}
STATES={'idle','combat_idle','happy','happy_sharp_caret','happy_thick_caret','sad','blink',
        'closed','indignant_surprise','dizzy_spiral','look_around','nausea_wave','raised_eyebrow'}

def finite(value,label,low=None,high=None):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError(label+' must be finite')
    if low is not None and value<low or high is not None and value>high:raise ValueError(label+' out of range')
    return value

def validate_document(data,animation_sha=None):
    if not isinstance(data,dict) or data.get('schema_version')!=1:raise ValueError('animation document schema_version must be 1')
    result=dict(data)
    if not isinstance(result.get('clip_name'),str) or not re.fullmatch('[a-z0-9][a-z0-9_]{0,127}',result['clip_name']):raise ValueError('invalid clip_name')
    if not isinstance(result.get('looped'),bool):raise ValueError('looped must be boolean')
    mode=result.get('mode','skeletal')
    if mode not in {'skeletal','procedural'}:raise ValueError('invalid animation document mode')
    result['mode']=mode
    rig=result.get('rig')
    if rig is not None:
        if not isinstance(rig,dict) or not isinstance(rig.get('id'),str) or not re.fullmatch('[a-z][a-z0-9_]*',rig['id']):raise ValueError('invalid rig identity')
        revision=rig.get('revision')
        if isinstance(revision,bool) or not isinstance(revision,int) or revision<1:raise ValueError('invalid rig revision')
        if not isinstance(rig.get('asset_id'),str) or not rig['asset_id'].isdigit():raise ValueError('invalid rig asset_id')
    fps=finite(result.get('fps'),'fps',1,240)
    start=finite(result.get('frame_start'),'frame_start',-100000,100000)
    end=finite(result.get('frame_end'),'frame_end',start,1000000)
    duration=(end-start)/fps
    if duration<=0 or duration>3600:raise ValueError('animation document duration must be 0..3600 seconds')
    result['duration']=duration
    if mode=='skeletal':
        digest=result.get('animation_sha256','')
        if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('animation document requires animation_sha256')
        if animation_sha is not None and digest!=animation_sha:raise ValueError('animation document does not match animation bytes')
    elif animation_sha is not None:raise ValueError('procedural document cannot accompany a skeletal animation')
    events=result.get('events',[])
    if not isinstance(events,list) or len(events)>256:raise ValueError('too many animation events')
    parsed=[];ids=set()
    for i,event in enumerate(events):
        if not isinstance(event,dict) or event.get('name') not in EVENT_NAMES:raise ValueError('unknown animation event')
        frame=finite(event.get('frame'),'event.frame',start,end)
        expected=(frame-start)/fps
        time_value=finite(event.get('time',expected),'event.time',0,duration)
        if abs(time_value-expected)>1e-6:raise ValueError('event time does not match frame/FPS')
        ident=event.get('id','event_'+str(i+1).zfill(4))
        if not isinstance(ident,str) or len(ident)>96 or ident in ids:raise ValueError('duplicate/invalid event ID')
        ids.add(ident)
        parameters=event.get('parameters',{})
        if not isinstance(parameters,dict) or len(json.dumps(parameters))>2048:raise ValueError('invalid event parameters')
        name=event['name']
        allowed={'blink':{'duration','side'},'face_state':{'name'},'face_reset':set(),
                 'eyes_set':{'name'},'eyes_spin_start':{'degrees_per_second'},'eyes_spin_stop':set()}[name]
        if set(parameters)-allowed:raise ValueError('unknown parameters for '+name)
        if name=='blink':
            finite(parameters.get('duration',.16),'blink.duration',.04,2)
            if parameters.get('side','both') not in {'both','l','r'}:raise ValueError('invalid blink side')
        if name=='face_state' and parameters.get('name') not in STATES:raise ValueError('unknown face state')
        if name=='eyes_set' and parameters.get('name') not in {'normal','spiral'}:raise ValueError('unknown eyes mesh')
        if name=='eyes_spin_start':finite(parameters.get('degrees_per_second',180),'spin speed',-1440,1440)
        parsed.append(dict(id=ident,frame=frame,time=expected,name=name,parameters=parameters))
    result['events']=sorted(parsed,key=lambda e:e['time'])
    json.dumps(result,allow_nan=False)
    return result

def document_path(source):
    source=Path(source)
    return source if source.name.endswith('.animation.json') else source.with_suffix('.animation.json')

def read_document(source,animation_sha=None):
    path=document_path(source)
    if not path.is_file():return None
    raw=path.read_bytes()
    if len(raw)>MAX_BYTES:raise ValueError('animation document exceeds 128 KiB')
    return validate_document(json.loads(raw.decode('utf-8')),animation_sha)

def document_digest(source):
    path=document_path(source)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ''

def is_animation_source(path):
    path=Path(path)
    if path.suffix.lower() in {'.rbxm','.rbxmx'}:return True
    if not path.name.endswith('.animation.json'):return False
    stem=path.name[:-len('.animation.json')]
    return not any((path.parent/(stem+ext)).is_file() for ext in ('.rbxm','.rbxmx'))

def ensure_schema(store):
    with connect(store.db) as db:
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='animation_clip_documents'").fetchone()
        if exists:return
        backup=store.db.parent/'backups'/('before_animation_documents_'+uuid.uuid4().hex+'.db')
        backup.parent.mkdir(exist_ok=True)
        with connect(backup) as target:db.backup(target)
        db.execute('''CREATE TABLE animation_clip_documents(
            clip_id TEXT NOT NULL,animation_sha256 TEXT NOT NULL,document_json TEXT NOT NULL,
            document_sha256 TEXT NOT NULL,revision INTEGER NOT NULL,updated_at REAL NOT NULL,
            PRIMARY KEY(clip_id,animation_sha256))''')

def save_document(connection,clip_id,document,digest,now):
    key=document.get('animation_sha256') if document['mode']=='skeletal' else 'procedural'
    connection.execute('''INSERT INTO animation_clip_documents VALUES(?,?,?,?,1,?)
        ON CONFLICT(clip_id,animation_sha256) DO UPDATE SET document_json=excluded.document_json,
        document_sha256=excluded.document_sha256,revision=revision+1,updated_at=excluded.updated_at
        WHERE document_sha256<>excluded.document_sha256''',
        (clip_id,key,json.dumps(document,ensure_ascii=False),digest,now))

def get_document(connection,clip_id,animation_sha):
    row=connection.execute('SELECT * FROM animation_clip_documents WHERE clip_id=? AND animation_sha256=?',(clip_id,animation_sha)).fetchone()
    return json.loads(row['document_json']) if row else None
