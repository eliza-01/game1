"""M172 character guided pipeline: external failure must never be hidden."""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "system/control-center"))
from services.character_registration_flow import run


class Store:
    def __init__(self, existing=None, error_at=""):
        self.row = existing
        self.error_at = error_at
        self.calls = []

    def get(self, character_id):
        return self.row if self.row and self.row["id"] == character_id else None

    def register(self, payload):
        self.calls.append("register")
        if self.error_at == "register":
            raise RuntimeError("bad FBX")
        previous = self.row or {}
        self.row = {"id": payload["id"], "race": payload["race"], "gender": payload["gender"],
                    "display_name": payload["displayName"], "model_asset_id": previous.get("model_asset_id"),
                    "revision": previous.get("revision", 0)+1, "source_path": payload["sourcePath"],
                    "status": "CHANGED" if previous else "REGISTERED", "model_replacement_pending": int(bool(payload.get("forceReplacement")))}
        return self.row

    def publish(self, character_id, credentials):
        self.calls.append("publish")
        if self.error_at == "publish":
            raise RuntimeError("Open Cloud unavailable")
        self.row = {**self.row, "model_asset_id": "222", "status": "PUBLISHED", "model_replacement_pending": 0}
        return self.row


class CharacterWorkflowM172(unittest.TestCase):
    def payload(self, existing_id=""):
        return {"existingId": existing_id,"id": existing_id or "human_male", "race":"human", "gender":"male",
                "displayName":"Human Male", "sourcePath":"C:/models/man.fbx", "description":"Model"}

    def call(self, store, data, sync=lambda cid: {"studio":{"destination":"characters/human/male"}}, creds=lambda desc: {"description":desc}):
        return run(data, store=store, publication_credentials=creds, sync_character_to_studio=sync)

    def test_fresh_register_publish_sync(self):
        store=Store(); result=self.call(store,self.payload())
        self.assertTrue(result['ok'])
        self.assertEqual(store.calls,['register','publish'])
        self.assertEqual([s['status'] for s in result['stages']],['ok']*4)
        self.assertEqual(result['newAssetId'],'222')

    def test_cloud_failure_keeps_explicit_partial_registration(self):
        store=Store(error_at='publish'); result=self.call(store,self.payload())
        self.assertFalse(result['ok']); self.assertEqual(result['failedStage'],'publish')
        self.assertEqual(result['newAssetId'],'')
        self.assertEqual([s['status'] for s in result['stages']],['ok','ok','error'])
        self.assertIn('Registration is saved',result['recovery'])

    def test_studio_failure_reports_committed_id_and_retry_not_republish(self):
        store=Store(); result=self.call(store,self.payload(),sync=lambda cid: (_ for _ in ()).throw(RuntimeError('Studio offline')))
        self.assertFalse(result['ok']); self.assertEqual(result['failedStage'],'studio')
        self.assertEqual(result['newAssetId'],'222')
        self.assertIn('Retry Studio sync',result['recovery'])

    def test_credentials_fail_before_register(self):
        store=Store(); result=self.call(store,self.payload(),creds=lambda desc: (_ for _ in ()).throw(RuntimeError('No Open Cloud')))
        self.assertEqual(store.calls,[]); self.assertEqual(result['failedStage'],'validate')

    def test_identity_changes_must_use_separate_endpoint(self):
        old={'id':'human_male','race':'human','gender':'male','display_name':'Human Male', 'model_asset_id':'111', 'revision':2,'status':'PUBLISHED'}
        store=Store(existing=old)
        data=self.payload('human_male');data['displayName']='Changed'
        result=self.call(store,data)
        self.assertEqual(result['failedStage'],'validate');self.assertEqual(store.calls,[])

    def test_replacement_changes_id_and_preserves_previous_one_in_report(self):
        old={'id':'human_male','race':'human','gender':'male','display_name':'Human Male', 'model_asset_id':'111', 'revision':2,'status':'PUBLISHED'}
        store=Store(existing=old);result=self.call(store,self.payload('human_male'))
        self.assertTrue(result['ok']);self.assertEqual(result['previousAssetId'],'111');self.assertEqual(result['newAssetId'],'222')

    def test_published_unchanged_does_not_republish_without_source(self):
        old={'id':'human_male','race':'human','gender':'male','display_name':'Human Male', 'model_asset_id':'111', 'revision':2,'status':'PUBLISHED'}
        store=Store(existing=old);data=self.payload('human_male');data['sourcePath']=''
        result=self.call(store,data)
        self.assertEqual(result['failedStage'],'validate');self.assertEqual(store.calls,[])

    def test_changed_registered_source_can_resume_without_new_fbx(self):
        old={'id':'human_male','race':'human','gender':'male','display_name':'Human Male', 'model_asset_id':None, 'revision':2,'status':'REGISTERED'}
        store=Store(existing=old);data=self.payload('human_male');data['sourcePath']=''
        result=self.call(store,data)
        self.assertTrue(result['ok']);self.assertEqual(store.calls,['publish'])

    def test_same_character_cannot_be_published_twice_concurrently(self):
        store=Store()
        inner=[]
        def sync(cid):
            inner.append(self.call(store,self.payload()))
            return {"studio":{"destination":"ok"}}
        outer=self.call(store,self.payload(),sync=sync)
        self.assertTrue(outer['ok'])
        self.assertFalse(inner[0]['ok'])
        self.assertIn('Another Reg + Publish',inner[0]['error'])
        self.assertEqual(store.calls,['register','publish'])

    def test_http_write_route_exposes_workflow_without_changing_legacy_endpoints(self):
        from api.write_actors import route
        store=Store()
        deps={name: object() for name in (
            'character_identity','monsters','npc_equipment','npcs','weapons')}
        deps.update(store=store,
                    publication_credentials=lambda desc: {'description':desc},
                    sync_character_to_studio=lambda cid: {'studio': {'destination':'ok'}},
                    sync_monster_to_studio=lambda *args: {},
                    sync_weapon_to_studio=lambda *args: {})
        status,result=route('/api/characters/workflow',lambda: self.payload(),deps)
        self.assertEqual(status,200)
        self.assertTrue(result['ok'])
        self.assertEqual(store.calls,['register','publish'])

    def test_ui_has_only_one_model_flow_action_and_reset(self):
        html=(ROOT/'system/control-center/static/index.html').read_text(encoding='utf8')
        js=(ROOT/'system/control-center/static/character-workflow.js').read_text(encoding='utf8')
        self.assertIn('id="register-character"',html)
        self.assertNotIn('id="publish-character"',html)
        self.assertNotIn('id="sync-character"',html)
        self.assertIn('id="clear-form" class="character-reset"',html)
        self.assertIn('id="character-report-dialog"',html)
        self.assertIn('Rojo propagates generated CharacterRegistry.luau',js)


if __name__ == '__main__':
    unittest.main()
