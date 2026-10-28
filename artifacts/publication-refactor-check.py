import sys, json, hashlib
from pathlib import Path
root=Path.cwd()
sys.path.insert(0,str(root/'system/control-center'))
from real_estate.fbx import inspect, inspect_selected, prepare_publication
from character_analysis import prepare_character_publication_fbx
from model_publication_service import staged_model
row=next(r for r in json.loads((root/'assets/manifests/real-estate.json').read_text(encoding='utf-8'))['items'] if r['slug']=='house_level4_01')
out=root/'artifacts/publication-check';out.mkdir(exist_ok=True)
source=root/row['model_path']; door=root/row['meshSources']['door']['path']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,door)}
textures={k:str(root/v['path']) for k,v in row['textures'].items() if v.get('path')}
expected=inspect(root,source)
full=prepare_publication(root,source,out/'full',expected,textures)
selected=inspect_selected(root,door,'door')
part=prepare_publication(root,door,out/'part',selected,{'door':textures['door']},only_part='door')
character=prepare_character_publication_fbx(root,door,out/'character-door.fbx')
with staged_model(root,door) as staged:
    generic=inspect_selected(root,staged,'door')
    from real_estate.contracts import assert_rig_survived
    assert_rig_survived(selected,generic,'door')
for p,h in hashes.items(): assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
report={'full':full,'part':part,'character':character['preparation'],'generic':generic,'sourceHashesUnchanged':True}
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'fullParts':list(full['parts']), 'door':part['parts']['door'], 'sourceHashesUnchanged':True}))
