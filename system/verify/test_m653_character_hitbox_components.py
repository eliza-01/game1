from pathlib import Path
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'system/control-center'))
from services import character_hitbox_authoring as authoring
from services import hitbox_asset_registry as registry
from api import write_actors


def fixture(slug='human_male'):
    key='component|1:body:rbxassetid://456:1.000000,1.000000,1.000000|identity:'+slug+'|head:head|parent:neck'
    return {'key':key,'signature':json.dumps([[[['body'],'rbxassetid://456',[0]*12,[0]*12,[]]],[],['head'],['neck'],[],[[0]*12,[0]*12]]),
            'component':{'dependencies':[],'rawHead':{'minimum':[0,0,0],'maximum':[0,1,2]}},
            'definition':{'broadRadius':4,'sourceVertexCount':5,'bodyBoxes':[],
                          'headBox':{'kind':'head','boneName':'head','center':[0,.5,1],'size':[.05,1.03,2.03]}}}


class CharacterHitboxM653(unittest.TestCase):
    def test_linear_catalog_plan_covers_each_choice(self):
        cat=json.loads((ROOT/'assets/manifests/character-creation-appearance.json').read_text('utf-8'))['archetypes']
        for slug in authoring.HUMANS:
            command=authoring.command_for(slug)
            variants=command['variants'];self.assertTrue(variants[0]['base'])
            self.assertLessEqual(len(variants),2+sum(max(0,len(cat[slug][group])-1) for group in authoring.GROUPS))
            for group in authoring.GROUPS:
                for item in cat[slug][group]:
                    expected=[item['part']['id']] if 'part' in item else [item['left']['id'],item['right']['id']]
                    self.assertTrue(any(all(x in [p['id'] for p in v['parts'].values()] for x in expected) for v in variants))

    def test_capture_replaces_only_scope_and_rejects_conflicts(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'registry.luau'; mnpc=fixture('gremlin');mnpc['key']=mnpc['key'].removeprefix('component|');mnpc.pop('component')
            path.write_text(registry.render({'schemaVersion':2,'entries':[mnpc,fixture('human_female')]}),encoding='utf-8')
            def bridge(command):return {'schemaVersion':2,'variants':len(command['variants']),'entries':[fixture(),fixture()]}
            result=authoring.capture('human_male',bridge=bridge,destination=path)
            self.assertEqual(result['components'],1);self.assertEqual(result['entries'],3)
            before=path.read_bytes()
            for invalid in ('conflict','wrong','missing','bounds'):
                def bad(command):
                    rows=[fixture()];second=fixture()
                    if invalid=='conflict':second['definition']['broadRadius']=9;rows.append(second)
                    elif invalid=='wrong':rows=[fixture('other')]
                    elif invalid=='missing':rows=[]
                    else:rows[0]['component']['rawHead']['maximum']=[0,2,2]
                    return {'schemaVersion':2,'variants':len(command['variants']),'entries':rows}
                with self.assertRaises(ValueError):authoring.capture('human_male',bridge=bad,destination=path)
                self.assertEqual(before,path.read_bytes())
            with patch.object(authoring,'command_for',side_effect=[authoring.command_for('human_male'),{'changed':True}]):
                with self.assertRaisesRegex(ValueError,'changed during'):authoring.capture('human_male',bridge=bridge,destination=path)
            self.assertEqual(before,path.read_bytes())

    def test_route_and_owners(self):
        with patch.object(authoring,'capture',return_value={'status':'CAPTURED'}) as capture:
            self.assertEqual(write_actors.route('/api/characters/hitboxes',lambda:{'id':'human_male'},{}),(200,{'status':'CAPTURED'}))
            capture.assert_called_once_with('human_male')
        service=(ROOT/'src/server/combat/EntityHitboxService.luau').read_text('utf-8')
        self.assertLess(service.index('CharacterHitboxComponents.Lookup(binding)'),service.index('HitboxMeshGeometryCache.Read(meshPart)'))
        self.assertIn('CharacterHitboxComponents.Capture(bound, oracle)',service)
        capture=(ROOT/'system/studio-plugin/modules/StudioCharacterHitboxCapture.luau').read_text('utf-8')
        for token in ('builder.Build(recipe, load)','rigService.BuildHitboxAuthoring','hitboxes.CaptureCharacterComponents','asset:Destroy()'):
            self.assertIn(token,capture)
        self.assertNotIn('Workspace',capture.split('local Capture',1)[1])
        js=(ROOT/'system/control-center/static/character-hitboxes.js').read_text('utf-8')
        self.assertIn('row.assembly_resolved?.ready===true',js)
        self.assertIn('/api/characters/hitboxes',js)

    def test_actual_lua_oracle_component_union(self):
        lua=shutil.which('texlua') or shutil.which('lua')
        if not lua:self.skipTest('Standalone Lua unavailable')
        combat=ROOT/'src/server/combat'
        with tempfile.TemporaryDirectory() as d:
            out=[]
            for name in ('HitboxDefinitionBuilder','HitboxAssetDefinitions','CharacterHitboxComponents'):
                s=(combat/(name+'.luau')).read_text('utf-8')
                s=re.sub(r' :: (?:Bone|CFrame)', '',s)
                s=re.sub(r': \([^\n]+?\)(?=\n)', '',s) # return tuples only
                s=re.sub(r': (?:Bone|CFrame|Vector3|MeshPart|any|string|number)\??(?=[,)\n])','',s)
                s=re.sub(r'([\w.]+) \+= (.+)',r'\1 = \1 + \2',s)
                s=s.replace('if math.abs(meshSize.X) > 1e-6 then meshPart.Size.X / meshSize.X else 1','(math.abs(meshSize.X) > 1e-6 and meshPart.Size.X / meshSize.X or 1)')
                for axis in 'YZ':s=s.replace(f'if math.abs(meshSize.{axis}) > 1e-6 then meshPart.Size.{axis} / meshSize.{axis} else 1',f'(math.abs(meshSize.{axis}) > 1e-6 and meshPart.Size.{axis} / meshSize.{axis} or 1)')
                s=s.replace('if headBone then transformedBoneFrame(headBone) else nil','(headBone and transformedBoneFrame(headBone) or nil)').replace('if headBounds.count > 0 then headBounds else nil','(headBounds.count > 0 and headBounds or nil)').replace('(if merged.headBox then 1 else 0)','(merged.headBox and 1 or 0)')
                # Do not rewrite method calls; only type annotations above.
                path=Path(d)/(name+'.lua');path.write_text(s,encoding='utf-8');out.append(str(path))
            subprocess.run([lua,str(ROOT/'system/verify/hitbox_components_m653.lua'),*out],check=True,timeout=15)
