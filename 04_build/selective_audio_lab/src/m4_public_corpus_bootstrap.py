"""HESYCHIA M4: auditable opt-in acquisition of OpenSLR speech and local background cataloguing.

No download by default; no licence or isolation auto-approval; no test audio
opened by the training pipeline. Run from 04_build/selective_audio_lab.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

# MD5 values copied from the publisher's resources/{31,12}/md5sum.txt.
# MD5 only checks whether archives match publisher listings; SHA256 is also
# computed locally for post-download provenance, not presented as publisher SHA.
ARCHIVES = {
    "mini-train": dict(filename="train-clean-5.tar.gz", subset="train-clean-5", collection="SLR31", md5="5df7d4e78065366204ca6845bb08f490", max_bytes=400_000_000, role="train_candidate"),
    "mini-dev": dict(filename="dev-clean-2.tar.gz", subset="dev-clean-2", collection="SLR31", md5="6d7ab67ac6a1d2c993d050e16d61080d", max_bytes=160_000_000, role="val_candidate"),
    "standard-test": dict(filename="test-clean.tar.gz", subset="test-clean", collection="SLR12", md5="32fa31d27d2e1cad72775fee3f4849a9", max_bytes=420_000_000, role="sealed_test_candidate"),
}
HOSTS = ("openslr.trmal.net", "openslr.elda.org", "openslr.magicdatatech.com")
CANDIDATE_FIELDS = (
    "candidate_id", "role", "source_dataset", "origin_uri", "download_uri",
    "expected_sha256", "recording_group_id", "speaker_id", "license_id",
    "license_evidence_uri", "reviewed_license", "audio_path", "split",
    "isolation_review", "reviewer", "review_note"
)


def checksums(path: Path) -> dict:
    md5 = hashlib.md5()
    sha = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            md5.update(block)
            sha.update(block)
    return {"md5": md5.hexdigest(), "sha256": sha.hexdigest(), "size_bytes": path.stat().st_size}


def archive_url(key: str, *, host: str = HOSTS[0]) -> str:
    if host not in HOSTS:
        raise ValueError("Unapproved mirror host")
    item = ARCHIVES[key]
    collection = "31" if item["collection"] == "SLR31" else "12"
    return f"https://{host}/resources/{collection}/{item['filename']}"


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlsplit(newurl)
        if u.scheme != "https" or u.hostname not in HOSTS or u.username or u.password or u.port:
            raise ValueError("Download redirected outside approved hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(key: str, folder: Path, *, host: str = HOSTS[0]) -> dict:
    info = ARCHIVES[key]
    url = archive_url(key, host=host)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{info['collection']}_{info['filename']}"
    if dest.exists():
        current = checksums(dest)
        if current["md5"] != info["md5"]:
            raise ValueError(f"Cached archive checksum mismatch: {dest}")
        return {"status": "ALREADY_VERIFIED", "dataset": key, "path": str(dest), "url": url, **current}
    temp = dest.with_suffix(dest.suffix + ".part")
    opener = urllib.request.build_opener(SafeRedirect())
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HESYCHIA-M4-research-intake/1"})
        with opener.open(req, timeout=60) as response, temp.open("wb") as out:
            count = 0
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                count += len(block)
                if count > info["max_bytes"]:
                    raise ValueError("Publisher archive exceeds declared conservative size ceiling")
                out.write(block)
        got = checksums(temp)
        if got["md5"] != info["md5"]:
            raise ValueError("Archive differs from official OpenSLR MD5; refusing extraction")
        temp.replace(dest)
        return {"status": "DOWNLOADED_VERIFIED", "dataset": key, "path": str(dest), "url": url, **got}
    finally:
        temp.unlink(missing_ok=True)


def _safe_member(member: tarfile.TarInfo, *, allowed_subset: str) -> Path:
    # Only regular FLAC / transcript files in expected LibriSpeech directory.
    posix = PurePosixPath(member.name)
    pieces = posix.parts
    if posix.is_absolute() or ".." in pieces or not pieces:
        raise ValueError(f"Archive includes unexpected/unsafe path: {member.name}")
    # Tar archives usually contain the two parent directory entries.
    if member.isdir() and pieces in (("LibriSpeech",), ("LibriSpeech", allowed_subset)):
        return Path(*pieces)
    if pieces[:2] != ("LibriSpeech", allowed_subset):
        raise ValueError(f"Archive includes unexpected/unsafe path: {member.name}")
    if member.issym() or member.islnk() or member.isdev() or not (member.isdir() or member.isfile()):
        raise ValueError(f"Disallowed member type: {member.name}")
    if member.isfile() and (member.size < 0 or member.size > 128_000_000):
        raise ValueError("Unexpectedly large archive member")
    if member.isfile() and Path(member.name).suffix not in {".flac", ".txt", ".trans"}:
        raise ValueError("Unexpected file extension in audio archive")
    return Path(*pieces)


def extract(key: str, folder: Path, output: Path, *, max_total_size: int = 10_000_000_000) -> dict:
    info = ARCHIVES[key]
    archive = folder / f"{info['collection']}_{info['filename']}"
    if not archive.is_file() or checksums(archive)["md5"] != info["md5"]:
        raise ValueError("Source archive absent or publisher MD5 check failed")
    dest = output / "LibriSpeech" / info["subset"]
    # Refuse partial/full collisions so repeated invocations do not silently change data.
    if dest.exists():
        raise ValueError(f"Destination already exists; inspect it before proceeding: {dest}")
    output.mkdir(parents=True, exist_ok=True)
    staging = output / (".staging-" + info["subset"])
    if staging.exists():
        raise ValueError(f"Interrupted staging exists; inspect manually: {staging}")
    staging.mkdir()
    nfiles, total = 0, 0
    try:
        with tarfile.open(archive, mode="r:gz") as tf:
            for member in tf:
                safe = _safe_member(member, allowed_subset=info["subset"])
                if len(safe.parts) < 3:
                    continue  # Publisher archive top-level folder entries.
                target = staging / Path(*safe.parts[2:])
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                nfiles += 1
                total += member.size
                if nfiles > 200_000 or total > max_total_size:
                    raise ValueError("Expanded archive size/member count exceeds safety ceiling")
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    raise ValueError("Duplicate archive member: " + member.name)
                stream = tf.extractfile(member)
                if stream is None:
                    raise ValueError("Could not extract regular file")
                with stream, target.open("xb") as out:
                    shutil.copyfileobj(stream, out, length=1024 * 1024)
        dest.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(dest)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {"status": "EXTRACTED_UNREVIEWED", "dataset": key, "path": str(dest), "files": nfiles, "bytes": total}


def index_speech(root: Path, out: Path, *, max_per_subset: int = 24, include_sealed: bool = False) -> dict:
    if max_per_subset < 1:
        raise ValueError("max_per_subset must be positive")
    subset_roles = {"train-clean-5": "train_candidate", "dev-clean-2": "val_candidate"}
    if include_sealed:
        subset_roles["test-clean"] = "sealed_test_candidate"
    seen_speakers = {}
    rows = []
    by_subset = {}
    for subset, review_split in subset_roles.items():
        src = root / "LibriSpeech" / subset
        found = 0
        if not src.exists():
            by_subset[subset] = 0
            continue
        # Choose at most one clip per speaker to maximize distinct speakers.
        for wav in sorted(src.rglob("*.flac")):
            name = wav.stem.split("-")
            if len(name) != 3 or not all(x.isdigit() for x in name):
                raise ValueError(f"Invalid LibriSpeech filename {wav.name}")
            speaker, chapter, _ = name
            if wav.parent.name != chapter or wav.parent.parent.name != speaker:
                raise ValueError(f"Noncanonical LibriSpeech layout: {wav}")
            prior = seen_speakers.get(speaker)
            if prior:
                if prior != subset:
                    raise ValueError(f"Cross-subset speaker overlap: {speaker}")
                continue
            seen_speakers[speaker] = subset
            sha = checksums(wav)["sha256"]
            rows.append(dict(candidate_id=f"SLR_{subset}_{wav.stem}", role="protected",
                             source_dataset=("SLR31" if subset != "test-clean" else "SLR12"),
                             origin_uri=("https://www.openslr.org/31/" if subset != "test-clean" else "https://www.openslr.org/12/"),
                             download_uri="", expected_sha256=sha,
                             recording_group_id=f"LibriSpeech:{speaker}:{chapter}",
                             speaker_id=f"LibriSpeech:{speaker}", license_id="CC-BY-4.0",
                             license_evidence_uri=("https://www.openslr.org/31/" if subset != "test-clean" else "https://www.openslr.org/12/"),
                             reviewed_license="", audio_path=str(wav.resolve()),split="",
                             isolation_review="", reviewer="",
                             review_note=f"Suggested role {review_split}; no split assigned; listen/verify prior to admission"))
            found += 1
            if found >= max_per_subset:
                break
        by_subset[subset] = found
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return {"status": "DISCOVERY_ONLY_NOT_ADMITTED", "candidate_rows": len(rows),
            "by_subset": by_subset, "test_not_inspected": not include_sealed, "path": str(out)}


def index_background(root: Path, out: Path, *, max_files: int = 100) -> dict:
    if max_files < 1:
        raise ValueError("max_files must be positive")
    rows = []
    for wav in sorted(x for x in root.rglob("*") if x.is_file() and x.suffix.lower() in (".wav", ".flac"))[:max_files]:
        # MS-SNSD includes CC0 Freesound and CC BY-SA DEMAND; filename alone
        # cannot tell which applies. Explicitly leave license unresolved.
        source_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(wav.relative_to(root)))
        rows.append(dict(candidate_id="BACKGROUND_"+source_id,role="background",
                         source_dataset="MS-SNSD/unverified_local",
                         origin_uri="https://github.com/microsoft/MS-SNSD",
                         download_uri="",expected_sha256=checksums(wav)["sha256"],
                         recording_group_id="ms-snsd:"+source_id,speaker_id="",
                         license_id="",license_evidence_uri="https://github.com/microsoft/MS-SNSD",
                         reviewed_license="",audio_path=str(wav.resolve()),split="",
                         isolation_review="",reviewer="",review_note="Source-specific licence and absence of voices/sirens must be reviewed"))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_FIELDS)
        writer.writeheader(); writer.writerows(rows)
    return {"status":"BACKGROUND_CANDIDATES_NOT_ADMITTED", "rows":len(rows),"path":str(out)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--action", choices=("status", "download", "extract", "index-speech", "index-background"), default="status")
    ap.add_argument("--dataset", choices=tuple(ARCHIVES))
    ap.add_argument("--archive-dir", type=Path, default=Path("data/m4_external/archives"))
    ap.add_argument("--root", type=Path, default=Path("data/m4_external"))
    ap.add_argument("--out", type=Path, default=Path("outputs/m4_corpus_v1/m4_external_candidates.csv"))
    ap.add_argument("--mirror", choices=HOSTS, default=HOSTS[0])
    ap.add_argument("--max-files", type=int, default=24)
    ap.add_argument("--include-sealed-test", action="store_true")
    args = ap.parse_args()
    if args.action == "status":
        res = {"status":"PLAN_ONLY_NO_DOWNLOAD", "datasets":{
            key:{"download_uri":archive_url(key),"published_md5":info["md5"],
                 "local_archive":str(args.archive_dir / (info["collection"]+"_"+info["filename"])),
                 "license":"CC-BY-4.0","use":info["role"]}
            for key,info in ARCHIVES.items()},
            "warnings":["No download unless --action download --dataset NAME",
                        "No automatic source/license/isolation acceptance",
                        "Test archive remains sealed until explicitly selected"]}
    elif args.action in ("download", "extract"):
        if not args.dataset:
            ap.error("--dataset required for download or extract")
        res = (download(args.dataset,args.archive_dir,host=args.mirror)
               if args.action=="download" else extract(args.dataset,args.archive_dir,args.root))
    elif args.action == "index-speech":
        res = index_speech(args.root,args.out,max_per_subset=args.max_files,include_sealed=args.include_sealed_test)
    else:
        res = index_background(args.root,args.out,max_files=args.max_files)
    print(json.dumps(res,indent=2,ensure_ascii=False))

if __name__ == "__main__":
    main()
