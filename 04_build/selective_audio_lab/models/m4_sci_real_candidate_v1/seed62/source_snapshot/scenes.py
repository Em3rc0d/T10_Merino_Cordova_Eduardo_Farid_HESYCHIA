"""Reproducible real-recording mixtures, with source membership fixed before training."""
from __future__ import annotations

import math
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np
import soundfile as sf

from .common import canonical_hash, read_json, write_json
from .corpus import TARGETS, SR


@lru_cache(maxsize=600)
def read_pcm(path):
    x, rate = sf.read(path, dtype="float32")
    if rate != SR or x.ndim != 1 or not np.isfinite(x).all():
        raise ValueError("PCM differs from declared mono 16 kHz contract")
    return x


def condition_key(recipe):
    other = TARGETS[1 - recipe["target_id"]] in recipe["parts"]
    return (recipe["target_id"], int(recipe["target_present"]), int(other),
            int(recipe["speech_present"]), int(recipe["alert_present"]))


def coverage(recipes):
    import itertools
    counts = Counter(condition_key(r) for r in recipes)
    expected = list(itertools.product(range(2), range(2), range(2), range(2), range(2)))
    missing = [list(k) for k in expected if not counts[k]]
    return dict(status="PASS" if not missing else "GAPS", required_conditions=32,
                observed_conditions=len(counts), missing=missing,
                fields=["requested_class", "target_present", "other_present", "speech_present", "alert_present"],
                counts={"/".join(map(str, k)): v for k, v in sorted(counts.items())},
                pure_speech_scenes=sum(r["speech_present"] and set(r["parts"]) == {"speech"} for r in recipes),
                silence_scenes=sum(not r["parts"] for r in recipes))


def make_recipes(root, registry, *, counts=(1600, 160, 160), seconds=2., seed=2710,
                 condition_version="legacy-v1"):
    if len(counts) != 3 or min(counts) < 2 or seconds <= 0 or round(seconds * SR) % 160:
        raise ValueError("Invalid scene counts/duration")
    result = {}
    for split, count, split_seed in zip(("train", "val", "test"), counts,
                                         (seed, seed + 10000, seed + 20000)):
        rng = np.random.default_rng(split_seed)
        rows = [a for a in registry["assets"] if a["split"] == split]
        pools = {cls: [a for a in rows if a["class"] == cls or a["role"] == cls]
                 for cls in TARGETS + ("speech", "background", "alert")}
        recipes = []
        for i in range(count):
            target_id = i % 2
            # Explicit negatives, concurrent targets, no-voice and alert controls.
            if condition_version == "legacy-v1":
                target_present = i % 5 != 0
                other_present = i % 3 == 0 or not target_present
                speech_present = i % 13 != 0
                alert_present = i % 10 == 3
                background_present = True
            elif condition_version == "full-factorial-v2":
                combo = (i // 2) % 4
                target_present = combo in (1, 3)
                other_present = combo in (2, 3)
                speech_present = (i // 8) % 4 != 0
                alert_present = (i // 32) % 5 == 3
                background_present = not (not target_present and not other_present and
                    not alert_present and (i // 8) % 2 == 0)
            else:
                raise ValueError("Unknown scene condition design")
            present = {TARGETS[target_id]: target_present,
                       TARGETS[1 - target_id]: other_present,
                       "speech": speech_present, "background": background_present, "alert": alert_present}
            parts = {}
            for cls, active in present.items():
                if not active:
                    continue
                asset = pools[cls][int(rng.integers(len(pools[cls])))]
                # Offsets are stored, and sampling retries only on nearly silent crops.
                x = read_pcm(str(Path(root) / asset["path"]))
                samples = int(seconds * SR)
                for _ in range(12):
                    offset = int(rng.integers(max(1, len(x) - samples + 1)))
                    segment = x[offset:offset + samples]
                    if float(np.mean(segment.astype(np.float64) ** 2)) > 1e-8:
                        break
                else:
                    raise ValueError(f"No usable segment in {asset['asset_id']}")
                db = float(rng.choice([-6., 0., 6.])) if cls in TARGETS else (
                    -12. if cls == "background" else (-3. if cls == "alert" else 0.))
                # Temporal placement supplies partial overlaps; validation/test are fixed too.
                onset = int(rng.integers(0, samples // 4)) if cls in TARGETS and i % 4 == 0 else 0
                parts[cls] = dict(asset_id=asset["asset_id"], offset=offset, onset=onset,
                                  relative_db=db, source_group=asset["source_group"])
            recipes.append(dict(scene_id=f"{split}-{i:05d}", split=split,
                                target_id=target_id, target_present=target_present,
                                alert_present=alert_present, speech_present=speech_present,
                                seconds=seconds, global_rms=float(rng.uniform(.035, .10)),
                                parts=parts))
        result[split] = recipes
    return result


def build_scene(root, registry, recipe):
    assets = {a["asset_id"]: a for a in registry["assets"]}
    n = int(recipe["seconds"] * SR)
    stems = {k: np.zeros(n, dtype=np.float32) for k in TARGETS + ("speech", "background", "alert")}
    for cls, part in recipe["parts"].items():
        asset = assets[part["asset_id"]]
        if asset["split"] != recipe["split"]:
            raise ValueError("Recipe crosses a source partition")
        original = read_pcm(str(Path(root) / asset["path"]))
        x = original[part["offset"]:part["offset"] + n].copy()
        x = np.pad(x, (part["onset"], max(0, n - len(x) - part["onset"])))[:n]
        rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
        if rms < 1e-6:
            raise ValueError("Recipe has silent active source")
        stems[cls] = (x / rms * recipe["global_rms"] * 10 ** (part["relative_db"] / 20)).astype(np.float32)
    mix = sum(stems.values())
    scale = max(1., float(np.max(np.abs(mix))) / .95)
    stems = {k: v / scale for k, v in stems.items()}
    return sum(stems.values()).astype(np.float32), stems


def save_recipes(root, registry, **kwargs):
    root = Path(root)
    if (root / "recipes_train.json").exists():
        raise ValueError("Scene recipes already exist; do not overwrite an experiment")
    resolved = dict(counts=(1600, 160, 160), seconds=2., seed=2710)
    resolved.update(kwargs)
    result = make_recipes(root, registry, **resolved)
    audits = {s: coverage(r) for s, r in result.items()}
    if resolved.get("condition_version") == "full-factorial-v2" and any(a["status"] != "PASS" for a in audits.values()):
        raise ValueError("Full-factorial design needs all 32 class/presence conditions in each split")
    hashes = {}
    for split, recipes in result.items():
        write_json(root / f"recipes_{split}.json", recipes)
        hashes[split] = canonical_hash(recipes)
    write_json(root / "scene_contract.json", dict(
        schema="m4-sci-mixtures-v1", recipe_hashes=hashes, targets=list(TARGETS),
        registry_sha256=canonical_hash(registry),
        counts={s: len(r) for s, r in result.items()},
        description="Real recordings mixed digitally, with known candidate pseudo-stems; "
                    "relative_db is component RMS relative to common reference, not total-mixture SNR",
        reference_gain_floor_db=12., sample_rate=SR,
        test_sealed=True, generation_config=resolved))
    write_json(root / "condition_coverage.json", audits)
    return hashes


def load_recipes(root, split):
    contract = read_json(Path(root) / "scene_contract.json")
    recipes = read_json(Path(root) / f"recipes_{split}.json")
    if canonical_hash(recipes) != contract["recipe_hashes"][split]:
        raise ValueError("Frozen scene recipes changed")
    return recipes
