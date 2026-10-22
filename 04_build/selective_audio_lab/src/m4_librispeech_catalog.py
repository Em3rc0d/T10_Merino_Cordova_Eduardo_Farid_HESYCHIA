"""Index *local* LibriSpeech FLACs into unreviewed M4 source candidates.

Source audio is never uploaded, and labels/partitions are only candidates pending
human review and cross-source independence audit. This does not unseal any test.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path
from m4_corpus_intake import CANDIDATE_FIELDS, digest

SUBSET = {'train-clean-100', 'dev-clean', 'test-clean'}


def speaker_id(path: Path) -> str:
    # LibriSpeech official layout speaker/chapter/speaker-chapter-utterance.flac
    name = path.stem.split('-')
    if len(name) < 3 or not name[0].isdigit() or not name[1].isdigit():
        raise ValueError(f"unexpected LibriSpeech filename: {path.name}")
    if path.parent.parent.name != name[0]:
        raise ValueError(f"speaker folder inconsistent: {path}")
    return name[0]


def generate(root: Path, output: Path, *, max_per_subset: int = 24) -> dict:
    if max_per_subset < 1:
        raise ValueError("max_per_subset must be positive")
    rows = []
    used_speakers = {}
    for subset in ('train-clean-100', 'dev-clean', 'test-clean'):
        base = root / 'LibriSpeech' / subset
        if not base.exists():
            base = root / subset
        matches = sorted(base.rglob('*.flac')) if base.exists() else []
        accepted = 0
        used_this_subset = set()
        # Favor distinct speakers. Allow only one utterance per speaker in the small pilot.
        for wav in matches:
            speaker = speaker_id(wav)
            if speaker in used_this_subset:
                continue
            old = used_speakers.get(speaker)
            if old and old != subset:
                raise ValueError(f"speaker {speaker} occurs in multiple upstream subsets")
            used_speakers[speaker] = subset
            used_this_subset.add(speaker)
            rows.append(dict(candidate_id=f'SLR12_{subset}_{wav.stem}',role='protected',
                             source_dataset='LibriSpeech_SLR12',origin_uri='https://openslr.elda.org/12/',
                             download_uri='',expected_sha256=digest(wav),
                             recording_group_id=f'Librispeech:{subset}:{speaker}:{wav.parent.name}',
                             speaker_id=f'LibriSpeech:{speaker}',license_id='CC-BY-4.0',
                             license_evidence_uri='https://openslr.elda.org/12/',
                             reviewed_license='',audio_path=str(wav.resolve()),split='',
                             isolation_review='',reviewer='',review_note=''))
            accepted += 1
            if accepted >= max_per_subset:
                break
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=CANDIDATE_FIELDS);w.writeheader();w.writerows(rows)
    return {'status':'DISCOVERY_ONLY_NOT_ADMITTED','total_candidates':len(rows),
            'by_subset':{x:sum(x in r['candidate_id'] for r in rows) for x in SUBSET},
            'output':str(output)}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--max-per-subset',type=int,default=24)
    a=p.parse_args()
    print(generate(a.root,a.out,max_per_subset=a.max_per_subset))
