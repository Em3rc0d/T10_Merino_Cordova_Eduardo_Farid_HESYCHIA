"""One-shot frozen test, frozen-gain stem decomposition and paired baselines."""
from __future__ import annotations

import csv
import hashlib
import math
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from pystoi import stoi

from .common import canonical_hash, create_json, read_json, sha256, write_json
from .corpus import TARGETS, SR, load_registry
from .model import features, frontend_contract, load_checkpoint, spectrum, synthesize
from .scenes import build_scene, load_recipes, condition_key, coverage
from .policy import resolve, POLICY_VERSION

THRESHOLDS = {"A_target_min_db": 6., "A_protected_max_db": 1.}


def evaluator_hash():
    # Freeze all code that can affect recipes, predictions and metrics.
    files = {p.name: sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))}
    files["legacy_S10A_policy.py"] = sha256(Path(__file__).parent.parent / "policy.py")
    return canonical_hash(files)


def runtime_versions():
    import scipy
    import soundfile
    import pystoi
    return dict(torch=str(torch.__version__), numpy=np.__version__, scipy=scipy.__version__,
                soundfile=soundfile.__version__, pystoi=pystoi.__version__)


def freeze(root, checkpoints, output, *, event_checkpoint=None, event_calibration=None, selection_path=None):
    if bool(event_checkpoint) != bool(event_calibration) or not checkpoints:
        raise ValueError("Need CNN checkpoints and a complete optional M2 checkpoint/calibration pair")
    root = Path(root).resolve()
    freeze_root = Path(output).resolve().parent
    repo_root = Path(__file__).resolve().parents[4]
    protocol_files = ("SOURCE_OF_TRUTH.md", "02_plan/PI11_M4_CNN_FIRST_STREAMING_SECOND.md",
                      "03_architecture/M4_SCIENTIFIC_TRAINING_CONTRACT.md",
                      "docs/PROTOCOLO_POST_PARCIAL_S9_S13.md")
    registry = read_json(root / "registry.json")
    scenes = read_json(root / "scene_contract.json")
    models = []
    for path in checkpoints:
        path = Path(path).resolve()
        model, obj = load_checkpoint(path)
        manifest_path = path.parent / "training_manifest.json"
        if obj["training_manifest_sha256"] != sha256(manifest_path):
            raise ValueError("Training manifest/checkpoint mismatch")
        if obj["corpus_sha256"] != canonical_hash(registry):
            raise ValueError("Checkpoint was not trained on this source corpus")
        training_summary = read_json(path.parent / "summary.json")
        models.append(dict(path=os.path.relpath(path, freeze_root), sha256=sha256(path), seed=obj["config"]["seed"],
                           loss=obj["config"]["loss"], conditioning=obj["config"].get("conditioning", "class"),
                           architecture=obj["model_config"].get("architecture", "temporal"),
                           training_scene_contract_sha256=obj["scene_contract_sha256"],
                           training_status=training_summary["status"],
                           epochs_logged=training_summary.get("epochs_run", training_summary.get("epochs_logged")),
                           best_epoch=obj["epoch"]))
    event_info = None
    if event_checkpoint is not None:
        from .events import load_events
        _, calibration = load_events(event_checkpoint, event_calibration)
        if calibration["corpus_sha256"] != canonical_hash(registry) or calibration["scene_contract_sha256"] != canonical_hash(scenes):
            raise ValueError("Event model uses a different source/scene contract")
        event_info = dict(checkpoint=os.path.relpath(Path(event_checkpoint).resolve(), freeze_root),
                          calibration=os.path.relpath(Path(event_calibration).resolve(), freeze_root),
                          checkpoint_sha256=sha256(event_checkpoint),
                          calibration_sha256=sha256(event_calibration))
    selection = None
    if selection_path is not None:
        selected = read_json(selection_path)
        if selected["checkpoint_sha256"] not in {m["sha256"] for m in models}:
            raise ValueError("Validation-selected checkpoint is not in the frozen comparison")
        selection = dict(path=os.path.relpath(Path(selection_path).resolve(), freeze_root),
                         sha256=sha256(selection_path), checkpoint_sha256=selected["checkpoint_sha256"])
    value = dict(schema="m4-sci-test-freeze-v1", corpus_sha256=canonical_hash(registry),
                 scene_contract_sha256=canonical_hash(scenes),
                 test_recipe_sha256=scenes["recipe_hashes"]["test"], checkpoints=models,
                 evaluation_code_sha256=evaluator_hash(), thresholds=THRESHOLDS,
                 runtime_versions=runtime_versions(),
                 protocol_sha256={name: sha256(repo_root / name) for name in protocol_files},
                 thresholds_source="docs/PROTOCOLO_POST_PARCIAL_S9_S13.md and docs/M4_METRICS_AUDIT.md",
                 predictor_inputs="mixture features and requested target class only",
                 event_model=event_info,
                 validation_selection=selection,
                 policy_version=POLICY_VERSION,
                 mode="ASSISTED_TARGET_WITH_ANNOTATED_ALERT_POLICY plus estimated M2 gate if frozen",
                 policy="BLOCK if protected alert annotation supplied; bypass before model inference",
                 baselines=["unprocessed", "causal_minimum_statistics", "oracle_IRM_privileged"],
                 historical_cnn="not applicable: drilling_synthetic-only taxonomy; no fabricated class mapping",
                 metrics="A_target/A_protected from fixed mixture-predicted gain applied to stems; "
                         "SI-SDRi and STOI of actual mixture output; no clean-stem model input",
                 uncertainty="95% source-group bootstrap, equal group means, 2000 resamples; "
                             "speech metrics grouped by speaker; crossed target/speaker dependence remains",
                 independent_field_recording=False, m2_integration_validated=False,
                 acceptance="Report per-scene target>=6 dB AND protected<=1 dB; "
                            "no aggregate pass-rate threshold invented; scientific GO remains closed "
                            "without source review, independent field evaluation and integrated M2 evaluation")
    create_json(output, value)
    return value


def attenuation(before, after):
    p0, p1 = float(np.sum(before.astype(np.float64) ** 2)), float(np.sum(after.astype(np.float64) ** 2))
    if p0 < 1e-10:
        return None
    return float(10 * np.log10(max(p0, 1e-20) / max(p1, 1e-20)))


def si_sdr(estimate, reference):
    x = np.asarray(estimate, dtype=np.float64)
    r = np.asarray(reference, dtype=np.float64)
    x, r = x - x.mean(), r - r.mean()
    power = float(r @ r)
    if power < 1e-10 or float(x @ x) < 1e-10:
        return None
    desired = r * float(x @ r) / power
    error = x - desired
    return float(10 * np.log10(max(float(desired @ desired), 1e-20) / max(float(error @ error), 1e-20)))


def classic_gain(spec, cap_db=12.):
    power = spec.abs().square()
    floor = 10 ** (-cap_db / 20)
    result = torch.ones_like(power)
    # A deliberately simple, class-agnostic causal DSP comparator, no clean references.
    smooth = power[0].clone()
    noise = smooth.clone()
    for frame in range(1, len(power)):
        smooth = .9 * smooth + .1 * power[frame]
        noise = torch.minimum(noise * 1.005 + 1e-8, smooth)
        result[frame] = torch.sqrt((1 - noise / power[frame].clamp_min(1e-8)).clamp_min(floor ** 2))
    return result


def group_ci(rows, metric, group_key):
    groups = defaultdict(list)
    for row in rows:
        if row.get(metric) is not None and row.get(group_key):
            groups[row[group_key]].append(float(row[metric]))
    means = np.array([np.mean(v) for v in groups.values()])
    if not len(means):
        return None
    rng = np.random.default_rng(271099)
    samples = rng.choice(means, size=(2000, len(means)), replace=True).mean(axis=1)
    return dict(group_mean=float(means.mean()), ci95=[float(x) for x in np.quantile(samples, [.025, .975])],
                groups=len(means), scenes=sum(len(v) for v in groups.values()))


def _row(method, seed, recipe, mix, stems, spec, gain, *, decision=None, mode="assisted"):
    n = len(mix)
    # Use the SAME mask estimated from the mixture on every stem.
    waves = torch.from_numpy(np.stack([mix, stems[TARGETS[recipe["target_id"]]], stems["speech"], stems["alert"],
                                       stems[TARGETS[1 - recipe["target_id"]]]]))
    stem_specs = spectrum(waves)
    with torch.no_grad():
        processed = synthesize(stem_specs * gain[None], n).numpy()
    out, target_out, speech_out, alert_out, nontarget_out = processed
    decision = decision or ("BLOCK" if recipe["alert_present"] else "ALLOW")
    target = stems[TARGETS[recipe["target_id"]]]
    speech = stems["speech"]
    at, ap = attenuation(target, target_out), attenuation(speech, speech_out)
    before, after = si_sdr(mix, speech), si_sdr(out, speech)
    desired = mix - (1 - 10 ** (-12 / 20)) * target
    desired_score = si_sdr(out, desired)
    if recipe["speech_present"]:
        stoi_in = float(stoi(speech, mix, SR, extended=False))
        stoi_out = float(stoi(speech, out, SR, extended=False))
    else:
        stoi_in = stoi_out = None
    both = (at >= THRESHOLDS["A_target_min_db"] and ap <= THRESHOLDS["A_protected_max_db"]
            if at is not None and ap is not None and not recipe["alert_present"] else None)
    return dict(scene_id=recipe["scene_id"], method=method, seed=seed,
                target_class=TARGETS[recipe["target_id"]], target_present=recipe["target_present"],
                speech_present=recipe["speech_present"], alert_present=recipe["alert_present"],
                decision=decision, mode=mode,
                target_group=recipe["parts"].get(TARGETS[recipe["target_id"]], {}).get("source_group", ""),
                nontarget_group=recipe["parts"].get(TARGETS[1 - recipe["target_id"]], {}).get("source_group", ""),
                speaker_group=recipe["parts"].get("speech", {}).get("source_group", ""),
                mixture_pcm_sha256=hashlib.sha256(mix.astype("<f4").tobytes()).hexdigest(),
                A_target_db=at, A_protected_db=ap, A_alert_db=attenuation(stems["alert"], alert_out),
                A_nontarget_db=attenuation(stems[TARGETS[1 - recipe["target_id"]]], nontarget_out),
                SI_SDRi_protected_db=after - before if before is not None and after is not None else None,
                SI_SDR_desired_db=desired_score, STOI_input=stoi_in, STOI_output=stoi_out,
                STOI_delta=stoi_out - stoi_in if stoi_in is not None else None,
                target_ok=at >= 6 if at is not None and not recipe["alert_present"] else None,
                protected_ok=ap <= 1 if ap is not None else None, both_ok=both,
                target_absent_false_attenuation=ap > 1 if ap is not None and not recipe["target_present"] else None,
                max_abs_output=float(np.max(np.abs(out))), gain_mean=float(gain.mean())), out


def evaluate(root, freeze_path, output, *, save_audio=8):
    root, freeze_path, output = Path(root), Path(freeze_path), Path(output)
    frozen = read_json(freeze_path)
    resolve_frozen = lambda path: Path(path) if Path(path).is_absolute() else freeze_path.resolve().parent / path
    if frozen["evaluation_code_sha256"] != evaluator_hash():
        raise ValueError("Evaluation code changed after freeze")
    if frozen["thresholds"] != THRESHOLDS or frozen.get("policy_version") != POLICY_VERSION:
        raise ValueError("Thresholds/policy differ from the frozen implementation")
    if frozen.get("runtime_versions") != runtime_versions():
        raise ValueError("Metric/model library versions changed after freeze")
    if frozen.get("validation_selection") and sha256(resolve_frozen(frozen["validation_selection"]["path"])) != frozen["validation_selection"]["sha256"]:
        raise ValueError("Validation selection changed after freeze")
    # Exclusive attempt marker is written BEFORE decoding the first test sample.
    output.mkdir(parents=True, exist_ok=False)
    receipt_path = freeze_path.with_suffix(".test_attempt.json")
    create_json(receipt_path, dict(freeze_sha256=sha256(freeze_path), output=str(output.resolve()),
                                   status="TEST_OPENED_DO_NOT_TUNE_ON_THIS_TEST"))
    registry = load_registry(root, allow_unreviewed=True, splits=("test",))
    if canonical_hash(registry) != frozen["corpus_sha256"]:
        raise ValueError("Corpus changed after freeze")
    contract = read_json(root / "scene_contract.json")
    if canonical_hash(contract) != frozen["scene_contract_sha256"]:
        raise ValueError("Scene contract changed after freeze")
    recipes = load_recipes(root, "test")
    if canonical_hash(recipes) != frozen["test_recipe_sha256"]:
        raise ValueError("Test recipes changed after freeze")
    # Representative examples are chosen from annotations BEFORE inference,
    # including clean speech and alert-only cases, never from favorable scores.
    patterns = [(0, 0, 0, 1, 0), (0, 1, 0, 1, 0), (1, 1, 0, 1, 0),
                (0, 1, 1, 1, 0), (0, 0, 1, 1, 0), (0, 0, 0, 1, 1),
                (0, 1, 0, 1, 1), (0, 0, 0, 0, 0)]
    audio_ids = []
    for pattern in patterns:
        match = next((r["scene_id"] for r in recipes if condition_key(r) == pattern), None)
        if match is not None and match not in audio_ids:
            audio_ids.append(match)
    audio_ids = set((audio_ids + [r["scene_id"] for r in recipes if r["scene_id"] not in audio_ids])[:save_audio])
    models = []
    for item in frozen["checkpoints"]:
        path = resolve_frozen(item["path"])
        if sha256(path) != item["sha256"]:
            raise ValueError("Checkpoint changed after freeze")
        model, obj = load_checkpoint(path)
        models.append((model, item))
    event_model, event_calibration = None, None
    if frozen.get("event_model"):
        from .events import load_events
        ei = frozen["event_model"]
        if sha256(resolve_frozen(ei["calibration"])) != ei["calibration_sha256"]:
            raise ValueError("Event calibration changed after freeze")
        event_model, event_calibration = load_events(resolve_frozen(ei["checkpoint"]), resolve_frozen(ei["calibration"]))
    torch.set_num_threads(4)
    rows, event_predictions, differences = [], [], []
    for idx, recipe in enumerate(recipes):
        mix, stems = build_scene(root, registry, recipe)
        spec = spectrum(torch.from_numpy(mix))[0]
        target_spec = spectrum(torch.from_numpy(stems[TARGETS[recipe["target_id"]]]))[0]
        privileged = (1 - target_spec.abs() / (target_spec.abs() + (spec - target_spec).abs() + 1e-8)).clamp_min(10 ** (-12 / 20))
        assisted_decision = resolve(TARGETS[recipe["target_id"]], alert_detected=recipe["alert_present"])["decision"]
        methods = [("unprocessed", None, torch.ones_like(spec.real), assisted_decision, "assisted"),
                   ("causal_minimum_statistics", None, classic_gain(spec), assisted_decision, "assisted"),
                   ("oracle_IRM_privileged", None, privileged, assisted_decision, "assisted")]
        event_probs = None
        if event_model is not None:
            with torch.no_grad():
                event_probs = torch.sigmoid(event_model(features(spec)[None]))[0].numpy()
            event_predictions.append(dict(scene_id=recipe["scene_id"], probabilities=event_probs.tolist(),
                                          labels=[float(c in recipe["parts"]) for c in TARGETS + ("speech", "alert")]))
        for model, item in models:
            with torch.no_grad():
                feat = features(spec)[None]
                label = torch.tensor([recipe["target_id"]])
                if item["conditioning"] == "none":
                    label.zero_()
                # BLOCK precedes inference. Do not manufacture an automatic alert detector.
                if recipe["alert_present"]:
                    gain = torch.ones_like(spec.real)
                    wrong = gain
                else:
                    mask = model(feat, label)
                    gain = model.gain(mask)[0]
                    wrong = gain if item["conditioning"] == "none" else model.gain(model(feat, 1 - label))[0]
                    differences.append(dict(scene_id=recipe["scene_id"], seed=item["seed"],
                                            loss=item["loss"], conditioning=item["conditioning"],
                                            gain_mean_abs_class_swap=float((gain - wrong).abs().mean())))
            name = f"cnn_{item.get('architecture', 'temporal')}_{item['loss']}_{item['conditioning']}"
            methods.append((name, item["seed"], gain, assisted_decision, "assisted"))
            if not recipe["alert_present"]:
                methods.append((name + "_class_swapped", item["seed"], wrong, assisted_decision, "assisted"))
            if event_probs is not None:
                thresholds = event_calibration["thresholds"]
                integrated_decision = resolve(TARGETS[recipe["target_id"]],
                    alert_detected=event_probs[3] >= thresholds[3],
                    target_detected=event_probs[recipe["target_id"]] >= thresholds[recipe["target_id"]])["decision"]
                if integrated_decision != "ALLOW":
                    integrated_gain = torch.ones_like(spec.real)
                else:
                    with torch.no_grad():
                        integrated_gain = model.gain(model(feat, label))[0]
                methods.append((name + "_M2_gate", item["seed"], integrated_gain,
                                integrated_decision, "integrated_requested_target"))
        for method, seed, gain, decision, mode in methods:
            if mode == "assisted" and recipe["alert_present"]:
                gain = torch.ones_like(spec.real)
            row, out = _row(method, seed, recipe, mix, stems, spec, gain, decision=decision, mode=mode)
            rows.append(row)
            if recipe["scene_id"] in audio_ids and "class_swapped" not in method:
                path = output / "audio" / f"{recipe['scene_id']}_{method}_{seed}.wav"
                path.parent.mkdir(exist_ok=True)
                sf.write(path, out, SR, subtype="FLOAT")
        if recipe["scene_id"] in audio_ids:
            sf.write(output / "audio" / f"{recipe['scene_id']}_input.wav", mix, SR, subtype="FLOAT")
            sf.write(output / "audio" / f"{recipe['scene_id']}_speech_reference.wav", stems["speech"], SR, subtype="FLOAT")
        if (idx + 1) % 20 == 0:
            print(f"test {idx + 1}/{len(recipes)}", flush=True)
    with (output / "per_scene.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summaries = []
    training_meta = {(f"cnn_{m['architecture']}_{m['loss']}_{m['conditioning']}", m["seed"]): m for m in frozen["checkpoints"]}
    for method, seed in sorted({(r["method"], r["seed"]) for r in rows}, key=str):
        subset = [r for r in rows if r["method"] == method and r["seed"] == seed]
        eligible = [r for r in subset if r["both_ok"] is not None]
        active = [r for r in subset if r["decision"] == "ALLOW"]
        item = dict(method=method, seed=seed, scenes=len(subset),
                    allowed_scenes=len(active),
                    bypass_scenes=sum(r["decision"] == "BYPASS_TARGET_NOT_DETECTED" for r in subset),
                    joint_eligible=len(eligible), joint_pass=sum(r["both_ok"] for r in eligible),
                    joint_pass_rate=float(np.mean([r["both_ok"] for r in eligible])) if eligible else None,
                    failures=[r["scene_id"] for r in eligible if not r["both_ok"]],
                    target_absent_false_attenuations=sum(r["target_absent_false_attenuation"] is True for r in active),
                    target_absent_with_speech=sum(not r["target_present"] and r["speech_present"] for r in active),
                    block_max_abs_gain_error=max([abs(r["gain_mean"] - 1) for r in subset if r["decision"] == "BLOCK"] or [0]))
        base_method = method.removesuffix("_class_swapped").removesuffix("_M2_gate")
        if (base_method, seed) in training_meta:
            item["training_status"] = training_meta[(base_method, seed)]["training_status"]
            item["training_scene_contract_sha256"] = training_meta[(base_method, seed)]["training_scene_contract_sha256"]
        item["joint_condition_statistics"] = {}
        for metric in ("A_target_db", "A_protected_db", "STOI_delta"):
            values = [r[metric] for r in eligible if r.get(metric) is not None]
            item["joint_condition_statistics"][metric] = (dict(
                mean=float(np.mean(values)), median=float(np.median(values)),
                p5=float(np.quantile(values, .05)), p95=float(np.quantile(values, .95)), n=len(values))
                if values else None)
        item["protected_alert_attenuations_gt_1db"] = sum(r["A_alert_db"] is not None and r["A_alert_db"] > 1 for r in subset)
        item["estimated_alert_blocks"] = sum(r["decision"] == "BLOCK" for r in subset)
        for metric, grouping in (("A_target_db", "target_group"), ("A_protected_db", "speaker_group"),
                                  ("A_nontarget_db", "nontarget_group"),
                                  ("SI_SDRi_protected_db", "speaker_group"), ("STOI_delta", "speaker_group")):
            item[metric] = group_ci(active, metric, grouping)
        item["by_class"] = {}
        for cls in TARGETS:
            selected = [r for r in active if r["target_class"] == cls]
            joint = [r for r in selected if r["both_ok"] is not None]
            item["by_class"][cls] = dict(
                scenes=len(selected), joint_eligible=len(joint),
                joint_pass=sum(r["both_ok"] for r in joint),
                A_target_db=group_ci(selected, "A_target_db", "target_group"),
                A_protected_db=group_ci(selected, "A_protected_db", "speaker_group"))
        summaries.append(item)
    # Pair scene-level improvements against DSP using identical mixtures, then cluster by source.
    paired = []
    dsp = {r["scene_id"]: r for r in rows if r["method"] == "causal_minimum_statistics"}
    for r in rows:
        if r["method"].startswith("cnn_") and not r["method"].endswith("_class_swapped") and r["decision"] == "ALLOW":
            ref = dsp[r["scene_id"]]
            paired.append(dict(scene_id=r["scene_id"], method=r["method"], seed=r["seed"],
                               target_group=r["target_group"], speaker_group=r["speaker_group"],
                               delta_A_target_db=r["A_target_db"] - ref["A_target_db"] if r["A_target_db"] is not None else None,
                               delta_A_protected_db=r["A_protected_db"] - ref["A_protected_db"] if r["A_protected_db"] is not None else None,
                               delta_STOI=r["STOI_output"] - ref["STOI_output"] if r["STOI_output"] is not None else None))
    write_json(output / "class_conditioning.json", differences)
    write_json(output / "paired_differences.json", paired)
    paired_summaries = []
    for method, seed in sorted({(r["method"], r["seed"]) for r in paired}, key=str):
        selected = [r for r in paired if r["method"] == method and r["seed"] == seed]
        paired_summaries.append(dict(method=method, seed=seed,
                                     delta_A_target_db=group_ci(selected, "delta_A_target_db", "target_group"),
                                     delta_A_protected_db=group_ci(selected, "delta_A_protected_db", "speaker_group"),
                                     delta_STOI=group_ci(selected, "delta_STOI", "speaker_group")))
    write_json(output / "paired_summary.json", paired_summaries)
    # A changed embedding response alone does not establish semantic extraction.
    # Compare acoustic outcomes for correct vs swapped labels on IDENTICAL scenes.
    lookup = {(r["method"], r["seed"], r["scene_id"]): r for r in rows}
    conditioning_effect = []
    for method, seed in sorted({(r["method"], r["seed"]) for r in rows
                               if r["method"].startswith("cnn_") and r["mode"] == "assisted"
                               and not r["method"].endswith("_class_swapped")}, key=str):
        pairs = []
        for r in rows:
            if r["method"] != method or r["seed"] != seed or r["decision"] != "ALLOW":
                continue
            wrong = lookup.get((method + "_class_swapped", seed, r["scene_id"]))
            if wrong is None:
                continue
            pairs.append(dict(target_group=r["target_group"], speaker_group=r["speaker_group"], nontarget_group=r["nontarget_group"],
                              delta_target_db=r["A_target_db"] - wrong["A_target_db"] if r["A_target_db"] is not None else None,
                              delta_nontarget_db=r["A_nontarget_db"] - wrong["A_nontarget_db"] if r["A_nontarget_db"] is not None else None,
                              delta_protected_db=r["A_protected_db"] - wrong["A_protected_db"] if r["A_protected_db"] is not None else None))
        conditioning_effect.append(dict(method=method, seed=seed,
                                        correct_minus_swapped_A_target_db=group_ci(pairs, "delta_target_db", "target_group"),
                                        correct_minus_swapped_A_nontarget_db=group_ci(pairs, "delta_nontarget_db", "nontarget_group"),
                                        correct_minus_swapped_A_protected_db=group_ci(pairs, "delta_protected_db", "speaker_group")))
    write_json(output / "conditioning_effect.json", conditioning_effect)
    event_metrics = None
    if event_predictions:
        from .events import classification_metrics
        event_metrics = classification_metrics(np.array([r["probabilities"] for r in event_predictions]),
                                               np.array([r["labels"] for r in event_predictions]),
                                               event_calibration["thresholds"])
        write_json(output / "M2_predictions.json", event_predictions)
    # A frozen attempt is a result, including failure. No code path silently issues GO.
    report = dict(status="REWORK", scientific_GO=False, test_used=True,
                  freeze_sha256=sha256(freeze_path), test_scenes=len(recipes),
                  condition_coverage=coverage(recipes),
                  silence_control_scenes=sum(not r["parts"] for r in recipes),
                  real_recording_mixture_scenes=sum(bool(r["parts"]) for r in recipes),
                  distinct_mixture_hashes=len({r["mixture_pcm_sha256"] for r in rows}),
                  registered_test_target_groups=len({a["source_group"] for a in registry["assets"]
                                                  if a["split"] == "test" and a["role"] == "target"}),
                  registered_test_speakers=len({a["speaker_id"] for a in registry["assets"]
                                                  if a["split"] == "test" and a["role"] == "speech"}),
                  observed_target_groups=len({r["target_group"] for r in rows if r["target_group"]}),
                  observed_speakers=len({r["speaker_group"] for r in rows if r["speaker_group"]}),
                  summaries=summaries, M2_test_metrics=event_metrics,
                  open_gates=["Human isolation/listening review", "Perceptual/cropped duplicate review",
                              "Independent field-domain evaluation", "M2 multilabel integration and protection recall",
                              "Academic acceptance of prospective architecture/loss/classes",
                              "P2 streaming and physical latency not executed"],
                  interpretation="Scenes share source recordings. Count source groups, not mixtures, "
                                 "as independent evidence; all references are candidate pseudo-stems.",
                  historical_cnn=frozen["historical_cnn"])
    write_json(output / "report.json", report)
    create_json(output / "completed.json", dict(per_scene_sha256=sha256(output / "per_scene.csv"),
                                                report_sha256=sha256(output / "report.json")))
    return report
