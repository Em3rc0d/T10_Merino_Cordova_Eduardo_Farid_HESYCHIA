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
    freeze(root, [tmp_path / "run" / "candidate.pt"], frozen)
    report = evaluate(root, frozen, tmp_path / "result", save_audio=0)
    assert report["test_scenes"] == 4
    assert report["scientific_GO"] is False
    assert len(report["summaries"]) == 5
    with pytest.raises(FileExistsError):
        evaluate(root, frozen, tmp_path / "second-result", save_audio=0)
