"""Restore archived FLOAT-WAV container bytes without distributing audio samples.

The first pilot's PEAK timestamps are retained as original container metadata.
The reproduction receipt records the actual new run time, not the archived time.
"""
from __future__ import annotations

import base64
import hashlib
import os
import shutil
import struct
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf

from .common import create_json, read_json, sha256, write_json


def export_containers(root, output):
    root = Path(root)
    registry = read_json(root / "registry.json")
    headers = {}
    for asset in registry["assets"]:
        path = root / asset["path"]
        raw = path.read_bytes()
        if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE" or sf.info(path).subtype != "FLOAT":
            raise ValueError("Expected little-endian FLOAT WAV")
        offset = 12
        while offset + 8 <= len(raw):
            size = struct.unpack("<I", raw[offset + 4:offset + 8])[0]
            if raw[offset:offset + 4] == b"data":
                start, end = offset + 8, offset + 8 + size
                headers[asset["asset_id"]] = dict(
                    prefix=base64.b64encode(raw[:start]).decode(),
                    suffix=base64.b64encode(raw[end:]).decode(),
                    data_bytes=size, pcm_sha256=sha256(path))
                break
            offset += 8 + size + size % 2
        else:
            raise ValueError("WAV data chunk missing")
    create_json(output, dict(schema="m4-float-wav-containers-v1", audio_samples_included=False,
                            containers=headers,
                            purpose="Original derived-container metadata only; no source audio samples"))


def restore(root, registry_path, containers_path):
    root = Path(root).resolve()
    registry = read_json(registry_path)
    containers = read_json(containers_path)["containers"]
    if (root / "pcm").is_symlink():
        raise ValueError("Restore into a fresh physical PCM directory, not a shared symlink")
    backup = root / "registry_before_restore.json"
    if backup.exists():
        raise ValueError("This corpus was already restored; use a fresh reproduction directory")
    stage = root / (".restore-" + str(os.getpid()))
    stage.mkdir(exist_ok=False)
    restored = []
    try:
        for asset in registry["assets"]:
            relative = Path(asset["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Frozen PCM paths must remain relative to the corpus")
            dest = (root / relative).resolve()
            if not dest.is_relative_to(root) or not dest.is_file():
                raise ValueError("Missing/unsafe PCM path")
            samples, rate = sf.read(dest, dtype="float32")
            if rate != 16000 or samples.ndim != 1 or not np.isfinite(samples).all():
                raise ValueError("Decoded audio differs from the scientific contract")
            meta = containers[asset["asset_id"]]
            payload = samples.astype("<f4").tobytes()
            if len(payload) != meta["data_bytes"]:
                raise ValueError("Decoded sample length differs from the frozen recording")
            raw = base64.b64decode(meta["prefix"], validate=True) + payload + base64.b64decode(meta["suffix"], validate=True)
            digest = hashlib.sha256(raw).hexdigest()
            if digest != asset["pcm_sha256"] or digest != meta["pcm_sha256"]:
                raise ValueError("Samples/container do not reproduce the frozen SHA-256")
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            restored.append((target, dest))
        shutil.copyfile(root / "registry.json", backup)
        for target, dest in restored:
            os.replace(target, dest)
        shutil.copyfile(registry_path, root / "registry.json")
        report = dict(status="PASS_BYTE_EXACT_RESTORATION", files=len(restored),
                      reproduced_at_utc=datetime.now(timezone.utc).isoformat(),
                      registry_sha256=sha256(root / "registry.json"),
                      samples_changed=False, isolation_or_rights_approved=False,
                      note="Retains archived conversion metadata; filesystem and receipt use actual reproduction time")
        create_json(root / "restoration_report.json", report)
        return report
    finally:
        shutil.rmtree(stage, ignore_errors=True)
