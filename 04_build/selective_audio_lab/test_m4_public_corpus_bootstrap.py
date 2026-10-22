"""Pure local tests; never hit external servers or inspect sealed test audio."""
import csv
import hashlib
import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from m4_public_corpus_bootstrap import (ARCHIVES, HOSTS, _safe_member, archive_url,
                                         checksums, download, extract, index_background, index_speech)


class M4PublicCorpusBootstrapTests(unittest.TestCase):
    def test_official_archive_name_and_hash(self):
        self.assertEqual(ARCHIVES['mini-train']['md5'], '5df7d4e78065366204ca6845bb08f490')
        self.assertIn('/31/train-clean-5.tar.gz', archive_url('mini-train'))

    def test_unapproved_mirror_rejected(self):
        with self.assertRaises(ValueError): archive_url('mini-train', host='other.example.org')

    def test_download_without_network_when_cached_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'SLR31_train-clean-5.tar.gz'
            p.write_bytes(b'bad data')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                download('mini-train', Path(t))

    def test_tar_blocks_symlink_and_traversal(self):
        for name in ('../../file.flac', '/tmp/file.flac', 'LibriSpeech/dev-clean-2/a.flac'):
            with self.assertRaises(ValueError):
                _safe_member(tarfile.TarInfo(name),allowed_subset='train-clean-5')
        m = tarfile.TarInfo('LibriSpeech/train-clean-5/1/2/1-2-3.flac')
        m.type = tarfile.SYMTYPE
        m.linkname = '/etc/passwd'
        with self.assertRaises(ValueError): _safe_member(m,allowed_subset='train-clean-5')

    def test_secure_extract_cached_small_fixture(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            fname = 'SLR31_train-clean-5.tar.gz'
            with tarfile.open(t / fname, 'w:gz') as f:
                for dirname in ("LibriSpeech/", "LibriSpeech/train-clean-5/"):
                    d = tarfile.TarInfo(dirname)
                    d.type = tarfile.DIRTYPE
                    f.addfile(d)
                content = b'fixture'
                info=tarfile.TarInfo('LibriSpeech/train-clean-5/1/2/1-2-3.flac')
                info.size = len(content)
                f.addfile(info,io.BytesIO(content))
            previous = ARCHIVES['mini-train']['md5']
            ARCHIVES['mini-train']['md5'] = checksums(t/fname)['md5']
            try:
                result=extract('mini-train', t,t/'corpus')
                self.assertEqual(result['status'],'EXTRACTED_UNREVIEWED')
                self.assertTrue((t/'corpus/LibriSpeech/train-clean-5/1/2/1-2-3.flac').is_file())
            finally:
                ARCHIVES['mini-train']['md5'] = previous

    def test_index_speech_no_sealed_test_default(self):
        with tempfile.TemporaryDirectory() as t:
            t=Path(t)
            train=t/'LibriSpeech/train-clean-5/100/200'
            dev=t/'LibriSpeech/dev-clean-2/101/201'
            test=t/'LibriSpeech/test-clean/102/202'
            for p,name in ((train,'100-200-0001.flac'),(dev,'101-201-0001.flac'),(test,'102-202-0001.flac')):
                p.mkdir(parents=True)
                (p/name).write_bytes(b'bytes')
            out=t/'candidates.csv'
            res=index_speech(t,out)
            self.assertEqual(res['candidate_rows'],2)
            self.assertTrue(res['test_not_inspected'])
            with out.open(encoding='utf-8') as source:
                rows=list(csv.DictReader(source))
            self.assertTrue(all(not r['split'] and not r['reviewed_license'] and not r['isolation_review'] for r in rows))
            self.assertFalse(any('test-clean' in r['audio_path'] for r in rows))

    def test_index_speech_rejects_speaker_overlap(self):
        with tempfile.TemporaryDirectory() as t:
            t=Path(t)
            for subset in ('train-clean-5','dev-clean-2'):
                folder=t/'LibriSpeech'/subset/'100'/'200'
                folder.mkdir(parents=True)
                (folder/'100-200-0001.flac').write_bytes(b'bytes')
            with self.assertRaisesRegex(ValueError, 'Cross-subset speaker overlap'):
                index_speech(t,t/'items.csv')

    def test_background_no_license_assumption(self):
        with tempfile.TemporaryDirectory() as t:
            t=Path(t)
            (t/'noise.wav').write_bytes(b'bytes')
            result=index_background(t,t/'items.csv')
            self.assertEqual(result['rows'],1)
            with (t/'items.csv').open(encoding='utf-8') as source:
                rows=list(csv.DictReader(source))
            self.assertEqual(rows[0]['license_id'],'')
            self.assertEqual(rows[0]['split'],'')
            self.assertEqual(rows[0]['role'],'background')

if __name__ == '__main__': unittest.main()
