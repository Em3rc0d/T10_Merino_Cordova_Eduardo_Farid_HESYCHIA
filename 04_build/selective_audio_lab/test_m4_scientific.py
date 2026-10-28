"""Behavioral gates: causal features/model, real split leakage, safe inference, freeze integrity."""
import copy
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

sys.path.insert(0, str(Path(__file__).parent / "src"))
from m4_scientific.common import canonical_hash, create_json
from m4_scientific.corpus import audit_assets
from m4_scientific.evaluation import attenuation, group_ci, si_sdr
from m4_scientific.inference import predict_wave
from m4_scientific.model import MaskCNN, ModelConfig, features, spectrum, synthesize
from m4_scientific.training import losses

torch.set_num_threads(2)


@pytest.mark.parametrize("length", [1, 159, 160, 161, 32000, 32017])
def test_identity_wola_keeps_edges_and_length(length):
    x = torch.randn(2, length) * .1
    y = synthesize(spectrum(x), length)
    assert y.shape == x.shape
    assert torch.max(torch.abs(y - x)) < 1e-6


def test_frozen_mixture_gain_supports_linear_stem_attribution():
    stems = torch.randn(3, 8000) * .04
    specs = spectrum(stems)
    gain = .25 + .75 * torch.rand_like(specs[:1].real)
    combined = synthesize(spectrum(stems.sum(0)) * gain, 8000)
    attributed = synthesize(specs * gain, 8000).sum(0)
    assert torch.max(torch.abs(combined[0] - attributed)) < 1e-6


def test_frontend_and_cnn_never_read_future():
    torch.manual_seed(12)
    x = torch.randn(1, 6000)
    changed = x.clone()
    changed[:, 3200:] += torch.randn_like(changed[:, 3200:]) * 50
    f1, f2 = features(spectrum(x)), features(spectrum(changed))
    assert torch.equal(f1[:, :20], f2[:, :20])
    model = MaskCNN(ModelConfig(channels=16)).eval()
    with torch.no_grad():
        a, b = model(f1, torch.tensor([0])), model(f2, torch.tensor([0]))
    assert torch.allclose(a[:, :20], b[:, :20], atol=1e-6)


def test_spectral_candidate_has_no_temporal_normalization_leak():
    from m4_scientific.model import build_model
    model = build_model(ModelConfig(channels=4, architecture="spectral")).eval()
    x = torch.rand(1, 50, 257)
    changed = x.clone()
    changed[:, 30:] += 20
    with torch.no_grad():
        a, b = model(x, torch.tensor([0])), model(changed, torch.tensor([0]))
    assert torch.allclose(a[:, :30], b[:, :30], atol=1e-6)


def test_model_class_changes_response_and_gradients_reach_embedding():
    model = MaskCNN(ModelConfig(channels=16))
    x = torch.rand(2, 40, 257)
    out = model(x, torch.tensor([0, 1]))
    out.mean().backward()
    assert torch.isfinite(model.embedding.weight.grad).all()
    assert model.embedding.weight.grad.abs().sum() > 0
    with torch.no_grad():
        a = model(x[:1], torch.tensor([0]))
        b = model(x[:1], torch.tensor([1]))
    assert (a - b).abs().mean() > 1e-6


def test_block_does_not_load_missing_checkpoint():
    x = np.random.default_rng(1).normal(size=320).astype(np.float32)
    y, meta = predict_wave(x, "/nonexistent.pt", "vacuum_cleaner", block_protected=True)
    assert np.array_equal(x, y)
    assert meta["decision"] == "BLOCK" and meta["model_called"] is False
    with pytest.raises(FileNotFoundError):
        predict_wave(x, "/nonexistent.pt", "vacuum_cleaner")


def test_estimated_alert_gate_bypasses_before_loading_m4(monkeypatch):
    from m4_scientific import events
    class Detector:
        def __call__(self, x):
            return torch.tensor([[-20., -20., 20., 20.]])
    monkeypatch.setattr(events, "load_events", lambda *a: (Detector(), {"thresholds": [.5] * 4}))
    import m4_scientific.inference as inference
    monkeypatch.setattr(inference, "sha256", lambda path: "fixture")
    x = np.random.default_rng(1).normal(0, .1, 3200).astype(np.float32)
    out, meta = predict_wave(x, "/missing-m4.pt", "chainsaw", event_checkpoint="event-fixture",
                             event_calibration="calibration-fixture")
    assert np.array_equal(x, out)
    assert meta["decision"] == "BLOCK"
    assert meta["model_called"] is False


@pytest.mark.parametrize("label", ["siren", "speech", "clock_alarm", "car_horn"])
def test_candidate_catalogue_preserves_legacy_protected_labels(label):
    x = np.ones(320, dtype=np.float32) * .1
    out, meta = predict_wave(x, "/missing-m4.pt", label)
    assert np.array_equal(x, out)
    assert meta["decision"] == "BLOCK" and meta["model_called"] is False


def test_target_absent_speech_absent_loss_has_finite_gradients():
    model = MaskCNN(ModelConfig(channels=16))
    feat = torch.rand(2, 30, 257)
    prediction = model(feat, torch.tensor([0, 1]))
    batch = dict(ideal=torch.zeros_like(prediction),
                 mixture=torch.complex(feat, feat), target=torch.zeros_like(feat, dtype=torch.complex64),
                 protected=torch.zeros_like(feat))
    loss, _ = losses(model, prediction, batch,
                      dict(loss="composite", reconstruction_weight=.5, speech_weight=.2))
    loss.backward()
    assert torch.isfinite(loss)
    assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)


@pytest.mark.parametrize("group_key", ["source_group", "speaker_id", "raw_sha256", "pcm_sha256", "normalized_pcm_hash"])
def test_leakage_rejects_source_speaker_or_transcoded_duplicate(group_key):
    rows = []
    for split in ("train", "val", "test"):
        for cls in ("vacuum_cleaner", "chainsaw", "speech", "background", "alert"):
            key = f"{split}_{cls}"
            rows.append(dict(asset_id=key, split=split, role=cls, **{"class": cls},
                             source_group=key, speaker_id=key if cls == "speech" else "",
                             raw_sha256=key, pcm_sha256=key, normalized_pcm_hash=key,
                             license_evidence="LICENSE"))
    assert audit_assets(rows, verify_files=False)["status"] == "PASS"
    rows[5][group_key] = rows[0][group_key] or "shared-speaker"
    rows[0][group_key] = rows[5][group_key]
    assert audit_assets(rows, verify_files=False)["status"] == "BLOCKED"


def test_metrics_do_not_confuse_scale_invariance_and_attenuation():
    x = np.random.default_rng(1).normal(size=3200)
    assert abs(attenuation(x, x * .5) - 6.020599913) < 1e-6
    assert si_sdr(x * .5, x) > 100
    assert attenuation(np.zeros_like(x), x) is None
    assert si_sdr(np.zeros_like(x), x) is None


def test_bootstrap_counts_sources_instead_of_copies():
    rows = [{"group": "a", "metric": 1.}] * 100 + [{"group": "b", "metric": 3.}]
    summary = group_ci(rows, "metric", "group")
    assert summary["group_mean"] == 2.
    assert summary["groups"] == 2


def test_freeze_file_cannot_be_rewritten(tmp_path):
    p = tmp_path / "freeze.json"
    create_json(p, {"checkpoint": "a"})
    with pytest.raises(FileExistsError):
        create_json(p, {"checkpoint": "b"})


def test_pcm_conversion_has_stable_container_and_exact_samples(tmp_path):
    import soundfile as sf
    from m4_scientific.corpus import _convert
    from m4_scientific.common import sha256
    original = tmp_path / "source.wav"
    wave = np.random.default_rng(9).normal(0, .1, 16000).astype(np.float32)
    sf.write(original, wave, 16000, subtype="PCM_16")
    first, second = tmp_path / "one.wav", tmp_path / "two.wav"
    _convert(original, first)
    _convert(original, second)
    assert sha256(first) == sha256(second)
    assert b"PEAK" not in first.read_bytes()[:100]
    a, _ = sf.read(original, dtype="float32")
    b, _ = sf.read(first, dtype="float32")
    assert np.array_equal(a, b)


def test_full_factorial_design_covers_clean_speech_alert_negatives_and_silence(tmp_path):
    import soundfile as sf
    from m4_scientific.scenes import make_recipes, coverage
    rows = []
    for split in ("train", "val", "test"):
        for cls in ("vacuum_cleaner", "chainsaw", "speech", "background", "alert"):
            path = tmp_path / f"{split}_{cls}.wav"
            sf.write(path, np.ones(16000, dtype=np.float32) * .1, 16000)
            rows.append(dict(asset_id=path.stem, split=split, **{"class": cls},
                             role=cls, path=path.name, source_group=path.stem))
    result = make_recipes(tmp_path, {"assets": rows}, counts=(160, 160, 160), seconds=.5,
                          condition_version="full-factorial-v2")
    for recipes in result.values():
        audit = coverage(recipes)
        assert audit["status"] == "PASS" and audit["observed_conditions"] == 32
        assert audit["pure_speech_scenes"] > 0 and audit["silence_scenes"] > 0
        assert any(r["alert_present"] and not r["target_present"] for r in recipes)


def test_reproduced_containers_match_frozen_hash_without_audio_distribution(tmp_path):
    import soundfile as sf
    from m4_scientific.reproduction import export_containers, restore
    from m4_scientific.corpus import _convert
    from m4_scientific.common import sha256, write_json
    original, rebuilt = tmp_path / "frozen", tmp_path / "rebuilt"
    for root in (original, rebuilt):
        (root / "pcm").mkdir(parents=True)
    x = np.random.default_rng(9).normal(0, .1, 16000).astype(np.float32)
    frozen_pcm = original / "pcm/a.wav"
    sf.write(frozen_pcm, x, 16000, subtype="FLOAT")
    row = dict(asset_id="a", path="pcm/a.wav", pcm_sha256=sha256(frozen_pcm))
    write_json(original / "registry.json", dict(assets=[row]))
    containers = tmp_path / "containers.json"
    export_containers(original, containers)
    _convert(frozen_pcm, rebuilt / "pcm/a.wav")
    assert sha256(rebuilt / "pcm/a.wav") != row["pcm_sha256"]
    write_json(rebuilt / "registry.json", dict(assets=[]))
    report = restore(rebuilt, original / "registry.json", containers)
    assert report["samples_changed"] is False
    assert sha256(rebuilt / "pcm/a.wav") == row["pcm_sha256"]


def test_pipeline_trains_freezes_evaluates_once_without_test_tuning(tmp_path):
    import soundfile as sf
    from m4_scientific.common import sha256, write_json, read_json
    from m4_scientific.scenes import save_recipes
    from m4_scientific.training import fit
    from m4_scientific.evaluation import freeze, evaluate
    # Explicit mathematical fixture. Never added to the real-audio results.
    root = tmp_path / "FIXTURE_ONLY"
    root.mkdir()
    rng = np.random.default_rng(90)
    assets = []
    for split in ("train", "val", "test"):
        for cls in ("vacuum_cleaner", "chainsaw", "speech", "background", "alert"):
            aid = f"{split}_{cls}"
            path = root / f"{aid}.wav"
            sf.write(path, rng.normal(0, .05, 16000).astype(np.float32), 16000, subtype="FLOAT")
            assets.append(dict(asset_id=aid, split=split, **{"class": cls},
                               role="target" if cls in ("vacuum_cleaner", "chainsaw") else cls,
                               source_group=aid, speaker_id=aid if cls == "speech" else "",
                               raw_sha256=sha256(path), pcm_sha256=sha256(path),
                               normalized_pcm_hash=sha256(path), path=path.name,
                               license_evidence="FIXTURE_ONLY", review="FIXTURE_ONLY"))
    registry = dict(assets=assets, review_status="FIXTURE_ONLY")
    write_json(root / "registry.json", registry)
    save_recipes(root, registry, counts=(4, 4, 4), seconds=.5, seed=123)
    config = dict(seed=1, epochs=1, batch_size=2, channels=16, threads=1,
                  loss="composite", reconstruction_weight=.5, speech_weight=.2,
                  learning_rate=.001, weight_decay=.0001, patience=1, conditioning="class")
    summary = fit(root, tmp_path / "run", config, pilot_unreviewed=True)
    assert summary["test_audio_read"] is False
    frozen = tmp_path / "freeze.json"
    selection = tmp_path / "validation_selection.json"
    create_json(selection, dict(checkpoint_sha256=summary["checkpoint_sha256"], selection="fixture-validation-only"))
    freeze(root, [tmp_path / "run" / "candidate.pt"], frozen, selection_path=selection)
    report = evaluate(root, frozen, tmp_path / "result", save_audio=0)
    assert report["test_scenes"] == 4
    assert report["scientific_GO"] is False
    assert len(report["summaries"]) == 5
    with pytest.raises(FileExistsError):
        evaluate(root, frozen, tmp_path / "second-result", save_audio=0)


# V2 deep-learning gates: these test the objective, NOT acoustic scientific GO.

def _v2_fixture():
    from m4_scientific.model import MaskCNN, ModelConfig
    model = MaskCNN(ModelConfig(channels=8))
    labels = torch.tensor([0, 1])
    feats = torch.rand(2, 40, 257)
    pred = model(feats, labels)
    swapped = model(feats, 1 - labels)
    target = torch.rand(2, 40, 257) * .2
    target[1] = 0.0  # Explicit target-absent supervision
    voice = torch.rand(2, 40, 257) * .1
    voice[0] = 0.0   # Explicit speech-absent supervision
    other = torch.rand(2, 40, 257) * .1
    batch = dict(ideal=target / (target + voice + other + 1e-8),
                 target=target.to(torch.complex64), protected=voice,
                 nontarget=other.to(torch.complex64),
                 mixture=(target + voice + other).to(torch.complex64),
                 alert_flag=torch.zeros(2))
    return model, pred, swapped, batch


def test_v2_joint_loss_is_finite_and_updates_deep_cnn():
    from m4_scientific.v2_objective import constrained_selective_loss
    model, prediction, swapped, batch = _v2_fixture()
    loss, details = constrained_selective_loss(model, prediction, batch, {},
                                               swapped_prediction=swapped)
    assert torch.isfinite(loss)
    assert all(torch.isfinite(v) for v in details.values())
    loss.backward()
    assert model.embedding.weight.grad is not None
    assert torch.isfinite(model.embedding.weight.grad).all()
    assert model.embedding.weight.grad.abs().sum() > 0
    assert model.mask_head.weight.grad is not None


def test_v2_empty_stems_do_not_create_nan_or_false_attenuation():
    from m4_scientific.v2_objective import constrained_selective_loss
    model, prediction, swapped, batch = _v2_fixture()
    for k in ("target", "protected", "nontarget", "mixture"):
        batch[k] = torch.zeros_like(batch[k])
    batch["ideal"] = torch.zeros_like(batch["ideal"])
    loss, metrics = constrained_selective_loss(model, prediction, batch, {},
                                               swapped_prediction=swapped)
    assert torch.isfinite(loss)
    assert all(torch.isfinite(v) for v in metrics.values())


def test_v2_counterfactual_rejects_swapped_class_on_same_mixture():
    from m4_scientific.v2_objective import constrained_selective_loss
    from m4_scientific.model import MaskCNN, ModelConfig
    model = MaskCNN(ModelConfig(channels=8))
    n = (1, 5, 257)
    target = torch.zeros(n)
    other = torch.zeros(n)
    target[..., :40] = 1.0
    other[..., 100:140] = 1.0
    data = dict(target=target.to(torch.complex64),
                nontarget=other.to(torch.complex64),
                protected=torch.zeros(n), mixture=(target + other).to(torch.complex64),
                ideal=torch.zeros(n), alert_flag=torch.zeros(1))
    correct, swapped = torch.zeros(n), torch.zeros(n)
    correct[..., :40] = 1.0
    swapped[..., 100:140] = 1.0
    cfg = dict(mask_weight=0., target_weight=0., speech_weight=0.,
               other_weight=0., absent_weight=0., class_weight=1.)
    _, good = constrained_selective_loss(model, correct, data, cfg,
                                         swapped_prediction=swapped)
    _, bad = constrained_selective_loss(model, swapped, data, cfg,
                                        swapped_prediction=correct)
    assert good["contrast"] < bad["contrast"]


def test_v2_target_absent_requires_near_identity():
    from m4_scientific.v2_objective import constrained_selective_loss
    from m4_scientific.model import MaskCNN, ModelConfig
    model = MaskCNN(ModelConfig(channels=8))
    n = (2, 5, 257)
    source = torch.ones(n)
    data = dict(ideal=torch.zeros(n), target=torch.zeros(n, dtype=torch.complex64),
                nontarget=source.to(torch.complex64), protected=source,
                mixture=(2*source).to(torch.complex64), alert_flag=torch.zeros(2))
    cfg = dict(mask_weight=0., target_weight=0., speech_weight=0.,
               other_weight=0., class_weight=0., absent_weight=1.)
    _, identity = constrained_selective_loss(model, torch.zeros(n), data, cfg)
    _, broad = constrained_selective_loss(model, .8 * torch.ones(n), data, cfg)
    assert broad["absent"] > identity["absent"]


def test_v2_requires_counterfactual_if_contrast_enabled():
    from m4_scientific.v2_objective import constrained_selective_loss
    model, prediction, _, batch = _v2_fixture()
    with pytest.raises(ValueError, match="swapped-class"):
        constrained_selective_loss(model, prediction, batch, {"class_weight": 1.0})


def test_v2_alerts_are_not_supervised_as_attenuable():
    from m4_scientific.v2_objective import constrained_selective_loss
    model, prediction, swapped, batch = _v2_fixture()
    batch["alert_flag"] = torch.ones(2)
    loss, parts = constrained_selective_loss(model, prediction, batch, {},
                                             swapped_prediction=swapped)
    assert float(loss) == pytest.approx(0., abs=1e-6)
    assert float(parts["eligible_joint_proxy"]) == pytest.approx(0., abs=1e-6)


def test_v2_class_conditional_training_can_learn_on_controlled_spectra():
    """Numeric trainability smoke only, NOT real-speech or scientific performance.

    The SAME mixture is repeated with two different requested target classes.
    The learned masks must be able to respond differently without changing
    acoustic inputs; no test-set recordings or labels are used here.
    """
    from m4_scientific.model import MaskCNN, ModelConfig, features
    from m4_scientific.training import losses
    from m4_scientific.v2_objective import spectral_attenuation_db

    torch.manual_seed(20261028)
    torch.set_num_threads(2)
    b, frames, bins = 8, 12, 257
    a = torch.zeros(b, frames, bins)
    b_source = torch.zeros_like(a)
    speech = torch.zeros_like(a)
    a[..., 20:27] = .75
    b_source[..., 140:147] = .75
    speech[..., 65:74] = .25
    labels = torch.tensor([0, 1] * 4)
    is_a = (labels == 0)[:, None, None]
    target = torch.where(is_a, a, b_source)
    other = torch.where(is_a, b_source, a)
    mixture = a + b_source + speech
    batch = dict(ideal=target / (target + other + speech + 1e-8),
                 mixture=mixture.to(torch.complex64),
                 target=target.to(torch.complex64),
                 nontarget=other.to(torch.complex64),
                 protected=speech, alert_flag=torch.zeros(b))
    x = features(batch["mixture"])
    model = MaskCNN(ModelConfig(channels=12, embedding=12, dilations=(1, 2)))
    optimizer = torch.optim.AdamW(model.parameters(), lr=.01, weight_decay=0.)
    cfg = dict(loss="selective_v2", mask_weight=.1,
               target_weight=1., speech_weight=1., other_weight=1.,
               absent_weight=1., class_weight=1., temperature_db=.5)
    history = []
    for i in range(80):
        pred = model(x, labels)
        swapped = model(x, 1 - labels)
        loss, metrics = losses(model, pred, batch, cfg, swapped_prediction=swapped)
        if i == 0:
            initial = float(loss.detach())
        assert torch.isfinite(loss)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
        history.append(float(loss.detach()))
    model.eval()
    with torch.no_grad():
        correct = model(x, labels)
        swapped = model(x, 1 - labels)
        final_loss, _ = losses(model, correct, batch, cfg,
                               swapped_prediction=swapped)
        correct_att = spectral_attenuation_db(model.gain(correct), batch["target"])
        swapped_att = spectral_attenuation_db(model.gain(swapped), batch["target"])
    assert float(final_loss) < .8 * initial, (initial, float(final_loss))
    assert float((correct_att - swapped_att).mean()) > .5


def test_v2_paired_comparator_refuses_test_and_mismatched_scenes(tmp_path):
    """Comparison must use validation and identical actual mixtures."""
    import csv
    import json
    sys.path.insert(0, str(Path(__file__).parent / "experiments"))
    from compare_m4_validation_only import compare

    folder = tmp_path / "validation"
    folder.mkdir()
    report = dict(split="validation_only", test_audio_read=False,
                  summaries=[dict(run="old"), dict(run="new")])
    (folder / "validation_report.json").write_text(json.dumps(report))
    base = dict(scene_id="val-00001", mixture_pcm_sha256="same-mixture",
                target_class="chainsaw", target_present="True",
                speech_present="True", alert_present="False",
                target_group="t1", speaker_group="v1")
    rows = [{**base, "method":"old", "both_ok":"False",
             "A_target_db":"2.", "A_protected_db":"1.2"},
            {**base, "method":"new", "both_ok":"True",
             "A_target_db":"7.", "A_protected_db":"0.8"}]
    path = folder / "per_scene.csv"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = compare(folder, "old", "new")
    assert result["eligible_pairs"] == 1
    assert result["target_delta_db"]["mean_equal_group"] == pytest.approx(5.)
    assert result["protected_delta_db"]["mean_equal_group"] == pytest.approx(-.4)
    assert result["candidate_joint_pass"] == 1
    assert result["test_used"] is False
    report["split"] = "test"
    (folder / "validation_report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="validation-only"):
        compare(folder, "old", "new")
    report["split"] = "validation_only"
    (folder / "validation_report.json").write_text(json.dumps(report))
    rows[1]["mixture_pcm_sha256"] = "different-mixture"
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="Unpaired"):
        compare(folder, "old", "new")
