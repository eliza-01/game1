"""Clip documents are versioned separately from published animation bytes."""
import hashlib
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from test_animation_review_m178 import AnimationReviewM178
from animation_core.documents import validate_document, get_document
from animation_core.common import classify_animation, EMOTION_SLOT_CATALOG

class AnimationDocuments(AnimationReviewM178):
    # Inherit the real-store fixture and legacy contract cases as well.
    def package(self, procedural=False):
        path=self.clip('human_male_emotions_blink.animation.json' if procedural else 'human_male_emotions_idle.rbxmx')
        data=dict(schema_version=1,clip_name='emotions_blink' if procedural else 'emotions_idle',
                  fps=30,frame_start=1,frame_end=91,looped=False,mode='procedural' if procedural else 'skeletal',
                  events=[dict(id='e1',name='blink',frame=31,time=1,parameters={'duration':.2})])
        if not procedural:data['animation_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        sidecar=path if procedural else path.with_suffix('.animation.json')
        sidecar.write_text(json.dumps(data),encoding='utf8')
        return path,sidecar,data

    def test_all_emotion_names_and_legacy_names(self):
        for row in EMOTION_SLOT_CATALOG:
            binding=classify_animation(Path('human_male_emotions_'+row['slot']+'.rbxmx'),'human_male')
            self.assertEqual((binding['scope'],binding['slot']),('emotions',row['slot']))
        self.assertEqual(classify_animation(Path('Atk02_1HS_FFighter.rbxm'))['variant'],2)

    def test_sidecar_not_scanned_twice_and_registered_with_clip(self):
        _,_,data=self.package()
        review=self.store.preview_folder('human_male',str(self.inbox))
        self.assertEqual(review['filesScanned'],1)
        self.store.register_selected('human_male',str(self.inbox),review['items'])
        row=self.store.snapshot('human_male')['items'][0]
        self.assertEqual(row['document']['events'],data['events'])
        self.assertFalse(row['document_only'])

    def test_procedural_document_has_no_cloud_animation(self):
        self.package(True)
        review=self.store.preview_folder('human_male',str(self.inbox))
        result=self.store.register_selected('human_male',str(self.inbox),review['items'])
        self.assertTrue(result['registered'][0]['documentOnly'])
        row=self.store.snapshot('human_male')['items'][0]
        self.assertEqual(row['status'],'DOCUMENT_READY')
        with self.assertRaisesRegex(ValueError,'procedural'):
            self.store.publish_clip(row['clip_id'],{})

    def test_metadata_update_preserves_published_id_and_bytes(self):
        _,sidecar,data=self.package()
        review=self.store.preview_folder('human_male',str(self.inbox))
        self.store.register_selected('human_male',str(self.inbox),review['items'])
        clip=self.store.snapshot('human_male')['items'][0]
        with self.store.connect() as db:
            db.execute("UPDATE animation_clips SET asset_id='123',published_sha256=sha256 WHERE id=?",(clip['clip_id'],))
        data['events'][0]['parameters']['duration']=.4
        sidecar.write_text(json.dumps(data),encoding='utf8')
        review=self.store.preview_folder('human_male',str(self.inbox))
        self.assertEqual(review['items'][0]['status'],'DOCUMENT_UPDATE')
        result=self.store.register_selected('human_male',str(self.inbox),review['items'])
        self.assertTrue(result['registered'][0]['metadataOnly'])
        row=self.store.snapshot('human_male')['items'][0]
        self.assertEqual((row['asset_id'],row['sha256']),('123',clip['sha256']))
        self.assertEqual(row['document']['events'][0]['parameters']['duration'],.4)

    def test_document_changed_since_preview_is_rejected(self):
        _,sidecar,data=self.package()
        review=self.store.preview_folder('human_male',str(self.inbox))
        data['events'][0]['parameters']['duration']=.4
        sidecar.write_text(json.dumps(data),encoding='utf8')
        with self.assertRaisesRegex(ValueError,'scan again'):
            self.store.register_selected('human_male',str(self.inbox),review['items'])
        self.assertFalse(self.store.snapshot('human_male')['items'])

    def test_invalid_hash_parameters_and_event_clock(self):
        _,_,data=self.package()
        with self.assertRaisesRegex(ValueError,'match animation'):validate_document(data,'0'*64)
        data['events'][0]['time']=2
        with self.assertRaisesRegex(ValueError,'frame/FPS'):validate_document(data)
        data['events'][0]['time']=1;data['events'][0]['parameters']['duration']=float('nan')
        with self.assertRaisesRegex(ValueError,'finite'):validate_document(data)

    def test_pending_native_replacement_keeps_old_published_document(self):
        path,sidecar,data=self.package()
        self.store.register_selected('human_male',str(self.inbox),self.store.preview_folder('human_male',str(self.inbox))['items'])
        clip=self.store.snapshot('human_male')['items'][0]
        with self.store.connect() as db:
            db.execute("UPDATE animation_clips SET asset_id='123',published_sha256=sha256 WHERE id=?",(clip['clip_id'],))
        path.write_bytes(b'new native bytes');data['animation_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        data['events'][0]['parameters']['duration']=.7;sidecar.write_text(json.dumps(data),encoding='utf8')
        self.store.stage_manual_replacement(clip['clip_id'],str(path))
        registry=(self.root/'src/shared/character/CharacterAnimationRegistry.luau').read_text(encoding='utf8')
        self.assertIn('["duration"]=0.2',registry)
        self.assertNotIn('["duration"]=0.7',registry)

    def test_failed_package_registration_rolls_back_database_and_files(self):
        self.package()
        self.clip('human_male_base_walk.rbxm',b'walking')
        review=self.store.preview_folder('human_male',str(self.inbox))
        original=self.store._register_source
        calls=[]
        def fail_second(*args,**kwargs):
            calls.append(True)
            if len(calls)==2:raise ValueError('injected second package failure')
            return original(*args,**kwargs)
        with patch.object(self.store,'_register_source',side_effect=fail_second):
            with self.assertRaisesRegex(ValueError,'second package'):
                self.store.register_selected('human_male',str(self.inbox),review['items'])
        self.assertFalse(self.store.snapshot('human_male')['items'])
        self.assertFalse(list((self.root/'assets/source').rglob('*.rbxm')))
        self.assertFalse(list((self.root/'assets/source').rglob('*.rbxmx')))

    def test_actual_rojo_transport_preserves_source(self):
        from services.animation_native import animation_upload_file
        from shutil import which
        if not which('rojo'):self.skipTest('Rojo not installed')
        source=self.clip('human_male_emotions_idle.rbxmx',b'<roblox version="4"><Item class="KeyframeSequence"><Properties><string name="Name">idle</string></Properties><Item class="Keyframe"><Properties><float name="Time">0</float></Properties></Item></Item></roblox>')
        raw=source.read_bytes()
        with animation_upload_file(source) as upload:
            self.assertTrue(upload.read_bytes().startswith(b'<roblox!'))
        self.assertEqual(source.read_bytes(),raw)
