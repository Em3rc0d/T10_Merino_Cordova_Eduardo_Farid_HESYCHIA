"""M4 source intake: acquisition, byte audit, audio QC, manual gate, and promotion.

CANDIDATES ARE NOT ACCEPTED TRAINING DATA. Sound tags or catalogs do not certify
source isolation or rights. Produces M4 sources only after human review.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf

CANDIDATE_FIELDS = (
    "candidate_id", "role", "source_dataset", "origin_uri", "download_uri",
    "expected_sha256", "recording_group_id", "speaker_id", "license_id",
    "license_evidence_uri", "reviewed_license", "audio_path", "split",
    "isolation_review", "reviewer", "review_note"
)
SOURCE_FIELDS = (
    "source_id", "role", "split", "recording_id", "speaker_id",
    "path", "sha256", "license", "reference_grade"
)
ALLOWED_HOSTS = frozenset(("cdn.freesound.org", "freesound.org", "bigsoundbank.com", "www.bigsoundbank.com"))
ROLES = {"target", "protected", "background"}
SPLITS = {"train", "val", "test"}
LICENCES = {"CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-NC-3.0"}
REVIEWS = {"target": "ACCEPT_ISOLATED", "protected": "ACCEPT_SPEECH", "background": "ACCEPT_BACKGROUND"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_BYTES = 25 * 1024 * 1024


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_https(url: str, *, for_download: bool = False) -> str:
    if not url.strip():
        if for_download:
            raise ValueError("download_uri missing; manually obtain a licensed original")
        return ""
    u = urllib.parse.urlparse(url)
    if u.scheme != "https" or not u.hostname or u.username or u.password or u.port:
        raise ValueError("source URL must be HTTPS without credentials or port")
    if for_download and u.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"download host not whitelisted: {u.hostname}")
    if u.fragment:
        raise ValueError("fragments not supported in source URLs")
    return url


class CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        canonical_https(newurl, for_download=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_candidate(url: str, destination: Path, expected_hash: str, *, max_bytes: int = MAX_BYTES):
    canonical_https(url, for_download=True)
    if not SHA256.fullmatch(expected_hash):
        raise ValueError("download requires source-provided SHA256; no unverified download")
    if destination.exists():
        if digest(destination) != expected_hash:
            raise ValueError("existing file checksum mismatch")
        return "ALREADY_VERIFIED"
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".part")
    opener = urllib.request.build_opener(CheckedRedirect())
    try:
        with opener.open(urllib.request.Request(url, headers={"User-Agent": "HESYCHIA-academic-corpus-intake/1"}), timeout=20) as response, tmp.open("wb") as out:
            total = 0
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("download exceeded byte limit")
                out.write(chunk)
        if digest(tmp) != expected_hash:
            raise ValueError("download SHA256 differs from declared source bytes")
        tmp.replace(destination)
    finally:
        tmp.unlink(missing_ok=True)
    return "DOWNLOADED_VERIFIED"


def read_candidates(registry: Path):
    with registry.open(encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        missing = set(CANDIDATE_FIELDS) - set(rd.fieldnames or [])
        if missing:
            raise ValueError(f"missing fields: {sorted(missing)}")
        rows = [{k: (row.get(k) or "").strip() for k in CANDIDATE_FIELDS} for row in rd]
    if not rows:
        raise ValueError("candidate registry empty")
    ids = [r["candidate_id"] for r in rows]
    if any(not x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("candidate_id empty or duplicate")
    for r in rows:
        if r["role"] not in ROLES:
            raise ValueError(f"unexpected role: {r['role']}")
        canonical_https(r["origin_uri"])
        if r["download_uri"]:
            canonical_https(r["download_uri"], for_download=True)
        if r["expected_sha256"] and not SHA256.fullmatch(r["expected_sha256"].lower()):
            raise ValueError(f"bad expected_sha256: {r['candidate_id']}")
    return rows


def audio_quality(path: Path, *, min_seconds: float = 4.0) -> dict:
    """Cheap objective QC, not an acoustic source-isolation classifier."""
    if not path.is_file():
        raise FileNotFoundError(path)
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if not len(audio) or sr <= 0 or not np.isfinite(audio).all():
        raise ValueError("invalid audio")
    mono = np.mean(audio.astype(np.float64), axis=1)
    rms = float(np.sqrt(np.mean(mono**2)))
    result = {
        "duration_s": len(audio) / sr, "sample_rate_hz": sr,
        "channels": int(audio.shape[1]), "rms": rms,
        "peak": float(np.max(np.abs(audio))),
        "fraction_near_clip": float(np.mean(np.abs(audio) >= 0.999)),
    }
    warnings = []
    if result["duration_s"] < min_seconds:
        warnings.append("SHORTER_THAN_EXPERIMENT_SCENE")
    if rms < 0.001:
        warnings.append("LOW_RMS")
    if result["fraction_near_clip"] > 0.005:
        warnings.append("SIGNIFICANT_CLIPPING")
    result["warnings"] = warnings
    return result


def convert_approved_original(original: Path, destination: Path, *, ffmpeg_bin="ffmpeg") -> dict:
    """Convert exact source bytes to a reproducible 16 kHz PCM WAV; store lineage."""
    if not original.is_file():
        raise FileNotFoundError(original)
    destination.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
           "-i", str(original), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(destination)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    if proc.returncode:
        destination.unlink(missing_ok=True)
        raise ValueError(f"FFmpeg conversion failed: {proc.stderr[-500:]}")
    q = audio_quality(destination)
    return {"original_sha256": digest(original), "converted_sha256": digest(destination), "quality": q,
            "conversion": "ffmpeg mono 16kHz PCM16 (FFmpeg version must be captured per run)"}


def promote(registry: Path, out_dir: Path, *, allow_nc_for_research: bool = False, min_groups_per_split: int = 1) -> dict:
    """Promote only human-reviewed WAV/FLAC; never certify isolation by label alone."""
    if min_groups_per_split < 1:
        raise ValueError("minimum original sources per split must be >=1")
    rows = read_candidates(registry)
    problems, promoted, evidence = [], [], []
    split_by_group, speaker_split, hash_split = defaultdict(set), defaultdict(set), defaultdict(set)
    seen = Counter()
    groups_per_cell = defaultdict(set)
    for r in rows:
        cid, role, split = r["candidate_id"], r["role"], r["split"]
        # Unreviewed discovery candidates are legal to keep in the registry.
        if not split:
            continue
        if split not in SPLITS:
            problems.append(f"{cid}: invalid split")
            continue
        if r["reviewed_license"] != "CONFIRMED" or r["license_id"] not in LICENCES or not r["license_evidence_uri"]:
            problems.append(f"{cid}: license requires explicit manual confirmation and evidence URL")
            continue
        if r["license_id"] == "CC-BY-NC-3.0" and not allow_nc_for_research:
            problems.append(f"{cid}: non-commercial source excluded in default posture")
            continue
        if r["isolation_review"] != REVIEWS[role] or not r["reviewer"] or not r["review_note"]:
            problems.append(f"{cid}: human audio/role review not recorded")
            continue
        if not r["recording_group_id"]:
            problems.append(f"{cid}: recording source group missing")
            continue
        if role == "protected" and not r["speaker_id"]:
            problems.append(f"{cid}: protected speaker missing")
            continue
        audio = Path(r["audio_path"])
        if not audio.is_absolute():
            audio = registry.parent / audio
        if not audio.is_file() or audio.suffix.lower() not in {".wav", ".flac"}:
            problems.append(f"{cid}: inspected decoded WAV/FLAC unavailable")
            continue
        try:
            stats = audio_quality(audio)
            if stats["warnings"]:
                problems.append(f"{cid}: audio quality failed {','.join(stats['warnings'])}")
                continue
            sha = digest(audio)
        except Exception as e:
            problems.append(f"{cid}: cannot audit audio ({e})")
            continue
        group = r["recording_group_id"]
        split_by_group[group].add(split)
        if role == "protected":
            speaker_split[r["speaker_id"]].add(split)
        hash_split[sha].add(split)
        seen[(split,role)] += 1
        groups_per_cell[(split,role)].add(group)
        grade = {"target": "isolated", "protected": "speech", "background": "background"}[role]
        promoted.append({"source_id":cid,"role":role,"split":split,"recording_id":group,
                         "speaker_id":r["speaker_id"],"path":str(audio.resolve()),"sha256":sha,
                         "license":r["license_id"],"reference_grade":grade})
        evidence.append({"candidate_id":cid,"origin_uri":r["origin_uri"],"reviewer":r["reviewer"],
                         "review_note":r["review_note"],"audio_sha256":sha,"quality":stats})
    for dimension, groups in (("recording_group_id",split_by_group),("speaker_id",speaker_split),("decoded_audio_sha256",hash_split)):
        conflicts = [k for k,v in groups.items() if len(v)>1]
        if conflicts:
            problems.append(f"cross-split {dimension} conflict: {len(conflicts)} groups")
    for sp in sorted(SPLITS):
        for role in sorted(ROLES):
            if len(groups_per_cell[(sp,role)]) < min_groups_per_split:
                problems.append(f"{sp}/{role}: insufficient independent recording groups {len(groups_per_cell[(sp,role)])}/{min_groups_per_split}")
    result = {"status":"PASS" if not problems else "BLOCKED", "candidate_rows":len(rows),
              "reviewed_accepted_rows":len(promoted),"problems":problems,
              "counts":{f"{sp}/{role}":seen[(sp,role)] for sp in sorted(SPLITS) for role in sorted(ROLES)},
              "warning":"Manual reviewer confirms isolation; tool only checks declared state and technical audio integrity.",
              "evidence":evidence}
    out_dir.mkdir(parents=True,exist_ok=True)
    (out_dir/"promotion_audit.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    if problems:
        (out_dir/"m4_sources.csv").unlink(missing_ok=True)
    else:
        with (out_dir/"m4_sources.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=SOURCE_FIELDS)
            w.writeheader();w.writerows(promoted)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--candidates",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--action",choices=("inspect","promote","download-one"),default="inspect")
    p.add_argument("--candidate-id")
    p.add_argument("--allow-nc-research",action="store_true")
    a=p.parse_args()
    if a.action=="promote":
        res=promote(a.candidates,a.out,allow_nc_for_research=a.allow_nc_research)
    elif a.action=="inspect":
        rows=read_candidates(a.candidates)
        res={"status":"CANDIDATES_NOT_CERTIFIED","rows":len(rows),"by_role":dict(Counter(r["role"] for r in rows)),
             "with_source_hash":sum(bool(r["expected_sha256"]) for r in rows),
             "with_manual_acceptance":sum(r["isolation_review"] in REVIEWS.values() for r in rows)}
    else:
        rows=[r for r in read_candidates(a.candidates) if r["candidate_id"]==a.candidate_id]
        if len(rows)!=1:
            raise SystemExit("--candidate-id must match exactly one candidate")
        r=rows[0]
        if not r["expected_sha256"] or not r["download_uri"]:
            raise SystemExit("candidate has no pinned source bytes and public preview URI")
        suffix=Path(urllib.parse.urlparse(r["download_uri"]).path).suffix or ".bin"
        dest=a.out/(r["candidate_id"].replace(":","_")+suffix)
        res={"status":download_candidate(r["download_uri"],dest,r["expected_sha256"].lower()),"path":str(dest),"sha256":digest(dest)}
    print(json.dumps(res,ensure_ascii=False,indent=2))
    if res.get("status")=="BLOCKED":
        raise SystemExit(2)

if __name__=="__main__":main()
