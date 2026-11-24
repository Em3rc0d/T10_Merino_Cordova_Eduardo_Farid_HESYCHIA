"""HTTP integration checks for actual candidate inference and BLOCK precedence."""
import base64
import io
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import request, error
import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from web_server import create_server
import scientific_web


class ScientificWebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.server = create_server('127.0.0.1', 0, output_root=self.root / 'runs', evidence_root=self.root / 'evidence')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.tmp.cleanup()

    def get(self, path):
        with request.urlopen(self.base+path, timeout=30) as r:
            return json.loads(r.read())

    def post(self, data):
        req = request.Request(self.base+'/api/jobs/scientific', data=json.dumps(data).encode(), headers={'Content-Type':'application/json'})
        with request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def payload(self, **kwargs):
        wave = .08*np.sin(2*np.pi*230*np.arange(3200)/16000)
        out=io.BytesIO(); sf.write(out, wave, 16000, format='WAV', subtype='FLOAT')
        return dict(audio_base64=base64.b64encode(out.getvalue()).decode(), target='vacuum_cleaner', **kwargs)

    def await_job(self, job):
        for _ in range(150):
            row=self.get('/api/jobs/'+job['jobId'])
            if row['status'] in ('completed','failed'):
                return row
            time.sleep(.1)
        self.fail('job timeout')

    def test_real_checkpoint_and_inference(self):
        status=self.get('/api/scientific/status')
        self.assertTrue(status['ready']); self.assertFalse(status['scientific_go'])
        done=self.await_job(self.post(self.payload()))
        self.assertEqual(done['status'],'completed', done.get('error'))
        r=done['result']; self.assertEqual(r['engine'],'cnn_scientific_candidate')
        self.assertEqual(r['policy']['checkpoint_sha256'], scientific_web.EXPECTED_SHA)
        self.assertIsNone(r['metrics']); self.assertTrue(r['policy']['model_called'])
        saved=self.get(done['resultRef']); self.assertEqual(saved['run_id'],r['run_id'])
        history=self.get('/api/scientific/runs')['runs']
        self.assertEqual(history[0]['run_id'], r['run_id'])
        self.assertEqual(history[0]['engine'], 'cnn_scientific_candidate')
        for a in r['artifacts']:
            self.assertEqual(scientific_web.digest(self.root/'runs'/r['run_id']/a['name']),a['sha256'])

    def test_block_does_not_load_model_and_preserves_pcm(self):
        with patch('m4_scientific.inference.load_checkpoint', side_effect=AssertionError('BLOCK invoked model')):
            done=self.await_job(self.post(self.payload(block_protected=True)))
        self.assertEqual(done['status'],'completed',done.get('error'))
        r=done['result'];self.assertEqual(r['engine'],'bypass')
        self.assertTrue(r['pcm_bypass_verified']);self.assertFalse(r['policy']['model_called'])

    def test_corrupt_checkpoint_fails_without_oracle_fallback(self):
        fake=self.root/'bad';fake.mkdir(); (fake/'candidate.pt').write_bytes(b'bad')
        with patch.object(scientific_web,'SELECTED',fake):
            self.assertFalse(self.get('/api/scientific/status')['ready'])
            done=self.await_job(self.post(self.payload()))
        self.assertEqual(done['status'],'failed')
        self.assertEqual(list((self.root/'runs').iterdir()),[])

    def test_invalid_audio_and_target_rejected(self):
        for data in [dict(audio_base64='not base64',target='vacuum_cleaner'),dict(self.payload(),target='siren'),dict(self.payload(),block_protected='true')]:
            with self.assertRaises(error.HTTPError) as e:self.post(data)
            self.assertEqual(e.exception.code,400)

    def test_duration_guard_before_prediction(self):
        out=io.BytesIO();sf.write(out,np.zeros(16*8000),8000,format='WAV')
        with self.assertRaises(error.HTTPError) as e:
            self.post(dict(audio_base64=base64.b64encode(out.getvalue()).decode(),target='chainsaw'))
        self.assertEqual(e.exception.code,400)

    def test_ui_release_and_candidate_route(self):
        with request.urlopen(self.base) as r:html=r.read().decode()
        self.assertNotIn('Selective Audio Lab · PI9 / PI10',html)
        self.assertIn('CNN · Inferencia con audio WAV',html)
        self.assertIn('/api/jobs/scientific',html)

if __name__=='__main__':unittest.main()
