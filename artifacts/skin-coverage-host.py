import json,os,sys,urllib.request,sqlite3,shutil
from pathlib import Path
from contextlib import closing
root=Path.cwd()
env={}
for raw in (root/'.env.local').read_text(encoding='utf-8').splitlines():
 if '=' in raw and not raw.lstrip().startswith('#'):
  key,value=raw.split('=',1)
  if key.strip() in ('CONTROL_TOKEN','CONTROL_AGENT_PORT'):env[key.strip()]=value.strip().strip('"').strip("'")
port=os.environ.get('CONTROL_AGENT_PORT',env.get('CONTROL_AGENT_PORT','43821'))
token=os.environ.get('CONTROL_TOKEN',env.get('CONTROL_TOKEN','Game1LocalControlV1'))
mode=sys.argv[1]
path='/api/real-estate/house_level4_01/'+{'job':'publication-job','publish':'publish-async','sync':'sync'}[mode]
body=None
if mode=='publish':
 backup=root/'.control-center/backups/skin-coverage-m157';backup.mkdir(parents=True,exist_ok=True)
 if (backup/'game1.db').exists():raise RuntimeError('Backup already exists; inspect prior job before another publication')
 with closing(sqlite3.connect((root/'.control-center/game1.db').as_uri()+'?mode=ro',uri=True)) as source, closing(sqlite3.connect(backup/'game1.db')) as dest:source.backup(dest)
 shutil.copy2(root/'assets/manifests/real-estate.json',backup/'real-estate.json')
 body=json.dumps({'scope':'model:house'}).encode()
if mode=='sync':body=json.dumps({'part':'house'}).encode()
request=urllib.request.Request('http://127.0.0.1:'+port+path,data=body,headers={'X-Control-Token':token,'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=180) as response:result=json.load(response)
if mode=='sync':
 print(json.dumps(result.get('studio',{}),ensure_ascii=True))
else:print(json.dumps(result,ensure_ascii=True))
