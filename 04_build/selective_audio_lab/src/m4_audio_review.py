"""Inspect source integrity and derived M4 audio quality; never admit a source."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import soundfile as sf
from m4_corpus_intake import audio_quality, digest, read_candidates

QUESTIONS = [
    "Is the target siren heard clearly in a usable interval?",
    "Are voices, traffic, music, alarms or other sources also heard?",
    "Is this a synthesized sound effect or field-acquired siren?",
    "Are reverb, codec artifacts, silence or other contamination audible?",
    "Have author attribution and reuse rights been confirmed?",
    "Are any other recordings derived from this same original?",
]

def build_report(*, registry: Path | str, candidate_id: str,
                 source: Path | str, wav: Path | str,
                 expected_wav_sha256: str = "") -> dict:
    candidates = [x for x in read_candidates(Path(registry))
                  if x["candidate_id"] == candidate_id]
    if len(candidates) != 1:
        raise ValueError("candidate_id must match exactly one entry")
    entry = candidates[0]
    if entry["role"] != "target":
        raise ValueError("this audit is for target sources")
    source, wav = Path(source), Path(wav)
    if not source.is_file() or not wav.is_file():
        raise FileNotFoundError("preview and decoded WAV must both exist")
    src_sha, wav_sha = digest(source), digest(wav)
    src_ok = src_sha.lower() == entry["expected_sha256"].lower()
    wav_ok = (wav_sha.lower() == expected_wav_sha256.lower()
              if expected_wav_sha256 else None)
    spec = sf.info(str(wav))
    quality = audio_quality(wav)
    problems = []
    if not entry["expected_sha256"]:
        problems.append("SOURCE_HASH_UNPINNED")
    elif not src_ok:
        problems.append("SOURCE_HASH_MISMATCH")
    if expected_wav_sha256 and not wav_ok:
        problems.append("DERIVED_WAV_HASH_MISMATCH")
    if spec.samplerate != 16000 or spec.channels != 1:
        problems.append("NOT_16KHZ_MONO")
    if spec.format != "WAV" or spec.subtype != "PCM_16":
        problems.append("NOT_WAV_PCM16")
    problems.extend("AUDIO_QC_" + warning for warning in quality["warnings"])
    return {
        "schema_version": "hesychia.m4-audio-review.v1",
        "candidate_id": candidate_id,
        "automatic_qc": "PASS" if not problems else "BLOCKED",
        "automatic_qc_problems": problems,
        "corpus_admission": "NOT_ADMITTED",
        "source": {
            "path": str(source), "sha256": src_sha,
            "catalog_sha256": entry["expected_sha256"],
            "checksum_match": src_ok,
            "mp3_preview": source.suffix.lower() == ".mp3",
            "publisher_page": entry["origin_uri"],
        },
        "wav": {
            "path": str(wav), "sha256": wav_sha,
            "checksum_matches_user_reported_wav": wav_ok,
            "reported_checksum_is_not_publisher_checksum": bool(expected_wav_sha256),
            "sample_rate": spec.samplerate, "channels": spec.channels,
            "format": spec.format, "subtype": spec.subtype,
            "numeric_quality": quality,
        },
        "license": {
            "catalog_license": entry["license_id"],
            "evidence_url": entry["license_evidence_uri"],
            "human_rights_review": "PENDING",
        },
        "acoustic_review": {
            "status": "PENDING", "isolated_target": None,
            "reviewer": None, "listening_notes": None, "questions": QUESTIONS,
        },
        "warnings": [
            "Numeric QC never proves isolation or license compliance.",
            "A converted preview is not the publisher's lossless original.",
            "No training split assigned; no corpus admission or CNN training.",
        ],
    }

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--candidate-id", required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--wav", type=Path, required=True)
    p.add_argument("--expected-wav-sha256", default="")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    result = build_report(registry=args.registry, candidate_id=args.candidate_id,
                          source=args.source, wav=args.wav,
                          expected_wav_sha256=args.expected_wav_sha256)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "automatic_qc": result["automatic_qc"],
        "corpus_admission": result["corpus_admission"],
        "acoustic_review": result["acoustic_review"]["status"],
        "problems": result["automatic_qc_problems"],
        "report": str(args.out)
    }, ensure_ascii=False, indent=2))
    if result["automatic_qc"] == "BLOCKED":
        raise SystemExit(2)

if __name__ == "__main__":
    main()
