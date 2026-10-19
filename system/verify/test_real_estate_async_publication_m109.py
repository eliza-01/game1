"""M109: async publishing, deduplication, recoverable Roblox operation paths."""
from __future__ import annotations

from http.client import RemoteDisconnected
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'system/control-center'))
from api import real_estate
from opencloud_assets import OpenCloudAssetError, _json_http
from real_estate.jobs import RealEstatePublicationJobs
from real_estate.store import RealEstateStore
from test_real_estate_m107 import skeleton


class SlowPublisher:
    def __init__(self, fail=False):
        self.entered=Event()
        self.release=Event()
        self.calls=[]
        self.fail=fail

    def get(self, slug):
        return {'slug':slug, 'meshParts':['house','door']} if slug in ('estate-1','estate-2','estate-3') else None

    def publish(self, slug, credentials, *, scope, on_progress):
        self.calls.append((slug,scope))
        on_progress('Waiting for Roblox to process HouseRig')
        self.entered.set()
        if not self.release.wait(3):
            raise RuntimeError('test worker timed out')
        if self.fail:
            raise RuntimeError('simulated network interruption')
        return {'slug':slug}


def finished(jobs, slug, timeout=3):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        job=jobs.get(slug)
        if job and job['status'] in ('succeeded','failed'):
            return job
        time.sleep(.01)
    raise AssertionError('Publication job did not finish')


class AsyncPublicationTests(unittest.TestCase):
    def test_request_returns_immediately_and_reuses_running_job(self):
        publisher=SlowPublisher()
        jobs=RealEstatePublicationJobs(publisher)
        try:
            begun=time.monotonic()
            first=jobs.start('estate-1',{'apiKey':'do-not-leak'},scope='all')
            self.assertLess(time.monotonic()-begun,1)
            self.assertTrue(publisher.entered.wait(1))
            self.assertEqual(jobs.get('estate-1')['step'],'Waiting for Roblox to process HouseRig')
            second=jobs.start('estate-1',{'apiKey':'do-not-leak'},scope='all')
            self.assertEqual(second['id'],first['id'])
            self.assertTrue(second['alreadyRunning'])
            self.assertEqual(publisher.calls,[('estate-1','all')])
            self.assertNotIn('do-not-leak',str(jobs.get('estate-1')))
        finally:
            publisher.release.set()
            self.assertEqual(finished(jobs,'estate-1')['status'],'succeeded')

    def test_job_failure_is_json_serializable_with_step_and_error(self):
        publisher=SlowPublisher(fail=True)
        jobs=RealEstatePublicationJobs(publisher)
        jobs.start('estate-1',{},scope='model')
        publisher.release.set()
        result=finished(jobs,'estate-1')
        self.assertEqual(result['status'],'failed')
        self.assertIn('network interruption',result['error'])
        self.assertEqual(result['step'],'Waiting for Roblox to process HouseRig')

    def test_concurrent_cap_and_invalid_slug(self):
        publisher=SlowPublisher()
        jobs=RealEstatePublicationJobs(publisher)
        jobs.start('estate-1',{},scope='all')
        jobs.start('estate-2',{},scope='house')
        try:
            with self.assertRaisesRegex(ValueError,'Two Real Estate'):
                jobs.start('estate-3',{},scope='all')
            with self.assertRaisesRegex(ValueError,'not registered'):
                jobs.start('not-registered',{},scope='all')
        finally:
            publisher.release.set()
            finished(jobs,'estate-1')
            finished(jobs,'estate-2')

    def test_async_routes_reuse_existing_sync_endpoint(self):
        publisher=SlowPublisher()
        jobs=RealEstatePublicationJobs(publisher)
        creds={'apiKey':'secret','creatorType':'user','creatorId':'123'}
        sources={'real_estate':publisher, 'real_estate_publications':jobs, 'publication_credentials':lambda description:creds}
        result=real_estate.write('/api/real-estate/estate-1/publish-async',
             lambda:{'scope':'model'},sources)
        try:
            self.assertEqual(result[0],202)
            self.assertEqual(result[1]['job']['scope'],'model')
            fetched=real_estate.read(urlparse('/api/real-estate/estate-1/publication-job'),sources)
            self.assertEqual(fetched[0],200)
            self.assertEqual(fetched[1]['job']['id'],result[1]['job']['id'])
        finally:
            publisher.release.set()
            finished(jobs,'estate-1')

    def test_opencloud_abrupt_disconnect_is_readable_not_unhandled(self):
        class BrokenOpener:
            def open(self, *args, **kwargs):
                raise RemoteDisconnected('remote server closed the connection')
        with patch('opencloud_assets._opener',return_value=BrokenOpener()):
            with self.assertRaisesRegex(OpenCloudAssetError,'RemoteDisconnected'):
                _json_http(object(),1)


class PendingOperationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='m109-pending-')
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        art=self.root/'art'
        art.mkdir()
        self.fbx=art/'house_level1_01.fbx'
        self.fbx.write_bytes(b'fake FBX')
        self.texture=art/'atlas.png'
        self.texture.write_bytes(b'fake image')
        self.store=RealEstateStore(self.root)
        with patch('real_estate.store.inspect',return_value=skeleton()):
            self.store.register({'sourcePath':str(self.fbx),'houseType':'house','level':1,'variant':'01',
                'textures':{'house':str(self.texture),'door':''},
                'textureReferences':{'door':'mesh:house'}})
        self.creds={'apiKey':'fake','creatorType':'user','creatorId':'2'}

    def test_retries_wait_on_same_image_operation_not_create_second_asset(self):
        submits=[]
        polls=[]
        def create(*args,**kwargs):
            submits.append('create')
            return 'operations/unique-image'
        def wait(op,**kwargs):
            polls.append(op)
            if len(polls)==1:
                raise TimeoutError('Roblox polling disconnected')
            return SimpleNamespace(asset_id='98371',moderation_state='Approved',operation_path=op)
        with patch('real_estate.store.prepare_texture',side_effect=lambda root,part,p,stage:p), \
             patch('real_estate.store.create_image_asset',side_effect=create), \
             patch('real_estate.store.wait_for_operation',side_effect=wait):
            with self.assertRaisesRegex(TimeoutError,'disconnected'):
                self.store.publish('house_level1_01',self.creds,scope='house')
            pending=self.store.publications('house_level1_01')
            self.assertEqual(len(pending),1)
            self.assertEqual(pending[0]['asset_id'],'')
            result=self.store.publish('house_level1_01',self.creds,scope='house')
        self.assertEqual(submits,['create'])
        self.assertEqual(polls,['operations/unique-image']*2)
        self.assertTrue(result['publicationCurrent']['house'])
        self.assertEqual(len(self.store.publications('house_level1_01')),1)
        self.assertEqual(self.store.publications('house_level1_01')[0]['asset_id'],'98371')
        self.assertEqual(result['textures']['door']['assetId'],'98371')

    def test_model_retry_after_first_rig_success_continues_second_rig(self):
        submits=[]
        polls=[]
        def stage(root,source,dest,expected,textures):
            dest.mkdir(parents=True,exist_ok=True)
            for part in ('house','door'):(dest/f'{part}.fbx').write_bytes(part.encode())
        def create(path,**kw):
            submits.append(path.stem)
            return 'operations/'+path.stem
        def wait(op,**kw):
            polls.append(op)
            if op=='operations/door' and polls.count(op)==1:
                raise TimeoutError('temporary interrupted operation')
            return SimpleNamespace(asset_id=str(100+len(polls)),moderation_state='Approved',operation_path=op)
        with patch('real_estate.store.prepare_publication',side_effect=stage), \
             patch('real_estate.store.prepare_texture',side_effect=lambda root,part,path,stage:path), \
             patch('real_estate.store.create_model_asset',side_effect=create), \
             patch('real_estate.store.wait_for_operation',side_effect=wait):
            with self.assertRaises(TimeoutError):
                self.store.publish('house_level1_01',self.creds,scope='model')
            result=self.store.publish('house_level1_01',self.creds,scope='model')
        self.assertEqual(submits,['house','door'])
        self.assertEqual(polls,['operations/house','operations/door','operations/door'])
        self.assertTrue(result['publicationCurrent']['model'])
        self.assertEqual(len(self.store.publications('house_level1_01')),2)

    def test_browser_uses_background_endpoint_and_reports_progress(self):
        script=(ROOT/'system/control-center/static/real-estate.js').read_text('utf-8')
        self.assertIn("'/publish-async'",script)
        self.assertIn("'/publication-job'",script)
        self.assertIn('job.step',script)
        self.assertIn('real-estate.js?v=10',(ROOT/'system/control-center/static/index.html').read_text('utf-8'))

if __name__ == '__main__':
    unittest.main()
