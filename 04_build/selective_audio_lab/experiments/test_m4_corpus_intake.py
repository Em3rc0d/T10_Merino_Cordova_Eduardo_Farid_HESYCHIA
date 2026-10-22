"""No external network; all fixtures are synthetic and are not corpus evidence."""
import csv
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from m4_corpus_intake import (
    CANDIDATE_FIELDS, canonical_https, read_candidates, audio_quality,
    convert_approved_original, promote, digest, download_candidate,
)


class M4CorpusIntakeChecks(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.rows = []
        for split in ("train", "val", "test"):
            for role in ("target", "protected", "background"):
                id_ = split + '_' + role
                wav = self.root / (id_ + '.wav')
                rng = np.random.default_rng(len(id_) * 41 + len(split))
                sf.write(wav, rng.normal(0, 0.04, 5 * 16000), 16000)
                self.rows.append({
                    'candidate_id': id_, 'role': role, 'source_dataset': 'FIXTURE_NOT_REAL',
                    'origin_uri': f'https://freesound.org/people/fixture/sounds/123/',
                    'download_uri': '', 'expected_sha256': '', 'recording_group_id': id_,
                    'speaker_id': split + '_speaker' if role == 'protected' else '',
                    'license_id': 'CC0-1.0', 'license_evidence_uri': 'https://freesound.org/',
                    'reviewed_license': 'CONFIRMED', 'audio_path': str(wav), 'split': split,
                    'isolation_review': {'target':'ACCEPT_ISOLATED','protected':'ACCEPT_SPEECH','background':'ACCEPT_BACKGROUND'}[role],
                    'reviewer':'fixture-only', 'review_note':'synthetic fixture, do not use for thesis',
                })

    def registry(self):
        path = self.root / 'candidates.csv'
        with path.open('w', newline='', encoding='utf-8') as f:
            wr = csv.DictWriter(f, fieldnames=CANDIDATE_FIELDS)
            wr.writeheader();wr.writerows(self.rows)
        return path

    def test_reject_non_https_and_network_hosts(self):
        for url in ('http://cdn.freesound.org/a.mp3', 'https://127.0.0.1/foo',
                    'https://cdn.freesound.org.evil.test/a.mp3', 'file:///etc/hosts'):
            with self.assertRaises(ValueError):canonical_https(url, for_download=True)

    def test_allow_explicit_preview_https(self):
        self.assertEqual(canonical_https('https://cdn.freesound.org/previews/123/abc.mp3',for_download=True),
                         'https://cdn.freesound.org/previews/123/abc.mp3')

    def test_pass_with_exact_sources_and_human_fixture_reviews(self):
        result=promote(self.registry(),self.root/'out')
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(len(list(csv.DictReader((self.root/'out/m4_sources.csv').read_text().splitlines()))),9)

    def test_block_if_human_review_missing(self):
        self.rows[0]['isolation_review']='UNREVIEWED'
        self.assertEqual(promote(self.registry(),self.root/'out')['status'],'BLOCKED')
        self.assertFalse((self.root/'out/m4_sources.csv').exists())

    def test_block_incorrect_licensing(self):
        self.rows[0]['license_id']='CC-BY-NC-3.0'
        self.assertEqual(promote(self.registry(),self.root/'out')['status'],'BLOCKED')
        self.assertEqual(promote(self.registry(),self.root/'ncout',allow_nc_for_research=True)['status'],'PASS')

    def test_block_cross_split_recordings(self):
        self.rows[0]['recording_group_id']=self.rows[3]['recording_group_id']
        self.assertEqual(promote(self.registry(),self.root/'out')['status'],'BLOCKED')

    def test_block_cross_split_speaker(self):
        self.rows[1]['speaker_id']=self.rows[4]['speaker_id']
        self.assertEqual(promote(self.registry(),self.root/'out')['status'],'BLOCKED')

    def test_block_missing_audio_and_low_rms(self):
        self.rows[0]['audio_path']='does_not_exist.wav'
        self.assertEqual(promote(self.registry(),self.root/'out')['status'],'BLOCKED')
        self.rows[0]['audio_path']=str(self.root/(self.rows[0]['candidate_id']+'.wav'))
        sf.write(self.root/(self.rows[0]['candidate_id']+'.wav'),np.zeros(16000*5),16000)
        self.assertEqual(promote(self.registry(),self.root/'out2')['status'],'BLOCKED')

    def test_download_requires_pinned_sha_and_host(self):
        with self.assertRaises(ValueError):download_candidate('https://cdn.freesound.org/previews/123.mp3',self.root/'x.mp3','')
        with self.assertRaises(ValueError):download_candidate('https://localhost/x',self.root/'x.mp3','0'*64)

    def test_convert_lineage_and_quality(self):
        inp=self.root/'train_target.wav'
        out=self.root/'decoded.wav'
        info=convert_approved_original(inp,out)
        self.assertEqual(info['original_sha256'],digest(inp))
        self.assertEqual(info['converted_sha256'],digest(out))
        self.assertEqual(info['quality']['sample_rate_hz'],16000)
        self.assertEqual(info['quality']['warnings'],[])
        self.assertAlmostEqual(audio_quality(out)['duration_s'],5)

    def test_unassigned_discovery_candidate_never_promoted(self):
        for r in self.rows:r['split']=''
        self.assertEqual(promote(self.registry(),self.root/'out')['status'],'BLOCKED')
        self.assertFalse((self.root/'out/m4_sources.csv').exists())


if __name__ == '__main__':unittest.main()
