from __future__ import annotations
from pathlib import Path
import hashlib, json, re, shutil, sqlite3, time

SCHEMA_VERSION=1
PROJECT="game1"
ID_RE=re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
class CharacterStore:
    def __init__(self, root: Path):
        self.root=root
        self.runtime=root/'.control-center'; self.runtime.mkdir(parents=True,exist_ok=True)
        self.db=self.runtime/'game1.db'
        self._init(); self.export()
    def connect(self):
        c=sqlite3.connect(self.db); c.row_factory=sqlite3.Row; return c
    def _init(self):
        with self.connect() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS characters(
              id TEXT PRIMARY KEY, display_name TEXT NOT NULL, source_path TEXT NOT NULL DEFAULT '',
              prepared_path TEXT NOT NULL DEFAULT '', sha256 TEXT NOT NULL DEFAULT '', model_asset_id TEXT,
              status TEXT NOT NULL DEFAULT 'LOCAL', revision INTEGER NOT NULL DEFAULT 1,
              created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
    def list(self):
        with self.connect() as c: return [dict(x) for x in c.execute('SELECT * FROM characters ORDER BY id')]
    def put(self,data):
        cid=str(data.get('id','')).strip().lower(); name=str(data.get('displayName','')).strip()
        if not ID_RE.fullmatch(cid): raise ValueError('id must match [a-z0-9][a-z0-9_-]{0,63}')
        if not name: raise ValueError('displayName is required')
        raw_source=str(data.get('sourcePath','')).strip()
        source=''; prepared=''; sha=str(data.get('sha256','')).strip().lower()
        if raw_source:
            source_file=Path(raw_source).expanduser()
            if not source_file.is_absolute(): source_file=(self.root/source_file).resolve()
            if not source_file.is_file(): raise ValueError(f'sourcePath does not exist: {source_file}')
            if source_file.suffix.lower() not in {'.fbx','.obj','.gltf','.glb','.rbxm','.rbxmx'}: raise ValueError('character model must be FBX/OBJ/glTF/RBXM/RBXMX')
            dest=self.root/'assets'/'source'/'characters'/cid/'model'/source_file.name
            dest.parent.mkdir(parents=True,exist_ok=True)
            if source_file.resolve()!=dest.resolve(): shutil.copy2(source_file,dest)
            source=dest.relative_to(self.root).as_posix(); prepared=source
            sha=hashlib.sha256(dest.read_bytes()).hexdigest()
        aid=str(data.get('modelAssetId','') or '').strip() or None
        if aid and not aid.isdigit(): raise ValueError('modelAssetId must be numeric')
        now=time.time()
        with self.connect() as c:
            old=c.execute('SELECT revision,created_at FROM characters WHERE id=?',(cid,)).fetchone()
            rev=(old['revision']+1) if old else 1; created=old['created_at'] if old else now
            c.execute("""INSERT OR REPLACE INTO characters(id,display_name,source_path,prepared_path,sha256,model_asset_id,status,revision,created_at,updated_at)
                         VALUES(?,?,?,?,?,?,?,?,?,?)""",(cid,name,source,prepared,sha,aid,'PUBLISHED' if aid else 'LOCAL',rev,created,now))
        self.export(); return self.get(cid)
    def get(self,cid):
        with self.connect() as c:
            r=c.execute('SELECT * FROM characters WHERE id=?',(cid,)).fetchone(); return dict(r) if r else None
    def delete(self,cid):
        with self.connect() as c: c.execute('DELETE FROM characters WHERE id=?',(cid,))
        self.export()
    def export(self):
        rows=[]
        for x in self.list():
            rows.append({'id':x['id'],'displayName':x['display_name'],'sourcePath':x['source_path'],'preparedPath':x['prepared_path'],'sha256':x['sha256'],'modelAssetId':x['model_asset_id'],'status':x['status'],'revision':x['revision']})
        payload={'schemaVersion':SCHEMA_VERSION,'project':PROJECT,'archetypes':rows}
        p=self.root/'assets/manifests/character-archetypes.json'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        def lua(v):
            if v is None:return 'nil'
            if isinstance(v,bool):return 'true' if v else 'false'
            if isinstance(v,(int,float)):return str(v)
            return json.dumps(str(v),ensure_ascii=False)
        lines=['-- GENERATED. DO NOT EDIT BY HAND.','return table.freeze({','\tschemaVersion = 1,','\tproject = "game1",','\tarchetypes = {']
        for r in rows:
            lines+=['\t\ttable.freeze({',f'\t\t\tid = {lua(r["id"])},',f'\t\t\tdisplayName = {lua(r["displayName"])},',f'\t\t\tmodelAssetId = {lua(r["modelAssetId"])},',f'\t\t\tstatus = {lua(r["status"])},',f'\t\t\trevision = {r["revision"]},','\t\t}),']
        lines+=['\t},','})','']
        (self.root/'src/shared/CharacterRegistry.luau').write_text('\n'.join(lines),encoding='utf-8')
        return payload
